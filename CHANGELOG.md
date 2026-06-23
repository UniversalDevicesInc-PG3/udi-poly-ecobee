# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.1.7] - 2026-06-23

### Fixed

- **HomeKit GV3 (Climate Type) commands:** comforts that share the HAP **Temp** slot (or collide with **Away** on the wire) now write that comfort’s heat/cool setpoints before ``VENDOR_ECOBEE_SET_HOLD_SCHEDULE``, using learned signatures, vendor snapshot targets (home/sleep/away), and configured-comfort mapping (HK slot **Smart1** → first extra comfort such as **Vacation**). Commands abort when setpoints are not known yet instead of reporting success with no change on the stat.

### Added

- **HomeKit startup comfort cache:** after the hub connects (and when the device list is processed), each HomeKit thermostat automatically runs a debounced hub snapshot (same as **QUERY**) to cache vendor **Home / Sleep / Away** target setpoints and to learn extra-comfort signatures when the stat is on them at refresh time.
- **Docs:** [docs/HOMEKIT_GV3_SETPOINTS.md](docs/HOMEKIT_GV3_SETPOINTS.md) — HomeKit **Climate Type** status (4.1.6), command setpoints (4.1.7), and startup cache behavior. **README.md** and **CONFIG.md** updated to use IoX labels from `en_us.txt` (not driver IDs).

## [4.1.6] - 2026-06-23

### Fixed

- **HomeKit GV3 (Climate Type) status:** when Ecobee reports HAP comfort byte **3** (Temp) for comforts beyond Home / Sleep / Away (e.g. **Vacation** and **Away Extended**), **GV3** is now resolved using heat/cool setpoint signatures against the thermostat’s configured comfort list instead of always reporting **Smart1** (index 3).

## [4.1.5] - 2026-06-23

### Fixed

- **HomeKit profile / NLS:** restore missing `profile_writer` imports in the HomeKit backend so hub device discovery writes `profile/nls/en_us.txt`, per-thermostat `custom.xml` nodedef/editor snippets, and calls **Load Profile** instead of failing with `NameError: profile_needs_update`.

## [4.1.4] - 2026-06-23

### Added

- **Per-thermostat comfort lists (cloud):** **GV3** (Climate Type) commands list only comforts configured on each thermostat (from the Ecobee API), with **custom names** from your program (e.g. “Workshop” instead of **Smart2**).
- **Climate program labels (Custom Typed Data):** nested **Climate program labels** — one row per thermostat (`thermostat_id`, display **name**, optional HomeKit **device_id**) with a nested **climates** list (`climateRef` + display **name**). Rows are **auto-created** on **DISCOVER** (cloud) or when HomeKit hub devices are listed; cloud fills names from the Ecobee API when still at defaults.

### Changed

- **HomeKit GV3** (Climate Type) **status:** comfort **status** uses the full **CTA_*** label range (custom names for all indices). **GV3** (Climate Type) **commands** stay on **CT_HK_*** (Home / Sleep / Away / Temp only — Ecobee HomeKit vendor limit).
- **Cloud GV3** (Climate Type) **command editor:** per-thermostat **CT_*** subset (configured comforts only) instead of a fixed catalog slice.
- **Profile (IoX nodedef):** version **4.1.9** — climate label and editor updates above. Restart the Node Server and **Load Profile** after upgrade.

## [4.1.3] - 2026-06-19

### Added

- **HomeKit resume schedule:** **CLISMD** (Schedule Mode) = **Running** (0) sends the Ecobee vendor **clear hold** sequence on the hub (`VENDOR_ECOBEE_CLEAR_HOLD`), then schedules a debounced thermostat snapshot refresh so IoX setpoints and hold state match the stat after the hold clears.
- **HomeKit hold / comfort UX:** HomeKit thermostats expose **GV3** (Climate Type) and **CLISMD** (Schedule Mode) as **separate** IoX controls (not a coupled comfort + HoldType multi-select like cloud). Change comfort alone, hold type alone, or both in sequence.

