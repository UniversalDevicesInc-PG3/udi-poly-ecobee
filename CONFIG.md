# Ecobee Node Server — configuration

**Start here.** This file is the main setup guide for new **HomeKit hub** installations.

---

## Prerequisites

1. **Install and pair on [udi-poly-homekit](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit) first** — follow its [CONFIG.md — Ecobee + IoX quick start](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit/blob/master/CONFIG.md#ecobee--iox-quick-start). Your Ecobee must be paired on that hub and **not** left paired only to Apple Home.
2. This Node Server does **not** replace the HomeKit hub; it connects to it over **MQTT** (default) or **WebSocket**.

**Ecobee cloud (REST API):** Ecobee has cut off UDI / Polyglot Cloud OAuth for this integration. **New setups should use HomeKit hub mode.** Cloud mode only remains viable with a **personal Ecobee developer `api_key`** you registered before shared keys stopped working — see [Cloud backend (legacy)](#cloud-backend-legacy) below.

---

## Ecobee quick start (HomeKit)

1. Complete [HomeKit hub pairing](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit/blob/master/CONFIG.md#ecobee--iox-quick-start) first. Confirm hub **GV0** = `1` and **GV1** = `2` (MQTT connected).
2. Add **Ecobee** from the PG3 store and start the Node Server.
3. Open **Configuration** → **Custom Configuration Parameters**.
4. On a **fresh install** you should see:
   - **`backend`** = `homekit` (seeded automatically)
   - **`hk_transport`** = `mqtt` (preferred default)
5. Confirm these match your HomeKit hub (see [Defaults checklist](#defaults-checklist) below). On a typical Polisy/eISY install, **do not change them** — just **Save**.
6. On the **Ecobee Controller** node, within about a minute:
   - **Ecobee Connection Status** = **true** when hello to the hub succeeded
   - **HomeKit MQTT** = **Connected** when using MQTT
7. Thermostat nodes (`t…`) and remote sensor nodes (`rs…`) should appear. If not, see [Verify success](#verify-success) and [Troubleshooting](#troubleshooting).

**`backend` seeding:** If **`backend`** is missing, the plugin sets it once: **`homekit`** for a brand-new NS; **`cloud`** only when OAuth, **`api_key`**, saved Ecobee tokens/PIN, or existing thermostat nodes indicate a legacy install. A value already stored in PG3 is never overwritten.

---

## Defaults checklist

On a typical single-hub Polisy/eISY install, these values should already match. Change only if you use a non-default broker or multiple hubs.

| HomeKit hub param | Ecobee param | Typical value |
|-------------------|--------------|---------------|
| `mqtt_enable` = `true` | `hk_transport` = `mqtt` | MQTT enabled on both sides |
| `mqtt_host` | `hk_mqtt_host` | `localhost` |
| `mqtt_port` | `hk_mqtt_port` | `1884` |
| `mqtt_hub_slug` | `hk_mqtt_hub_slug` | `default` |

**WebSocket fallback:** set **`hk_transport`** to **`websocket`**, **`hk_ws_url`** to e.g. `ws://127.0.0.1:8163`, and optionally **`hk_ws_token`** if the hub requires it. Enable MQTT on the hub is still recommended for production.

Saving Custom Params after changing **`hk_transport`** or any **`hk_ws_*` / `hk_mqtt_*`** field restarts the hub client immediately (no full Node Server restart required).

---

## Verify success

On the **Ecobee Controller** node (HomeKit mode):

| IoX status | Good value | Meaning |
|------------|------------|---------|
| **Ecobee Connection Status** | `true` | Active transport completed hello to the hub. |
| **HomeKit MQTT** | `Connected` | MQTT connected (when **`hk_transport`** is `mqtt`). |
| **HomeKit WebSocket** | `Connected` | WebSocket connected (only when **`hk_transport`** is `websocket`). |
| **Authorized** | reflects hub | Hub reported paired devices. |

**Healthy signs:** thermostat nodes (`t…`) and sensors (`rs…`) in IoX; no persistent **Notices** named **`homekit_hub_unreachable`**, **`homekit_no_thermostat`**, or **`homekit_hub_warnings`**.

**Logs:** `logs/debug.log` records **INFO** when the client starts and when **hello** succeeds; **WARNING** on transport problems.

**Notices:**

- **`homekit_hub_unreachable`** — cannot connect or hello failed; check hub is running and slug/host/port match.
- **`homekit_hub_disconnected`** — session dropped while retrying (deduped in UI about every 45 seconds).
- **`homekit_hub_warnings`** — structured warnings from the hub (see udi-poly-homekit **PROTOCOL.md**).
- **`homekit_no_thermostat`** — hub sent devices but none became a thermostat node (includes JSON snapshot).

---

## Optional settings

- **`use_celsius`**: `auto`, `true`, or `false`. Default `auto`.
- **`dry_run`**: default **`false`**. Set **`true`** to log commands without sending them; Notice **`homekit_dry_run`** reminds you.
- **`hk_mqtt_client_slug`**: default **`udi-poly-ecobee`**. Set a unique value only if multiple Ecobee NS instances share one broker.
- **Custom Typed Params** (address overrides, [climate program labels](#climate-program-labels)): only needed for advanced installs — see [Reference: Typed params](#reference-custom-typed-configuration-parameters).

---

## Troubleshooting

### Ecobee NS starts but no thermostats appear

1. Confirm **udi-poly-homekit** has the Ecobee paired (child node **ST** = paired on the hub).
2. Confirm hub **GV0** = `1` and **GV1** = `2`.
3. Confirm **`hk_mqtt_hub_slug`** matches hub **`mqtt_hub_slug`** (usually both `default`).
4. Check Notice **`homekit_no_thermostat`** and hub **`homekit_hub_warnings`**.

### `homekit_hub_unreachable` after reboot

The Ecobee client retries hello until the hub is up. If it persists more than a few minutes, restart the **HomeKit Hub** Node Server first, then Ecobee. Confirm MQTT broker on port **1884** is available on the Polisy/eISY.

### Wrong backend (`cloud` instead of `homekit`)

If this is a **new** HomeKit install but **`backend`** shows `cloud`, you may be upgrading a legacy NS. Set **`backend`** to **`homekit`** manually and **Save**, or remove and re-add the Node Server on a clean install. See seeding rules under [Ecobee quick start](#ecobee-quick-start-homekit).

### Slug or broker mismatch

**`hk_mqtt_hub_slug`** must exactly match the hub's **`mqtt_hub_slug`**. **`hk_mqtt_host`** / **`hk_mqtt_port`** must reach the same broker the hub uses.

---

## Reference: Custom Configuration Parameters

Flat **Custom Params** (PG3). New installs: keys are seeded at startup so every row appears in the editor.

| Parameter | Required | Description |
| --------- | -------- | ----------- |
| `backend` | No | **`homekit`** or **`cloud`**. Seeding rules in [Ecobee quick start](#ecobee-quick-start-homekit). **`cloud`**: only realistic with a personal developer **`api_key`**. |
| `hk_transport` | No | **`mqtt`** (default, preferred) or **`websocket`**. Saving transport or `hk_*` fields restarts the hub client. |
| `hk_ws_url` | WS fallback | WebSocket URL of **udi-poly-homekit**, e.g. `ws://127.0.0.1:8163`. |
| `hk_ws_token` | No | Optional hello token (**WebSocket only**). |
| `hk_mqtt_host` | MQTT | Broker hostname. Default `localhost`. |
| `hk_mqtt_port` | MQTT | Broker port. Default `1884`. |
| `hk_mqtt_username` | No | Broker username when required. |
| `hk_mqtt_password` | No | Broker password when required. |
| `hk_mqtt_hub_slug` | MQTT | Must match hub **`mqtt_hub_slug`**. Default `default`. Characters: `[A-Za-z0-9_-]`, length 1–128. |
| `hk_mqtt_client_slug` | MQTT | Client topic segment. Default **`udi-poly-ecobee`**. Unique per NS instance if sharing a broker. |
| `use_celsius` | No | `auto`, `true`, or `false`. Default `auto`. |
| `dry_run` | No | `true` / `false`. Default `false`. |
| `hk_heat_cool_min_delta` | No | HomeKit **Auto** mode: minimum separation between **Heat Setpoint** and **Cool Setpoint** when co-writing HAP thresholds (matches Ecobee app **Compressor minimum delta**). Integer **1–10** in the stat's display units (°F or °C). Default **`3`**. Set to **`2`** when the Ecobee app allows a 2° minimum. Cloud mode ignores this (Ecobee API enforces limits on the stat). |
| `api_key` | Cloud / PIN | Ecobee developer application key. See [Cloud backend](#cloud-backend-legacy). |

---

## Reference: Custom Typed Configuration Parameters

| Section | Purpose |
| ------- | ------- |
| **HomeKit thermostat address overrides** | Map hub `device_id` to thermostat id for IoX address `t<id>`. |
| **HomeKit remote sensor address overrides** | Optional hints for `rs_*` sensor addresses. |
| **Climate program labels** | Per-thermostat comfort display names for IoX **Climate Type** labels and editors. See [Climate program labels](#climate-program-labels). |

---

## Climate program labels

**Custom Typed Data → Climate program labels** stores friendly comfort names **per thermostat**. The plugin uses these names in IoX nodedef labels (**CTA_***, **CT_***, **CT_HK_***) and in per-thermostat **Climate Type** command lists.

### Structure

One top-level row per thermostat:

| Field | Purpose |
| ----- | ------- |
| `thermostat_id` | IoX address suffix (`t<id>`), e.g. `123456789012` |
| `name` | Thermostat display name (informational) |
| `device_id` | HomeKit hub device id (optional; helps match hub-only stats) |
| `climates` | Nested list of comforts for this stat |

Each nested **climates** row:

| Field | Purpose |
| ----- | ------- |
| `climateRef` | Ecobee program ref (e.g. `home`, `away`, `sleep`, `smart2`) |
| `name` | Label shown in IoX for that comfort |

Example (cloud stat with custom Smart comforts):

```json
{
  "thermostat_id": "123456789012",
  "name": "Downstairs",
  "climates": [
    {"climateRef": "home", "name": "Home"},
    {"climateRef": "away", "name": "Away"},
    {"climateRef": "sleep", "name": "Sleep"},
    {"climateRef": "smart1", "name": "Workshop"},
    {"climateRef": "smart2", "name": "Guest"}
  ]
}
```

### Auto-initialization

You usually do **not** need to create rows manually:

- **Cloud:** rows are created or updated on **DISCOVER**. Names are filled from `program.climates` in the Ecobee API when still empty or at plugin defaults. **User-edited names are preserved** on later syncs.
- **HomeKit:** rows are created when the hub device list is processed. Names start from the default catalog until you edit them here.

After you change labels in Custom Typed Data, the plugin refreshes the IoX profile so **Climate Type** pick lists pick up the new text (cloud immediately on save; HomeKit on the next hub device list / profile write).

### Effect on **Climate Type** (cloud vs HomeKit)

**Cloud backend**

- **Climate Type** **status** uses the full comfort catalog with your custom names where configured.
- **Climate Type** **commands** list only comforts **configured on that thermostat** (from the Ecobee API), not the entire fixed catalog. Custom names appear in the command editor (**CT_***).

**HomeKit backend**

- **Climate Type** **status** uses the full comfort label range (**CTA_***) so current comfort and all configured names can display correctly. When Ecobee reports HAP byte **3** (Temp) for comforts beyond Home / Sleep / Away (e.g. **Vacation** and **Away Extended**), status resolves **Climate Type** from **Heat Setpoint** / **Cool Setpoint** signatures against the thermostat’s configured comfort list (not always **Smart1**).
- **Climate Type** **commands** use the four HomeKit hold slots (**CT_HK_***) indices **0–3** (Away / Home / Sleep / Temp). For comforts that need explicit setpoints (Temp slot, Vacation, Away Extended, etc.), the plugin writes heat/cool thresholds before the vendor hold. See [HomeKit Climate Type — commands and setpoints](#homekit-climate-type-commands-and-setpoints).

### HomeKit Climate Type — commands and setpoints

Ecobee HomeKit exposes only **four** hold bytes on the wire (Home, Sleep, Away, Temp). IoX can still **command** extra comforts when their setpoints are known:

| Source | What is cached |
|--------|----------------|
| **Startup / hub reconnect** | Automatic debounced snapshot per thermostat (same as **Query**) after the hub connects |
| **Vendor snapshot** | Target heat/cool for **Home**, **Sleep**, and **Away** (`VENDOR_ECOBEE_*_TARGET_*`) |
| **Learned signatures** | Heat/cool pairs for **Vacation**, **Away Extended**, custom Smart slots, etc., when the stat has been on that comfort (status or Ecobee app) |
| **HK command index 3** | Maps to the first configured extra comfort on that stat (e.g. **Vacation** when **Smart1** is not in the program) |

**Home / Away / Sleep** commands use the hold byte only (Ecobee applies program setpoints). **Vacation**, **Away Extended**, and other Temp-slot comforts require cached setpoints; the command is rejected (IoX unchanged) until a snapshot or prior use has populated the cache.

Extra comforts that have never been active on the stat may still need one activation from the **Ecobee app** (or cloud backend) before IoX can command them over HomeKit.

---

## Reference: HomeKit behavior vs cloud

### Overview

- **No Ecobee OAuth or PIN** on the HomeKit path; pairing lives in **udi-poly-homekit**.
- Thermostats appear as **`t…`** nodes; remote sensors as **`rs…`**. **No weather / forecast nodes** on HomeKit.
- **Realtime updates** from hub events; **Query** triggers a snapshot read. On hub connect / Node Server start, each thermostat also gets an automatic debounced snapshot to cache comfort setpoints for **Climate Type** commands.
- Hub metadata characteristics are informational only (not copied to IoX drivers). Unknown HAP chars may log **`homekit_unknown_chars`** notices.
- Temperature display follows **`use_celsius`** in Custom Params, not HAP Temperature Display Units.

### HomeKit thermostat node (drivers and commands)

HomeKit thermostats use **`EcobeeHKC_*`** / **`EcobeeHKF_*`** (Celsius / Fahrenheit) — slimmer than cloud nodedefs.

**Supported via hub:** **Temperature**, **Heat Setpoint**, **Cool Setpoint**, **Mode**, **Fan Mode**, **Humidity**, **HVAC State**, **Fan State**, **Humidification Setpoint**, **Schedule Mode**, **Climate Type**, **Setpoint Up** / **Setpoint Down**, **Query**.

In **Auto** mode, **Heat Setpoint** / **Cool Setpoint** commands enforce a minimum gap before writing to the hub so IoX matches the physical thermostat. Default gap is **3** degrees; set Custom Param **`hk_heat_cool_min_delta`** to **`2`** (or your Ecobee app **Compressor minimum delta**) when the stat allows a narrower range. Value is in the stat's display units (°F or °C per **`use_celsius`**).

**Climate Type** **(HomeKit):** **Status** uses the full comfort label range with per-thermostat custom names. When the hub reports HAP byte **3** (Temp), status disambiguates **Vacation**, **Away Extended**, and other extra comforts using setpoint signatures (not always catalog **Smart1**). **Commands** use **CT_HK_*** indices **away (0), home (1), sleep (2), smart1 (3)**; index **3** maps to the first configured extra comfort when **smart1** is not on the stat. For Temp-slot and collision comforts, the plugin writes heat/cool setpoints before the vendor hold. See [HomeKit Climate Type — commands and setpoints](#homekit-climate-type-commands-and-setpoints).

**Schedule Mode** **(HomeKit):** **Running** sends the Ecobee vendor **clear hold** sequence on the hub and refreshes the thermostat snapshot. **Hold Next** (1) and **Hold Indefinite** (2) update the IoX driver only — HomeKit does not expose hold duration the way the cloud API does. **Heat Setpoint** / **Cool Setpoint** and **Climate Type** writes imply a hold (**Schedule Mode** becomes **Hold Next**); use **Schedule Mode** = **Running** to resume the programmed schedule.

**Removed vs cloud (not on HomeKit node):** **Fan On Time**, **Backlight On Intensity**, **Backlight Sleep Intensity**, **ECO+**, etc. Use the Ecobee app or cloud if you need those.

**Hold duration:** HomeKit cannot set hold-next vs indefinite independently. After a hold is placed via setpoints or **Climate Type**, **Schedule Mode** reports **Hold Next** (hold active). Use the Ecobee app or cloud backend if you need the exact hold type.

**Fan Mode** uses the same IoX values as cloud (**auto = 0**, **on = 1**); HAP TargetFanState is translated at the hub boundary.

### Limitations (HomeKit path)

The Ecobee app's full program list is not exposed as distinct HomeKit **hold bytes** — only **Home, Sleep, Away,** and **Temp** on the wire. Custom names for additional comforts appear in **Climate Type** status; commanding them from IoX uses cached setpoints when available (see [HomeKit Climate Type — commands and setpoints](#homekit-climate-type-commands-and-setpoints)). Schedules, hold duration, and some comfort features may not map 1:1 to HomeKit.

After profile upgrades, restart the Node Server and let the profile refresh so nodedefs update.

---

## Cloud backend (legacy)

Use only if you have a **working personal Ecobee developer API key** (not UDI / Polyglot Cloud OAuth) which is an oauth key pointing back to the portal.

1. Set **`backend`** to **`cloud`** and configure **`api_key`**.
2. On first start you receive a PIN.
3. Log in at the Ecobee web site → Profile → **My Apps** → **Add Application** → enter the PIN.
4. Wait for approval (checked every 60 seconds; do not restart during this step).
5. Thermostats, sensors, weather, and forecast nodes are added via the Ecobee API (refreshes about every 3 minutes).

**Climate Type** **(cloud):** **Status** and **commands** use per-thermostat comfort lists from the Ecobee API. The command editor (**CT_***) shows only comforts configured on that stat, with labels from [Climate program labels](#climate-program-labels) when set. See [Effect on Climate Type](#effect-on-climate-type-cloud-vs-homekit) for details.

**Schedule mode:** **Schedule Mode** — **Running** / **Hold Next** / **Hold Indefinite** on all backends. On **HomeKit**, only **Running** is sent to the hub (vendor clear hold); **Hold Next** and **Hold Indefinite** are IoX-only. See [HomeKit behavior vs cloud](#reference-homekit-behavior-vs-cloud) for **Climate Type** hold limits.

With Polyglot OAuth, **`api_key`** overrides injected defaults and must use a redirect URI matching `https://polyglot.isy.io/api/oauth/callback`. Do not rely on historical UDI-provided keys for new setups.
