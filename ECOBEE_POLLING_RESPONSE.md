# udi-poly-ecobee Polling Compliance Response

**Plugin:** Universal Devices Polyglot v3 plugin "Ecobee" (`udi-poly-ecobee`)
**Repository:** https://github.com/UniversalDevicesInc-PG3/udi-poly-ecobee
**Date:** April 2026

## Summary

Ecobee notified us that this plugin was generating an excessive number of
requests against the Ecobee API, well above the documented and reasonable
rate. Thank you for the report - it allowed us to find and fix several
distinct defects in our HTTP and polling logic that, in combination, could
amplify a single logical poll into many actual API calls under failure
conditions. This document describes what we found, what we changed, and
why those changes will keep the plugin within reasonable bounds going
forward.

For installs already at **180** seconds or longer between long polls, the
intended cadence is unchanged: a `/thermostatSummary` call each long poll
(Ecobee's recommended interval is about **3 minutes**), followed by a
`/thermostat` GET only for thermostats whose revision values changed, plus
periodic OAuth token refreshes. Installs that had Polyglot `longPoll` set
**below** 180 seconds are now clamped to **180** seconds so summary traffic
cannot exceed that rate. The defects below all caused the actual request
count under abnormal conditions (or misconfiguration) to far exceed that
intent.

## Root causes we identified

We treated this as a request-amplification problem and looked for every
place the plugin could turn one logical poll into many HTTP calls. The
material findings were:

1. **Aggressive HTTP retry policy on every request.** The `requests`
   session was configured with `total=30` retries and a 0.3 second
   exponential backoff, applied to **all** methods including `POST` to
   `/thermostat` (which is a non-idempotent write). A single transient
   `5xx` from Ecobee could therefore produce up to 31 HTTP attempts for
   one logical operation, spread over several minutes. Worse, writes to
   `/thermostat` could be silently re-issued.

2. **No first-class handling of HTTP 429.** When Ecobee returned `429 Too
   Many Requests`, the plugin had no specific handler, so the response
   handler treated it like any other unknown error and the next poll
   would simply resume hitting the API. The `Retry-After` header was
   ignored. This is the single biggest reason a rate-limited plugin
   would keep generating traffic.

3. **PIN authorization endpoint polled without honoring `interval`.**
   During the ecobeePin authorization flow, the plugin's `shortPoll` was
   calling `/token` on every short-poll tick (default ~30s) without
   reading the `interval` field returned by `/authorize`, and without
   handling the `slow_down` error response. If a user left the PIN
   screen open, the token endpoint was being polled indefinitely.

4. **Duplicate `/thermostatSummary` per long-poll cycle on recovery.**
   When a previous discover had failed (`discover_st == False`), the next
   `longPoll` would call `discover()` (which itself calls
   `/thermostatSummary` plus a `/thermostat` for any new node) and then
   immediately call `updateThermostats()` (which calls
   `/thermostatSummary` again). On the recovery path each cycle issued
   the summary call twice.

5. **`check_profile` re-fetched all programs on every discover.** Each
   discover unconditionally issued one `/thermostat?includeProgram=true`
   per thermostat, even when nothing about the profile or thermostat set
   had changed. Combined with #4, a recovery loop produced O(N+2)
   `/thermostat` GETs per long poll for N thermostats.

6. **`getThermostatFull` over-fetched on every refresh.** The routine
   refresh path fetched all 13 selection sections (events, program,
   settings, runtime, extendedRuntime, location, equipmentStatus,
   version, utility, alerts, weather, sensors, energy) every cycle,
   even though our update code only consumes a subset. While this does
   not increase request count, it inflates payload sizes and may have
   contributed to throttling decisions on Ecobee's side.

7. **No backoff on failed token refreshes.** A failed `/token` refresh
   set neither a cooldown nor a once-per-cycle marker. Subsequent API
   calls in the same long poll could each independently retry the
   refresh, multiplying `/token` traffic during outages or invalid-grant
   storms.

8. **No backoff on repeated `discover()` failures.** If discover failed
   on long-poll N, it ran again every 3 minutes thereafter with no
   spacing - and each attempt does the multi-call check_profile sweep
   from #5.

9. **Connection status was reported as "connected" before validation.**
   `_getRefresh()` set the visible "Ecobee Connected" driver to True as
   soon as the refresh POST returned HTTP 200, before we had checked
   whether the body contained an error or an `access_token`. Users seeing
   green-light status during outages are less likely to investigate, but
   are also more likely to manually press the POLL button repeatedly
   when something is "obviously" wrong, amplifying traffic further.

10. **Manual POLL command was unthrottled.** A frustrated user pressing
    POLL repeatedly during an outage could compound the traffic pattern.

11. **No per-cycle visibility into request volume.** Operators could not
    see how many calls a long poll was generating, so problem #1-#10 had
    no warning signal short of Ecobee's own throttling.

12. **Polyglot `longPoll` set below Ecobee's recommended interval.** The
    Polyglot Dashboard lets each operator configure the nodeserver's
    `longPoll` period in **seconds**. Nothing in the plugin previously
    prevented values such as **60** or **120** seconds. Because each long
    poll drives at least one `/thermostatSummary` call, cutting the period
    from 180s to 60s **triples** summary traffic for that install; a **30**
    second setting multiplies it by **six**, independently of thermostat
    count. Across many installs, a handful of aggressive settings
    materially inflated aggregate request volume against Ecobee.

## What we changed

All fixes are in this commit. The changes are defensive and reduce the
number of HTTP requests the plugin can issue per unit time. ISY-visible
thermostat behavior is unchanged for operators already using a **180**
second or longer `longPoll`; those with a shorter Polyglot interval will
see refreshes at most every **180** seconds instead of their previous
(higher-frequency) setting.

### A. Bounded, GET-only retry policy (`pgSession.py`)

- `Retry(total=30)` reduced to `Retry(total=3)`.
- `allowed_methods=frozenset(['GET'])` so `POST` and `DELETE` are never
  silently retried by `urllib3`. Writes to `/thermostat` are now executed
  exactly once and the caller sees any error directly.
- `status_forcelist` now includes `429` so urllib3 sleeps according to
  the server's `Retry-After` header before retrying (only for GETs).
- `respect_retry_after_header=True` and `raise_on_status=False` are set
  explicitly.

Worst-case retry inflation per logical GET dropped from up to **31x** to
**4x**, and writes are no longer multiplied at all.

### B. First-class HTTP 429 handling (`pgSession.py`, `Controller.py`)

- The response handler now detects `429`, parses `Retry-After` (with a
  conservative 60s minimum), and stores `rate_limited_until` on the
  session.
- `pgSession.get/post/delete` short-circuit and return `False` while the
  rate-limit window is open. They do not even open a TCP connection.
- `Controller.longPoll` and `Controller.cmd_poll` check
  `session.is_rate_limited()` up-front and skip the entire cycle if a
  rate-limit window is active.

The practical effect is that a single `429` response stops the plugin
from issuing **any** further requests until Ecobee's `Retry-After`
window elapses. Previously a `429` was effectively ignored.

### C. Honor PIN authorization `interval` and `slow_down` (`Controller.py`)

- `_getPin()` now reads `interval` from the `/authorize` response and
  uses it as the minimum spacing between subsequent `/token` calls.
- `shortPoll` enforces that minimum: if not enough time has elapsed
  since the last PIN poll, it returns without contacting Ecobee.
- `_getTokens()` now treats `error == "slow_down"` as a signal to
  double the polling interval (capped at 120s) rather than as a fatal
  error, and treats `error == "authorization_pending"` as a normal
  "user has not entered the PIN yet" condition.

This bounds the `/token` poll rate during the PIN window to at most
once per Ecobee-supplied interval, with automatic backoff on `slow_down`.

### D. No duplicate `/thermostatSummary` on recovery (`Controller.longPoll`)

- We now track whether `discover()` ran in the current long-poll cycle.
  If it did, we skip the immediate `updateThermostats()` call (whose
  first action is another `/thermostatSummary`). Existing nodes refresh
  on the next cycle, 3 minutes later.

### E. Lazy `check_profile()` (`Controller.py`)

- The per-thermostat `/thermostat?includeProgram=true` fetch only runs
  when the profile actually needs to be (re)built:
  - First run / no cached `profile_info` or `climates`, or
  - Plugin profile version changed across an upgrade, or
  - Set of thermostat IDs changed (added/removed thermostat).
- In steady state the per-thermostat program fetch is **not issued at all**
  during recovery discover loops.

### F. Trim routine refresh selection (`Controller.py`)

- Added `getThermostatRuntime(id, include_weather=...)` which requests only:
  `events, program, settings, runtime, equipmentStatus, sensors,
  energy`, and **optionally** `weather` when the thermostat's Weather
  driver (GV9) is enabled (see **M**).
- `updateThermostats()` uses this instead of the all-flags
  `getThermostatFull()` path for routine refreshes; new thermostats on
  discover use the same lean selection with `include_weather=False` by
  default.
- The dropped fields (`extendedRuntime`, `location`, `utility`,
  `version`, `alerts`) are not consumed by our refresh code, so this is
  a safe payload reduction with no behavioral change.

### G. Exponential backoff on repeated discover failures (`Controller.longPoll`)

- After a failed discover, the next attempt is delayed by `3 * 3^n`
  minutes (so 3, 9, 27, 81, 180, 180...) instead of being retried on
  every long poll tick (which is at least **180** seconds apart after fix L).
- A successful discover resets the counter immediately.

### H. Token refresh cooldown (`Controller.py`)

- A failed `/token` refresh now arms a cooldown timestamp
  (`_refresh_cooldown_until`, default `max(longPoll, 60)` seconds).
- `_checkTokens()` skips refresh attempts inside that window and uses
  the existing token if it has any time remaining.
- `_checkTokens()` also tracks `_last_refresh_attempt` per long-poll
  cycle and refuses to retry refresh more than once per cycle.

### I. Honest connection status (`Controller._getRefresh`)

- `set_ecobee_st(True)` is called **only** after `'access_token' in res_data`
  is verified.
- All error paths (`res is False`, `res_data is False`, `'error' in
  res_data`) now correctly set the status to False.

### J. Throttle manual POLL (`Controller.cmd_poll`)

- The user-initiated POLL command from ISY is now no-op'd if invoked
  more than once per 60 seconds, and is also gated by the rate-limit
  window check from B.

### K. Per-cycle request observability (`pgSession.py`, `Controller.longPoll`)

- `pgSession` keeps counters bucketed as
  `{authorize, token, summary, thermostat, other}` x `{GET, POST, DELETE}`
  for every request issued.
- `Controller.longPoll` logs a one-line summary at the end of each
  cycle, e.g.
  `longPoll: ecobee request counts (total=4): {'GET:summary': 1, 'GET:thermostat': 3}`
- This makes it possible for operators (and Ecobee, via support
  requests) to verify polling volume from the plugin's own logs without
  needing access to the upstream API gateway.

### L. Minimum Polyglot `longPoll` of 180 seconds (`Controller.handler_config`)

- `Controller.handler_config` now clamps `cfg_data['longPoll']` to at
  least **180** seconds (3 minutes), matching Ecobee's documented
  guidance for summary polling.
- If Polyglot is configured lower (e.g. 30, 60, or 120 seconds), the
  nodeserver logs a **warning** and uses **180** seconds anyway. The
  Dashboard value is not rewritten by the plugin; operators who want a
  shorter interval will still see their saved value in Polyglot, but
  runtime behavior will not poll faster than the minimum.
- This removes an entire class of **operator-configured** over-polling
  that scaled linearly with `3600 / longPoll` summary calls per install
  per hour.
- **Fleet-scale illustration** (how much that could inflate aggregate
  `/thermostatSummary` traffic for a ~200-install population) is in the
  subsection **Operator short `longPoll` (fix L) — substantial fleet impact**
  under *Illustrative fleet scale* below.

### M. Weather omitted by default (`includeWeather` + GV9 + one-time migration)

- **Default:** Thermostat driver **GV9 (Weather)** now defaults to **off**
  in `driversMap`, and routine `GET /1/thermostat` calls use
  `includeWeather: false` unless GV9 is **on** for that thermostat.
  Forecast and current-weather data are not separate HTTP calls in this
  plugin; they are embedded in the same thermostat JSON when
  `includeWeather` is true. Skipping it **does not reduce the number of
  GETs** per poll cycle, but it **materially shrinks response bodies** and
  Ecobee-side work per response for the majority of installs that do not
  need weather in ISY.
- **One-time migration (3.1.7):** On the **first** nodeserver start after
  upgrading from before **3.1.7**, **every** existing thermostat has GV9
  forced to **off**, weather/forecast child nodes removed, and
  `includeWeather` omitted on subsequent refreshes until the operator turns
  Weather back **on** in the Admin Console. The nodeserver stores the last
  applied migration level in custom data as **`ns_data_version`** (semver
  string, same as the running package version after migrations run), so
  **future releases can add more one-time steps** by comparing
  `ns_data_version` to new thresholds in `_apply_version_migrations`.
  Turning Weather **on** triggers an immediate `includeWeather: true`
  fetch for that thermostat so nodes repopulate without waiting for the next
  revision change.
- **Why this helps Ecobee:** Under healthy polling, `/thermostatSummary`
  volume is unchanged, but each follow-on `GET /1/thermostat` for a
  changed thermostat is a smaller payload when weather is off fleet-wide.
  That reduces bytes moved per install per long poll, lowers JSON parse
  cost on both sides, and aligns default behavior with users who never
  used weather in automation—while keeping an explicit opt-in for those
  who do.

## Expected impact on Ecobee API traffic

Under normal operation (everything healthy, N thermostats, longPoll =
3 minutes):

- `/thermostatSummary`: 1 GET per 3 minutes (unchanged - this is the
  intended cadence).
- `/thermostat`: 0 to N GETs per 3 minutes, only for thermostats whose
  `thermostatRev` / `runtimeRev` / etc. actually changed.
- `/token` refresh: as needed, capped at most once per long poll.

Under abnormal conditions (5xx storm, rate-limit window, expired
refresh token, dead network), the new bounds are:

| Scenario | Before | After |
|---|---|---|
| Single GET hits a 5xx | up to 31 attempts over many minutes | up to 4 attempts |
| Single POST hits a 5xx | up to 31 attempts (writes resent) | exactly 1 attempt |
| Server returns 429 | ignored, traffic continues | full plugin pause for `Retry-After` |
| Recovery discover loop | 2 x summary + N x program per cycle | 1 x summary, 0 x program (cached) |
| Repeated discover failures | every 3 minutes | 3, 9, 27, ... minutes |
| User mashes POLL button | no throttle | once per 60s |
| PIN auth screen left open | every short poll | at the interval Ecobee specified |
| Failed refresh storm | refresh on every API call | cooldown + once per longPoll |
| Polyglot `longPoll` at 60s (example) | ~60 summary GETs/hour/install | clamped to ~20/hour at 180s minimum |

We expect this to take the plugin from "occasionally bursting tens of
requests under failure" back to its design point of a small, predictable
number of requests per 3-minute window.

### Illustrative fleet scale (~200 installs, assume 1 thermostat each)

The following numbers are **order-of-magnitude illustrations**, not a
measurement from Ecobee's logs. They assume a **3-minute** (180 second)
`longPoll` interval (**20** cycles per hour per install), which is now
**enforced as a minimum** in code (see fix L); previously, operators could
set `longPoll` lower and multiply summary traffic proportionally. They
also assume **one thermostat per install** (some sites have more;
multi-thermostat sites scale the per-install numbers roughly linearly
with N for the parts of the plugin that iterate thermostats).

**Operator short `longPoll` (fix L) — substantial fleet impact:** The
**4,000** summary GETs/hour figure below assumes **every** install polls at
most once per **180** seconds. Before fix **L**, that assumption did **not**
hold: Polyglot allowed any `longPoll` value, and summary traffic scaled
approximately as **`3600 / longPoll` GETs per install per hour** for the
steady path. A single install at **60** seconds therefore issued about
**three times** as many summary calls as one at **180** seconds; at **30**
seconds, about **six times**. That is **linear** in the number of affected
customers, not a rare edge case: if **20** installs out of **200** (10%)
had been set to **60** seconds while the rest were at **180**, those
twenty would each do **60** summaries/hour instead of **20** — **40** extra
per install per hour, or **20 × 40 = 800** extra summary GETs/hour fleet-
wide on top of the **3,600** from the other **180** installs (i.e. roughly
**20%** more aggregate summary traffic than a uniform 180-second fleet). If **all** **200** installs had
run at **60** seconds, steady summary traffic would have been on the order
of **200 × 60 = 12,000** GETs/hour versus **~4,000** at the enforced
minimum — a **3×** fleet-wide multiplier **before** counting any retries,
recovery duplication, or detail GETs. For Ecobee, that means
**misconfigured or over-aggressive `longPoll` could have been a major
contributor to elevated polling for the subset of API keys tied to those
operators**, independent of bugs elsewhere. Fix **L** caps that per-install
cadence so this class of inflation cannot recur.

**Steady state, healthy (no recovery, no PIN, no outages):** At the
**enforced minimum** long poll of **180** seconds, the fleet issues roughly
**one** `GET /1/thermostatSummary` per install per long poll. For **200**
installs that is about **4,000 summary GETs per hour** (about **96,000 per
day**). That headline rate is what we target **after** fix **L**; prior to
it, the same nominal “200 install” fleet could sit materially **above** that
if many operators used shorter intervals, as quantified in the previous
paragraph. Separately from request **count**, routine detail refreshes benefit from
**payload size**: `GET /1/thermostat` uses a trimmed selection
(`getThermostatRuntime`) instead of all 13 include flags, and **fix M**
omits the `weather` section entirely unless the operator has enabled
Weather (GV9) for that thermostat. That further reduces bytes per
`thermostat` GET for most installs after upgrade, without increasing
request count.

**Recovery / discover path (where request count actually drops):** On
the old code path, a single `longPoll` while `discover_st` was false
could issue **two** summary calls in one cycle (discover + immediate
`updateThermostats`), plus **one** `GET /1/thermostat?includeProgram=true`
per thermostat on every discover for `check_profile`. With N=1 that is
**at least three** Ecobee GETs per 3-minute cycle during recovery. After
these fixes, the same cycle issues **one** summary, **zero** program
fetches when the ISY profile is already cached, and **skips** the second
summary in that cycle. That is roughly **a two-thirds reduction** in
GET count for that specific recovery scenario (3 → 1), per affected
install, per cycle. If **10** installs were stuck in that recovery mode
for **one hour**, a rough order of magnitude is:

- Before: ~10 installs × 20 cycles/h × ~3 GETs ≈ **600** GETs/hour
  attributable to that pattern (plus any detail refreshes).
- After: ~10 × 20 × ~1 GET ≈ **200** GETs/hour for the same pattern.

Multi-thermostat homes increase the old `check_profile` cost roughly by
**N** program fetches per discover; the new lazy profile removes that
entire class of traffic whenever the thermostat set and cached profile
metadata are unchanged.

**Correlated infrastructure failure (where amplification was worst):**
If Ecobee (or the path to Ecobee) returns **HTTP 5xx** on summary for a
large share of the fleet at once, the old HTTP layer could issue up to
**31** attempts per logical GET per install; the new layer caps that at
**4**. Across **200** installs polling in the same window, that is a
theoretical worst-case drop from on the order of **6,200** HTTP attempts
down to **800** for that single logical poll wave (about **87% fewer**
HTTP attempts in that scenario). In practice the reduction depends on
how many installs hit the failure at the same time and how long the
outage lasts; the point is that the **upper bound** on burstiness per
install dropped by an order of magnitude.

**PIN authorization and `/token`:** When the plugin ignored Ecobee's
`interval` or reacted poorly to `slow_down`, a single user leaving the
PIN screen open could drive **dozens** of `/token` calls per hour from
one install. Honoring `interval` and backing off on `slow_down` caps
that traffic to roughly **once per Ecobee-specified interval** (often on
the order of tens of seconds to a few minutes), which is typically on
the order of **3× to 10× fewer** `/token` attempts during a typical
10-minute authorization window when the previous behavior was polling
too aggressively.

**Bottom line for Ecobee:** For a **200-install** fleet, **aggregate**
summary traffic was sensitive both to **bugs** (retries, duplicate
summary on recovery, and so on) and to **operator configuration**: a
subset of installs with `longPoll` well below **180** seconds could have
raised fleet-wide `/thermostatSummary` volume by **tens of percent up to a
small integer multiple** without any outage, as in the fix **L** paragraph
above. The largest **spiky** reductions still apply to **failure,
recovery, and auth** paths where the old code multiplied or repeated
requests. Fix **L** aligns the **steady** per-install summary ceiling with
Ecobee's documented guidance (**at least** **180** seconds between polls);
the other fixes prevent that baseline from turning into **multiplicative**
load under stress.

## How Ecobee can verify

- The new `longPoll: ecobee request counts (total=...)` log line is
  emitted once per long-poll cycle in the plugin's log. This is the
  authoritative count of requests issued by the plugin per cycle, by
  endpoint bucket and HTTP method.
- All write operations (`POST /1/thermostat`) are now performed exactly
  once per logical user action. They are no longer auto-retried by the
  HTTP layer.
- All requests issued during an active rate-limit window are short-
  circuited locally and emit a `Skipping <METHOD> <path>: rate-limited
  for Ns more seconds` warning, so any unexpected post-429 traffic
  would be visible in the plugin's own logs as well as on the API
  gateway.

## Next steps and ongoing commitments

- We will monitor the new request-count logs across the user base for
  any cycles that exceed the expected volume, and treat any such cycle
  as a defect.
- If Ecobee can share approximate per-API-key request rate ceilings, we
  will surface them as configurable parameters in the plugin and add
  client-side rate limiting matched to those ceilings.
- We will continue to investigate any specific API key or installation
  ID that Ecobee can identify as a heavy emitter so we can determine
  whether it is the issue described above (now fixed) or a separate
  problem.

If there is a way to coordinate going forward (e.g. a developer contact
or notification channel for partner integrations), we would welcome
that. The plugin is open-source and we are happy to make any further
adjustments needed to stay within Ecobee's expectations.

## Contact

- Plugin maintainers / project: https://github.com/UniversalDevicesInc-PG3/udi-poly-ecobee
- Issue tracker: https://github.com/UniversalDevicesInc-PG3/udi-poly-ecobee/issues
- User support forum: https://forum.universal-devices.com/forum/322-ecobee/