### Changed

- **HomeKit `GV3` (Climate Type) profile:** status and command both use **`CT_HK_*`** (away / home / sleep / smart1 only). Comfort-only writes default to **Hold Next** (**CLISMD** (Schedule Mode) = 1) in the backend when no hold type is specified.
- **Cloud `GV3` (Climate Type) holds:** optional **HoldType** on climate commands defaults to **Hold Next** when omitted, so the admin UI no longer requires setting comfort and hold type together.
- **User setup docs:** restructured **CONFIG.md** as the primary HomeKit setup guide with step-by-step quick start, hub/Ecobee defaults checklist, verify/troubleshooting sections, and **Reference: HomeKit behavior vs cloud** (moved from README). **README.md** trimmed to help links and CONFIG pointers.
- **Profile (IoX nodedef):** version **4.1.7** — HomeKit thermostat template updates above; **4.1.5** fixed non-ASCII punctuation in generated editor XML. After upgrade, restart the Node Server and **Load Profile** if release notes mention **Profile Change**.

### Fixed

- **HomeKit clear-hold UI refresh:** immediately after **CLISMD** (Schedule Mode) = **Running**, a hub snapshot could still report stale hold setpoints until **QUERY**; the debounced refresh after clear-hold updates drivers without a manual query.

## [4.1.2] - 2026-05-25

### Fixed

- **HomeKit thermostat heating setpoints (Fahrenheit):** heat writes now use the **lowest** compatible **0.1 C** bin for Ecobee display parity, which avoids the remaining **72 F -> 73 F** case on the physical thermostat.
- **HomeKit hub reconnect after reboot:** the Ecobee MQTT client now documents the **hello** retry schedule and keeps retrying until the hub acknowledges, so startup races with **udi-poly-homekit** no longer leave the backend disconnected after an eisy reboot.
- **PG3 notices:** Ecobee notice helpers now prepend a local timestamp across controller, cloud, and HomeKit notice paths so warnings in the Polyglot UI include the time they were generated.

## [4.1.1] - 2026-05-11

### Fixed

- **HomeKit CT_HK editor (per thermostat):** generated **subset** was **0-11_hk_hi** because **tstatcnt** was substituted inside **tstatcnt_hk_hi**. **profile_writer** now replaces **tstatcnt_hk_hi** before **tstatcnt**, so the hold command editor is **subset="0-3"** as intended.

## [4.1.0] - 2026-05-10

### Changed

- **HomeKit thermostat profile:** **GV3** (Climate Type) **commands** use editor **CT_HK_\<tstat\>** with subset **0–3** (IoX **away / home / sleep / smart1**) so the IoX UI cannot select hold values the Ecobee HomeKit vendor characteristic rejects. **GV3** (Climate Type) **status** keeps the full **CTA_\<tstat\>** range for label resolution. **README** / **CONFIG.md** document the four hold slots vs the Ecobee app.

### Fixed

- **HomeKit GV3** (Climate Type) **writes:** map remaining **climateList** indices to valid **SET_HOLD** bytes before sending to the hub (avoids HAP **-70410** for e.g. vacation). See **`homekit_client/hap_apply.py`** ``gv3_to_ecobee_set_hold_schedule``.

## [4.0.9] - 2026-05-10

### Fixed

- **Cloud OAuth:** Custom Param **`api_key`** is honored when Polyglot OAuth is enabled: a non-empty value overrides injected **`serverdata`** / nsdata keys for Ecobee **`client_id`** (authorize URL, token exchange, refresh). **`CONFIG.md`** documents Polyglot redirect URI requirements for personal developer keys.

## [4.0.8] - 2026-05-09

### Fixed

