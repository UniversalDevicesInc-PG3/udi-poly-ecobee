# Ecobee Poly

## Help

If you have any issues are questions you can ask on [PG3 Ecobee NS SubForum](https://forum.universal-devices.com/forum/322-ecobee/) or report an issue at [PG3 Ecobee Github issues](https://github.com/UniversalDevicesInc-PG3/udi-poly-ecobee/issues).

## Recommended setup (HomeKit)

**For new installations, install and configure [udi-poly-homekit](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit) first**, then this nodeserver.

1. Add **udi-poly-homekit** from the PG3 store. Pair your Ecobee(s) through that plugin, enable its **WebSocket hub**, and note **`ws_host` / `ws_port`** (and **`ws_token`** if you set one). Typical URL on the same machine as Polyglot: `ws://127.0.0.1:8163`.
2. Add **udi-poly-ecobee**. If **`backend`** is not already in PG3, it is **seeded** once: **`homekit`** for a brand-new NS, or **`cloud`** when the store still looks like a legacy cloud/OAuth/PIN setup (see **`CONFIG.md`**). Set **`hk_ws_url`** to the hub WebSocket URL and **`hk_ws_token`** if required.

**Ecobee cloud mode** (REST API) is effectively **unavailable for Universal Devices / Polyglot Cloud OAuth**: Ecobee has **disabled UDI’s access** to the cloud API for this integration. **Cloud mode can only work** if you use **your own Ecobee developer application key** that you obtained **before** Ecobee stopped accepting API traffic for the old shared/UDI keys—and you enter that key in **Custom Params** (**`api_key`**) where applicable (local PIN flow). Do not expect cloud OAuth or the historical UDI key path to work for new setups. Use **HomeKit hub mode** instead.

## Installation

Install from the Polyglot 3 store. **New installs:** complete **[Recommended setup (HomeKit)](#recommended-setup-homekit)** so the HomeKit hub is installed, paired, and listening before you point this plugin at **`hk_ws_url`**.

### Initial setup (cloud backend only)

These steps apply only when **`backend`** is **`cloud`** and you have a **working personal Ecobee developer API key** (see **Recommended setup** above). They do **not** apply to Polyglot Cloud OAuth anymore.

1. On first start up you will be given a PIN.
1. Login to the Ecobee web page, click on your profile, then click 'My Apps' > 'Add Application'.
1. You will be prompted to enter the PIN provided.
1. The nodeserver will check every 60 seconds that you have completed the approval so do not restart the nodeserver. You can monitor the log to see when the approval is recognized.
1. Your thermostat will be added to ISY, along with nodes for any sensors, a node for the current weather, and a node for the forecast.

After the first run. It will refresh any changes every 3 minutes. This is a limitation imposed by Ecobee.

## HomeKit hub mode

This is the **supported** integration path for Ecobee: **[udi-poly-homekit](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit)** must already be **installed, paired to your Ecobee, and exposing its WebSocket hub** before this nodeserver can work in **`backend` = `homekit`**. Default URL is often `ws://127.0.0.1:8163` when the hub runs on the same host as Polyglot. See **[Recommended setup (HomeKit)](#recommended-setup-homekit)** for order of operations.

### What you configure

- In **Custom Params**, **`backend`** defaults to **`homekit`** on new installs; change it only if you intentionally use **cloud** (see caveats above).
- Set **`hk_ws_url`** to the hub WebSocket URL (see udi-poly-homekit docs for port and TLS).
- Optionally set **`hk_ws_token`** if the hub requires a hello/auth token.
- **`use_celsius`**: `auto`, `true`, or `false` (same meaning as cloud; `auto` currently behaves like Fahrenheit for HomeKit in code paths that do not infer from the accessory).
- **`dry_run`**: default **`false`**. Set to **`true`** to log thermostat commands without sending them to the hub; IoX drivers are not updated from those writes. A PG3 **Notice** (`homekit_dry_run`) reminds you when dry run is on.

**Custom Typed Params** (PG3) for HomeKit:

| Section | Purpose |
| ------- | ------- |
| **HomeKit thermostat address overrides** | Map hub `device_id` to a thermostat id so the IoX address is `t<id>`. |
| **HomeKit remote sensor address overrides** | Optional `code` (and `aid` / accessory name) to stabilize `rs_*` sensor addresses. |
| **Climate program labels** | Per `device_id`: **HomeKit** and **cloud** use the same **climateList** / **CT_*_\<tstat\>*** editors for **GV3**; typed rows override labels by catalog index. |

Full parameter table: **`CONFIG.md`** in this repo (also shown in the PG3 Custom Params doc when configured).

### Behavior vs cloud mode

- **No Ecobee OAuth or PIN** is used; pairing and credentials are entirely in udi-poly-homekit.
- Thermostats still appear as **`t…`** nodes; remote room sensors appear as **`rs_…`** children (from hub snapshot/events). **Weather / forecast nodes** from the Ecobee API are **not** created on the HomeKit path.
- **Controller drivers**: **GV1** reflects hub WebSocket connectivity; **GV3** reflects that the hub reported paired devices. Heartbeats behave like cloud.
- **Realtime updates** come from hub **event** frames; **QUERY** triggers a **snapshot** read for that device.
- **Hub metadata characteristics** (accessory information, product data, temperature display units, version, vendor UUIDs, etc.) are classified as *informational*: they are **not copied into IoX drivers** and they **do not** produce **`homekit_unknown_chars`** notices. That only means the plugin does not surface them in PG3 today; they can still matter for Apple/HomeKit or debugging. Temperature display is still driven by **`use_celsius`** in Custom Params, not by HAP Temperature Display Units.
- HAP characteristics that are truly unknown may still log a warning and accumulate **`homekit_unknown_chars`** (deduplicated by name).
- The hub may send structured **`warnings`** on the WebSocket **hello `ack`** and **`list_devices`** (see **udi-poly-homekit** `PROTOCOL.md`). This plugin logs each entry and shows them in a PG3 **Notice** named **`homekit_hub_warnings`**. An empty **`warnings`** array clears that notice.
- If no thermostat node is created from **`list_devices`**, check PG3 **Notice** **`homekit_no_thermostat`** (raw **`devices[]`** snapshot) and hub **`warnings`**; **udi-poly-homekit** must send each row with **`device_id`** and thermostat **category** metadata per **PROTOCOL.md**.

### HomeKit thermostat node (drivers and commands)

HomeKit thermostats use nodedefs **`EcobeeHKC_<id>`** / **`EcobeeHKF_<id>`** (Celsius / Fahrenheit). These are **slimmer** than cloud **`EcobeeC_*`** / **`EcobeeF_*`**: controls that HomeKit does not expose are **omitted** from the node so the PG3 UI matches what the hub can do.

**Why two nodedefs (C vs F) instead of one?** Other nodeservers (e.g. some use a single nodedef with a **`temperature`** editor that defines both UOM 4 and UOM 17 ranges, then set **`uom` per `setDriver`**) can avoid splitting nodes. This plugin keeps **separate C and F thermostat nodedefs** end-to-end—cloud **`EcobeeC_*`** / **`EcobeeF_*`**, HomeKit **`EcobeeHKC_*`** / **`EcobeeHKF_*`**—for **consistency** with the existing profile and docs. Scale is still chosen with **`use_celsius`** in Custom Params (`auto` currently follows the same rules as elsewhere in this codebase, not HAP Temperature Display Units).

**Still present (supported via hub):** **ST**, **CLISPH**, **CLISPC**, **CLIMD**, **CLIFS**, **CLIHUM**, **CLIHCS**, **CLIFRS**, **GV1** (humidification setpoint / target relative humidity), **GV3** (comfort / program: **read** from ``VENDOR_ECOBEE_CURRENT_MODE``; **set** via ``VENDOR_ECOBEE_SET_HOLD_SCHEDULE``). **GV3** and **CLIFS** use the **same IoX values as cloud** (``climateMap`` / **climateList** indices for programs; ``fanMap`` order for fan target: **auto = 0**, **on = 1**). The plugin translates Ecobee HAP vendor comfort bytes (**0 = Home, 1 = Sleep, 2 = Away, 3 = Temp**) and HAP **TargetFanState** (**0 = On, 1 = Auto**) at the hub boundary so existing programs and **CT_*_\<tstat\>*** / **I_TSTAT_FAN_MODE** keep working when you switch between cloud and HomeKit. **BRT** / **DIM** (setpoint step via target temperature where applicable), **QUERY**.

**Removed vs cloud nodedef (not on HomeKit node):** **CLISMD** (hold / schedule mode), **GV4** (fan minimum on time), **GV5** (dehumidification setpoint), **GV6** (Smart Home/Away), **GV7** (Follow Me), **GV8** (connected), **GV9** (weather), **GV10** / **GV11** (backlight), **GV17** (ECO+). Use the Ecobee app or cloud/API path if you need those.

**Hold type (Running / Hold next / Hold indefinite) vs HomeKit GV3:** On **cloud** thermostats, **CLISMD** is *Schedule mode*: Running cancels holds; the two Hold options choose whether the hold lasts until the next scheduled event or indefinitely, and that choice is sent to the Ecobee API (including when you change comfort type with **GV3**). On **HomeKit** thermostats there is **no CLISMD** and **no** IoX driver that reports hold *duration*. **GV3** is only the vendor **comfort / program index** (**read** ``VENDOR_ECOBEE_CURRENT_MODE``; **set** ``VENDOR_ECOBEE_SET_HOLD_SCHEDULE``). After a HomeKit write you can refresh **GV3** to see which program slot the thermostat reports; you **cannot** tell from this nodeserver whether the hold is “until next” or “indefinite”—use the **Ecobee app** or **cloud** backend if you need that distinction.

After upgrading, restart the nodeserver and let the profile refresh (version **4.1.0**+). Existing HomeKit thermostat nodes pick up the new nodedef id on reload.

### Limitations (HomeKit path)

Additional cloud-only behavior may never map 1:1 to HomeKit (schedules, holds, some comfort features). Expect to iterate on firmware and hub protocol as you test.

## Settings

Applies to **cloud**-mode thermostats (**CLISMD** / Schedule mode). **HomeKit** thermostat nodes do not expose **CLISMD**; see **Hold type (Running / Hold next / Hold indefinite) vs HomeKit GV3** under **HomeKit thermostat node** above.

- The "Schedule Mode" is one of
  1. Running
  1. Hold Next
  1. Hold Indefinite
  If this is changed to either Hold settings then the current Cool/Heat and Fan modes are sent with that Hold type.  If Running is selected then any Holds are cancelled.

## Node info

1. Controller node - Nodeserver Online
   * The Nodeserver process status
1. Controller node - Ecobee Connection Status
   * The Nodeserver communication to the Ecobee server status.
1. Main thermostat node (n00x_t) - Connected
   * The Ecobee servers can see the thermostat
1. Main thermostat sensor node (n00x_s) - Responding
   * Probably node needed since main sensor is inside the thermostat
1. Remote sensor node (n00x_rs) - Responding
   * The thermostat can see the sensor, this going False can indicate dead battery or out-of-range.

## Monitoring

See https://forum.universal-devices.com/topic/25016-polyglot-nodeserver-monitoring/ for info on how to use the heartbeats.  You can also check the thermostat GV8 True/False to see if the Ecobee servers can see the thermostats.

## Upgrading

When a new release is published, it should be released to the polyglot web store within an hour, currently around 40 minutes past the hour.

1. Open the Polyglot web page
  1. Go to the Dashboard for the ISY and Restart the NS
  1. In the future there will be an upgrade button for major and minor changes, only patch changes will be automatic
1. If the release has a (Profile Change) then the profile will be updated automatically but if you had the Admin Console open, you will need to close and open it again.

## Changelog

Version history is in **[CHANGELOG.md](CHANGELOG.md)** in this repository.
