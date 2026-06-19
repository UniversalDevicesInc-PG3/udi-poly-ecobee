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
   - **GV1** (Ecobee Connection Status) = **true** when hello to the hub succeeded
   - **GV5** (HomeKit MQTT) = **2** (Connected) when using MQTT
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

| Driver | Good value | Meaning |
|--------|------------|---------|
| **GV1** | `true` | Active transport completed hello to the hub. |
| **GV5** | `2` | MQTT connected (when **`hk_transport`** is `mqtt`). |
| **GV4** | `2` | WebSocket connected (only when **`hk_transport`** is `websocket`). |
| **GV3** | reflects hub | Hub reported paired devices. |

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
- **Custom Typed Params** (address overrides, climate labels): only needed for advanced installs — see [Reference: Typed params](#reference-custom-typed-configuration-parameters).

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
| `api_key` | Cloud / PIN | Ecobee developer application key. See [Cloud backend](#cloud-backend-legacy). |

---

## Reference: Custom Typed Configuration Parameters

| Section | Purpose |
| ------- | ------- |
| **HomeKit thermostat address overrides** | Map hub `device_id` to thermostat id for IoX address `t<id>`. |
| **HomeKit remote sensor address overrides** | Optional hints for `rs_*` sensor addresses. |
| **Climate program labels** | Per `device_id`: override **climateList** labels. **HomeKit** **GV3** **commands** only offer indices **0–3** (away / home / sleep / smart1); status can show wider label range. |

---

## Reference: HomeKit behavior vs cloud

### Overview

- **No Ecobee OAuth or PIN** on the HomeKit path; pairing lives in **udi-poly-homekit**.
- Thermostats appear as **`t…`** nodes; remote sensors as **`rs…`**. **No weather / forecast nodes** on HomeKit.
- **Realtime updates** from hub events; **QUERY** triggers a snapshot read.
- Hub metadata characteristics are informational only (not copied to IoX drivers). Unknown HAP chars may log **`homekit_unknown_chars`** notices.
- Temperature display follows **`use_celsius`** in Custom Params, not HAP Temperature Display Units.

### HomeKit thermostat node (drivers and commands)

HomeKit thermostats use **`EcobeeHKC_*`** / **`EcobeeHKF_*`** (Celsius / Fahrenheit) — slimmer than cloud nodedefs.

**Supported via hub:** **ST**, **CLISPH**, **CLISPC**, **CLIMD**, **CLIFS**, **CLIHUM**, **CLIHCS**, **CLIFRS**, **GV1** (target humidity), **CLISMD** (resume schedule), **GV3** (comfort / program), **BRT** / **DIM**, **QUERY**.

**GV3 (HomeKit) — four hold slots only:** Ecobee's vendor hold accepts four program bytes mapped to IoX indices **away (0), home (1), sleep (2), smart1 (3)**. **GV3** **commands** expose only those four (**CT_HK_***). **GV3** **status** uses the full **CTA_*** range for label resolution. Vacation, Smart Away, and other app-only programs are not separate HomeKit writes — use the **Ecobee app** or **cloud** backend.

**CLISMD (HomeKit):** **Running (0)** sends the Ecobee vendor **clear hold** sequence on the hub and refreshes the thermostat snapshot. **Hold Next (1)** and **Hold Indefinite (2)** update the IoX driver only — HomeKit does not expose hold duration the way the cloud API does. Setpoints and **GV3** writes imply a hold (**CLISMD** becomes **1**); use **CLISMD=0** to resume the programmed schedule.

**Removed vs cloud (not on HomeKit node):** **GV4**–**GV11**, **GV17** (ECO+), etc. Use the Ecobee app or cloud if you need those.

**Hold duration:** HomeKit cannot set hold-next vs indefinite independently. After a hold is placed via setpoints or **GV3**, **CLISMD** reports **1** (hold active). Use the Ecobee app or cloud backend if you need the exact hold type.

**CLIFS** uses the same IoX values as cloud (**auto = 0**, **on = 1**); HAP TargetFanState is translated at the hub boundary.

### Limitations (HomeKit path)

The Ecobee app's full program list (vacation, custom comforts, Smart Home/Away, etc.) is not exposed as distinct HomeKit hold values — only **Home, Sleep, Away,** and **Temp** (smart1). Schedules, hold duration, and some comfort features may not map 1:1 to HomeKit.

After profile upgrades, restart the Node Server and let the profile refresh so nodedefs update.

---

## Cloud backend (legacy)

Use only if you have a **working personal Ecobee developer API key** (not UDI / Polyglot Cloud OAuth).

1. Set **`backend`** to **`cloud`** and configure **`api_key`**.
2. On first start you receive a PIN.
3. Log in at the Ecobee web site → Profile → **My Apps** → **Add Application** → enter the PIN.
4. Wait for approval (checked every 60 seconds; do not restart during this step).
5. Thermostats, sensors, weather, and forecast nodes are added via the Ecobee API (refreshes about every 3 minutes).

**Schedule mode:** **CLISMD** — Running / Hold Next / Hold Indefinite on all backends. On **HomeKit**, only **Running (0)** is sent to the hub (vendor clear hold); **1** and **2** are IoX-only. See [GV3 hold slots](#reference-homekit-behavior-vs-cloud) above.

With Polyglot OAuth, **`api_key`** overrides injected defaults and must use a redirect URI matching `https://polyglot.isy.io/api/oauth/callback`. Do not rely on historical UDI-provided keys for new setups.