- **HomeKit thermostat (°F):** HAP writes use **0.1 °C** steps; naive Fahrenheit→Celsius rounding can land just **above** the target whole °F on the wire (e.g. **75 °F → 23.9 °C → 75.02 °F**), and Ecobee’s display then shows **+1 °F**. **`iox_temp_to_hap_celsius`** now accepts **`fahrenheit_wire_bias`**: **low** for cooling / **CLISPC** (Cool Setpoint; lowest compatible 0.1 °C bin per **`toF`**) and **high** for heating / **CLISPH** (Heat Setpoint).

## [4.0.7] - 2026-05-09

### Fixed

- **HomeKit thermostat (auto):** use **3 °F** (and **5/3 °C** for Celsius nodedefs) minimum heat/cool span when co-writing HAP thresholds so Ecobee’s compressor minimum delta is satisfied on the wire. Previously a **1 °F** slack let HomeKit writes succeed while the stat raised the cooling setpoint (e.g. **72 → 73** when heat was **70**).

## [4.0.6] - 2026-05-08

### Fixed

- **Profile NLS (Profile Change):** add missing remote-sensor driver names for the `140ES` editor — **CLIHUM** (Humidity), **BATLVL** (`Battery Level`), and **BATLOW** (`Battery Low`). The `EcobeeSensor*` nodedefs publish all three but the IoX UI was rendering them without labels.

## [4.0.5] - 2026-05-08

### Fixed

- **HomeKit sensors:** when a remote sensor already exists in PG3's node database, re-send its `addnode` once per plugin process so IoX can recover if it missed or dropped the original add. This helps repair installs where `rs_*` nodes are present in Polyglot but absent from IoX.

## [4.0.4] - 2026-05-08

### Fixed

- **Profile NLS (Profile Change):** add missing controller names for **GV4** (HomeKit WebSocket) / **GV5** (HomeKit MQTT) HomeKit transport status drivers and **HKTR** enum labels (`Not Selected` / `Not Connected` / `Connected`) used by the `hktr` editor.

## [4.0.3] - 2026-05-08

### Changed

- **HomeKit transport default:** new installs now seed **`hk_transport`** to **`mqtt`** (was `websocket`). MQTT is the preferred path because the broker survives plugin restarts and gives lower-latency events; **WebSocket** remains fully supported as a fallback when MQTT is not available. Existing installs are unaffected — their stored value is preserved. Set **`hk_transport`** to **`websocket`** in Custom Params to keep using the WebSocket transport. **CONFIG.md** and **README.md** updated to document MQTT as the recommended transport.
- **Install:** `install.sh` now passes `pip3 install --no-warn-script-location` to suppress noisy "script is installed in `.local/bin` ... not on PATH" warnings on PG3 hosts where the per-NS `.local/bin` is intentionally off PATH.

## [4.0.2] - 2026-05-08

### Changed

- **HomeKit backend:** `dry_run` now defaults to **`false`** so thermostat commands are sent to the HomeKit hub by default. Set Custom Param **`dry_run`** to **`true`** to restore log-only command behavior.

### Fixed

- **HomeKit backend:** hub **`command`** RPC failures (for example HAP **-70410** invalid value) now raise the same PG3 **`homekit_hub_rpc_error`** notice as on udi-poly-homekit, with **`command`**, **`device_id`**, transport (**MQTT `client_slug`** or WebSocket), **`characteristic`**, and value context; hub **`command_sync`** timeouts are noticed as well.
- **HomeKit thermostat / HAP:** mode-aware setpoint and threshold writes, heat/cool span handling, and IoX temperature rounding in **`hap_apply`** to avoid invalid HAP writes.

## [4.0.1] - 2026-05-03

### Changed

- **MQTT default `hk_mqtt_client_slug`:** defaults to this plugin’s PG3 id **`udi-poly-ecobee`** (`DEFAULT_HK_MQTT_CLIENT_SLUG` in `params_flat.py`); override when multiple clients share one broker and need distinct topic slugs.

### Fixed

- **Controller** **GV4** (HomeKit WebSocket) / **GV5** (HomeKit MQTT) (HomeKit transport status): merge Polyglot `CONFIG` driver rows into the full **`ECO_CTR`** template from **`const.driversMap`** instead of replacing in-memory drivers with only PG3’s subset. Prevents **`setDriver('GV4'|'GV5')`** *Invalid driver* when IoX has not yet persisted new hub-transport status drivers, so WebSocket/MQTT tri-state updates correctly.

## [4.0.0] - 2026-05-02

Major release: **HomeKit hub integration** with [udi-poly-homekit](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit) is the supported path for new installs; Ecobee cloud/API remains for legacy deployments only.

### Added

- **HomeKit hub MQTT client** — optional Custom Param **`hk_transport`** = **`mqtt`** with **`hk_mqtt_*`** broker and topic slugs (**`HubMqttClient`**, **aiomqtt**); same JSON protocol as WebSocket when udi-poly-homekit has **`mqtt_enable`** (see udi-poly-homekit **`PROTOCOL.md`**).
- **HomeKit backend** — WebSocket client to the udi-poly-homekit hub (hello `ack` pairing list, multiplexed `command` / `snapshot` / `get` RPC, hub `warnings` mirrored to PG3 Notices).
- **PG3 Notice `homekit_hub_unreachable`** — when the hub WebSocket fails (connection or hello), with guidance to install and configure udi-poly-homekit and set `hk_ws_url` / `hk_ws_token`.
- **`default_backend_for_new_param_seed`** — when Custom Param `backend` is missing, seed **`homekit`** for a fresh nodeserver and **`cloud`** when OAuth, non-empty `api_key`, Ecobee `tokenData` / PIN in customdata, or existing non-controller nodes indicate a legacy cloud install.

### Changed

- **Documentation (`README.md`, `CONFIG.md`)** — install/configure udi-poly-homekit first; Ecobee/UDI shared cloud API access is discontinued; cloud only viable with a personal developer key obtained before Ecobee disabled UDI keys.
- **WebSocket client** — pairing list always taken from hello `ack` `devices[]` (including empty); clear cached devices on new connection; optional `on_transport_error` callback; no reliance on an automatic second `list_devices` frame from the hub.

### Fixed

- Avoid leaving **stale hub device rows** when hello `ack` returns an empty `devices[]` (reconnect / unpair cases).

---

## Earlier releases

The following entries were migrated from `README.md` (original wording and dates preserved).

### 3.1.5 — 11/11/2023
  - Fix: [Setting Climate Type doesn't set proper hold mode](https://github.com/UniversalDevicesInc-PG3/udi-poly-ecobee/issues/10)
### 3.1.4 — 08/15/2023
  - Properly set version
### 3.1.3 — 08/12/2023
  - Add ability to see and control ECO+
  - Add node names so they show up in PG3 UI
### 3.1.2 — 07/24/2022
  - Fix bug caused by changes in previous release.
### 3.1.1 — 07/24/2022
  - Release: [Feature Request: ecobee Premium air quality sensor](https://github.com/UniversalDevicesInc-PG3/udi-poly-ecobee/issues/4)
### 3.1.0 — 07/23/2022
  - Beta release of supporting New thermostats with Air Quality
### 3.0.2 — 03/08/2022
  - Call interface stop when stopping
### 3.0.1 — 03/02/2022
  - Fix bug caused by change in PG3 interface sending oauth data to nsdata handler.
### 3.0.0 — Jimbo 01/22/2022
  - Initial PG3 release, not tested from store yet...
### 2.3.0 — JimBo 01/14/2022
  - Pull in PR from @firstone: Adding set (de)humidity point commands
### 2.2.3 — JimBo 01/01/2021
  - Fix for Celcius
### 2.2.2 — JimBo 12/31/2020
  - Different workaround for [Crash getting date/time](https://github.com/Einstein42/udi-ecobee-poly/issues/65)
    - This is only an issue on Polyglot Cloud
### 2.2.1 — JimBo 12/27/2020
  - Another fix for [Add support for dryContact sensors](https://github.com/Einstein42/udi-ecobee-poly/issues/24)
### 2.2.0 — JimBo 12/22/2020
  - Change Authorization to use use new Ecobee UDI Authorization, see __IMPORTANT__ message above!
    - PGC now uses OAuth so no PIN required
    - Hopefully this will resolve users having to re-authorize, but only time will tell for sure.
    - Should fix [The client was authorized, but Ecobee returned an invalid_client error](https://github.com/Einstein42/udi-ecobee-poly/issues/60)
  - Add traceback for [ClimateType smart14 Error](https://github.com/Einstein42/udi-ecobee-poly/issues/63) to help debug the issue
    - Also, will only print the error once per run instead of constantly
  - Fix [Crash getting date/time](https://github.com/Einstein42/udi-ecobee-poly/issues/65)
  - Initial support for [Add support for dryContact sensors](https://github.com/Einstein42/udi-ecobee-poly/issues/24)
  - For [ClimateType - smart14](https://github.com/Einstein42/udi-ecobee-poly/issues/63) Only print error once, actually bug will be fixed in the future.
### 2.1.34 — jimBo 11/19/2020
  - Stop longPoll from running if node start has not completed.  This is a rare case when startup takes a long time due to Polyglot/PBC running very slow
### 2.1.33 — JimBo 11/17/2020
  - Increased DB write/verify timeout from 15seconds to 15minutes since we have seen issue where retrying a write causes issues
  - Also, if we see the DB was written, but the date/time is older than what we wrote, then ignore it.
### 2.1.32 — JimBo 11/14/2020
  - Fix syntax error in last release when token is expired on startup.
### 2.1.31 — JimBo 11/14/2020
  - Don't force user reauthorization when invalid_grant is returned and token has not expired.  This is to hopefully get around the issue where Ecobee servers return invalid_grant when it's really not.  Ecobee support is no longer responding to us for help on this issue.
### 2.1.30 — JimBo 09/13/2020
  - Temporary fix for https://github.com/Einstein42/udi-ecobee-poly/issues/60
    - May have to update after hearing back from Ecobee.
### 2.1.29 — JimBo 09/11/2020
  - Fix bug introduced in previous version that only affects a new install
  - Also fix ecobee login url
### 2.1.28 — JimBo 09/09/2020
  - Change timeout from 60 to 10,61 to see if that stops read timeout issue
  - Also added connect retries
### 2.1.27 — JimBo 09/07/2020
  - More fixes for https://github.com/Einstein42/udi-ecobee-poly/issues/57
    - Clean up DB lock/unlock more
    - Add retry if save custom data doesn't seem to happen
    - Set Auth driver to False to trigger programs
### 2.1.26 — JimBo 09/06/2020
  - Enhance Fix for https://github.com/Einstein42/udi-ecobee-poly/issues/57
    - Add timeout in saveCustomDataWait method
### 2.1.25 — JimBo 09/04/2020
  - Enhance Fix for https://github.com/Einstein42/udi-ecobee-poly/issues/57
    - To workaround possible DB write order issue, do not continue until DB data is confirmed to be saved when locking/unlocking
### 2.1.24 — JimBo 08/30/2020
  - Fix for https://github.com/Einstein42/udi-ecobee-poly/issues/57
### 2.1.23 — JImBo 06/06/2020
  - Fix to not set auth status False when starting refresh
### 2.1.22 — JimBo 06/05/2020
  - Refresh token before it expires,
  - Don't save tokenData in customData because it will increase PGC cost.
### 2.1.21 — JimBo 06/04/2020
  - Fix crash for another authentication issue.
### 2.1.20 — JimBo 06/03/2020
  - Print msg to log when requesting a pin in case it doesn't show up in Polyglot UI
  - Print customData on restart
  - Store current nodeserver version in customData for reference
  - Increase waitingOnPin sleep time to 30 and increment by 30 on each loop up to 180
### 2.1.19 — JimBo 05/26/2020
  - Fix another crash when Ecobee servers are not responding
### 2.1.18 — JimBo 05/07/20202
  - When refresh_token goes missing, force a reAuth.  No idea how that happens, but we can track it now.
### 2.1.17 — JimBo 05/07/2020
  - Keep track of old tokenData when it becomes invalid, along with the reason in the DB.
### 2.1.16 — JimBo 03/17/2020
  - Fix for https://github.com/Einstein42/udi-ecobee-poly/issues/52
### 2.1.15 — JimBo 02/06/2020
  - Add fix for https://github.com/Einstein42/udi-ecobee-poly/issues/51 not fully tested since I can't repeat, but should trap the error.
### 2.1.14 — JimBo 02/02/2020
  - Add Support for auxHeat https://github.com/Einstein42/udi-ecobee-poly/issues/50
  - profile update required, must restart AC after retarting Nodeserver
### 2.1.13 — JimBo 09/09/2019
  - Fix issue with new installs where profile/nls didn't exist on initial start
### 2.1.12 — JimBo 09/08/2019
  - Added simple fix for [ClimateType of 'wakeup' not found, halts further processing](https://github.com/Einstein42/udi-ecobee-poly/issues/46)
  - Proper fix is defered for later [climateList should be pulled from API](https://github.com/Einstein42/udi-ecobee-poly/issues/47)
  - New profile will be generated on restart, make sure to close and re-open admin console
### 2.1.11 — JimBo 06/19/2019
  - Better trapping for expired tokens
### 2.1.10 — JimBo 05/09/2019
  - Ignore socket not closed warnings (hopefully for @larryllix)
### 2.1.9 — JimBo 05/05/2019
  - Fixed backlightSleepIntensity
### 2.1.8 — JimBo 04/23/2019
  - Add backlightSleepIntensity
### 2.1.7 — JimBo 04/22/2019
  - Add Upload Profile to Controller, should never be needed, but just in case.
### 2.1.6 — JimBo
  - [Crash due to bad json returned from Ecobee](https://github.com/Einstein42/udi-ecobee-poly/issues/45)
### 2.1.5 — JimBo
  - [Crash due to bad json returned from Ecobee](https://github.com/Einstein42/udi-ecobee-poly/issues/45)
  - [Not properly recognizing expired token response?](https://github.com/Einstein42/udi-ecobee-poly/issues/44)
  - [Track Vacation along with Smart Home/Away](https://github.com/Einstein42/udi-ecobee-poly/issues/31)
    - Properly support Vacation, SmartAway, SmartHome and DemandResponse Events in 'Climate Type'
  - [Support changing backlightOnIntensity](https://github.com/Einstein42/udi-ecobee-poly/issues/42)
### 2.1.4 — JimBo
  - [Crash due to bad json returned from Ecobee](https://github.com/Einstein42/udi-ecobee-poly/issues/45)
### 2.1.3 — JimBo
  - More fixing flakey Ecobee servers.
### 2.1.2 — JimBo
  - Fix re-authorization, but can not completely verify because Ecobee site is flakey.
### 2.1.1 — JimBo
  - [Add setting to include/exclude weather and forcast](https://github.com/Einstein42/udi-ecobee-poly/issues/40)
### 2.1.0 — JimBo
  - Changed communcation with Ecobee to use sessions.  This has fixed the hanging issue and made network connections to Ecobee servers more robust.
  - Added logger level to controller which defaults to warning, however polyglot doesn't udpate the DB so it's not changeable from the ISY until this magically happens, not sure when.
### 2.0.39 — JimBo
  - Add more debugging to see where hang is happening
### 2.0.38 — JimBo
  - Fixed typo when initial discover fails.
### 2.0.37 — JimBo
  - Trap any error in discover in case Ecobee servers are not responding when starting up, and we hit an error that is not being trapped.
### 2.0.36 — JimBo
  - [Trap: ConnectionResetError: [Errno 104] Connection reset by peer](https://github.com/Einstein42/udi-ecobee-poly/issues/39)
### 2.0.35 — JimBo
  - Fix initialization of "Ecobee Connection Status".  Try to set it to False on exit, but doesn't work due to polyglot issue.
  - Add debug in getThermostatSelection to see where it's hanging
### 2.0.34 — JimBo
  - [AttributeError: 'Controller' object has no attribute 'revData'](https://github.com/Einstein42/udi-ecobee-poly/issues/36)
  - Send Heartbeat on startup
### 2.0.33 — JimBo
  - Fix another crash from Ecobee server returning bad json data.
### 2.0.32 — JimBo
  - [Fix issue with unknown remote sensor temperature](https://github.com/Einstein42/udi-ecobee-poly/issues/35)
  - [AttributeError: 'Controller' object has no attribute 'revData'](https://github.com/Einstein42/udi-ecobee-poly/issues/36)
  - [Thermostat connected not updated when service is down](https://github.com/Einstein42/udi-ecobee-poly/issues/37)
### 2.0.31 — JimBo
  - Add Poll on controller to grab all current settings, and query to just report the currently known drivers values to the isy.
  - Fix another issue found when Ecobee servers are not responding.
### 2.0.30 — JimBo
  - Fix for Hold Type names in Climate Control program action.  Although, they don't actually work yet in Polyglot, so you have to set Hold Type in another Action.
### 2.0.29 — JimBo
  - Added back fix for checking sensors from 2.0.26 that git merge decided to get rid of.
### 2.0.28 — JimBo
  - Added vacation mode tracking as a Climate Type for [Track Vacation along with Smart Home/Away](https://github.com/Einstein42/udi-ecobee-poly/issues/31)
### 2.0.27 — JimBo
  - [Issue with custom climate names](https://github.com/Einstein42/udi-ecobee-poly/issues/32)
### 2.0.26 — JimBo
  - Changed logic for adding sensors and checking sensor updates, so we know if there is a problem with sensor not found
### 2.0.25 — JimBo
  - Build the profile before adding any nodes, shouldn't make any difference, but is just the right thing to do.
### 2.0.24 — JimBo
  - Set Fan State on when manually turned on and off when Climate Type = Resume, will get updated on next long poll if not the actual status.
### 2.0.23 — JimBo
  - [Add heartbeat](https://github.com/Einstein42/udi-ecobee-poly/issues/29)
    - See https://forum.universal-devices.com/topic/25016-polyglot-nodeserver-monitoring/ for info on how to use it.
### 2.0.22 — JimBo
  - [Ecobee server issues caused nodeserver to hang](https://github.com/Einstein42/udi-ecobee-poly/issues/28)
    - More trapping
  - [Set Fan driver on/off based on heat setting when fanControlRequired setting](https://github.com/Einstein42/udi-ecobee-poly/issues/25)
    - Should actually work this time.
### 2.0.21 — JimBo
  - [Ecobee server issues caused nodeserver to hang](https://github.com/Einstein42/udi-ecobee-poly/issues/28)
    - Not a sure fix, but should improve stablity.
  - [Add control of fan on/auto state](https://github.com/Einstein42/udi-ecobee-poly/issues/23)
  - [Set Fan driver on/off based on heat setting when fanControlRequired setting](https://github.com/Einstein42/udi-ecobee-poly/issues/25)
### 2.0.20 — JimBo
  - Fix for old Ecobee's that don't have the same sensor data.
### 2.0.19 — JimBo
  - Fix bug when installing
### 2.0.18 — JimBo
  - Support sensors with or without Humidity
  - Fix Sensor update to not report drivers on every check.  Will reduce a lot of updates to ISY.
### 2.0.17 — JimBo
  - Add Connected to Thermostat, set to False when Ecobee servers can't see the Thermostat
  - Fix crash where Sensor temp was 'unknown' when it hasn't reported yet
  - Fix bug where profile is not rebuilt when a climate name is Changed
  - If an invalid climate type is somehow selected, meaning it isn't named in the app, then smart<n> is shown.  I can't figure out how this can happen, but seems possible.
### 2.0.16 — JimBo
  - Fix issues with custom climate types for mutliple thermostats
### 2.0.15 — JimBo
  - [Add support for custom named climate type's](https://github.com/Einstein42/udi-ecobee-poly/issues/1)
    - With this change the custom Climate Types (Comfort Settings) names you have created in the thermostat will show up on the ISY, but this means that during discover it will build custom profiles that will be loaded and will require the admin console to be closed if it's open.
### 2.0.14 — JimBo
  - [When I select hold-indefinite on schedule mode, it sets the heat setpoint to 26 degrees C and holds it there indefinitely.](https://github.com/Einstein42/udi-ecobee-poly/issues/16)
  - [Temperature is being displayed in the console in deg F (even though it says deg C)](https://github.com/Einstein42/udi-ecobee-poly/issues/17)
  - [The Occupancy variable does change for the the satellite sensors, but not for the thermostats itself.](https://github.com/Einstein42/udi-ecobee-poly/issues/18)
    - Also added Humidity support to sensors, which will show up after restarting the nodeserver and restarting admin console.
### 2.0.13 — JimBo
  - Reorganize hold functions for changing setpoints, climate type, ...
  - Fix Illegal node names
  - More trapping of bad return data from Ecobee servers
  - More debugging info to find issues
### 2.0.12 — JimBo
  - Fix for polling not working
  - Many changes to how hold's are handled, should be more reliable
### 2.0.11 — JimBo
  - Thermostat address starts with 't', existing users will need to delete the old node after fixing their programs to reference the new one.
### 2.0.10 — JimBo
  - Changed setpoint up/down (BRT/DIM) to change as a hold nextTransition instead of changing the program setpoint
  - Better trapping of issues when Ecobee servers are not responding
### 2.0.9 — JimBo
  - Should now be properly tracking all status when going in and out of holds.
### 2.0.8 — JimBo
  - Shortend names of Sensor, Weather, and Forcast nodes.
    - Existing users will have to delete the current nodes in the Polyglot UI to get the new names, or just rename them yourself.
### 2.0.7 — JimBo
  - [Changing setpoint when program running changes the actual "comfort setting"](https://github.com/Einstein42/udi-ecobee-poly/issues/6)
    - See Notes above in Settings for "Schedule Mode"
  - [Schedule Mode crash ValueError: invalid literal for int() with base 10](https://github.com/Einstein42/udi-ecobee-poly/issues/10)
  - [Setting 'Climate Type' sets hold as indefinite, should it use nextTransition?](https://github.com/Einstein42/udi-ecobee-poly/issues/9)
    - It will now use the current set "Schedule Mode"
  - [Move creating Thermostat child nodes into Thermostat](https://github.com/Einstein42/udi-ecobee-poly/issues/7)
  - [Sensor ID's are not unique when you have multiple thermostats](https://github.com/Einstein42/udi-ecobee-poly/issues/2)
    - The new sensor nodes will be created when the nodeserver is restarted.
    - IMPORTANT: Please delete the nodes from within the Polyglot UI after changing any programs that may reference the old ones.
### 2.0.6 — JimBo
  - [Fix lookup for setting Mode](https://github.com/Einstein42/udi-ecobee-poly/issues/4)
  - [Fix crash when changing schedule mode](https://github.com/Einstein42/udi-ecobee-poly/issues/5)
  - Fix "Climate Type" initialization when there is a manual change
  - Automatically upload new profile when it is out of date.
  - Change current temp for F to include one signficant digit, since that's what is sent.
