# Ecobee Node Server — configuration

## Before you start

1. **Install and configure [udi-poly-homekit](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit) first** (PG3 store): pair your Ecobee(s), enable the hub WebSocket, set **`ws_host` / `ws_port`** (and optional **`ws_token`**) in that plugin. This nodeserver’s HomeKit mode talks to that hub only; it does not replace it.
2. **Missing `backend` param:** the plugin **seeds** a default once: **`homekit`** for a fresh NS (no OAuth, no `api_key`, no saved Ecobee tokens/PIN in customdata, no extra nodes yet); **`cloud`** if Polyglot OAuth is enabled for this NS, **`api_key`** is set, customdata has **`tokenData`** / **`pin_code`**, or the NS already has nodes besides the controller (legacy upgrade). If **`backend`** is **already stored** in PG3, it is never changed by seeding.
3. **Ecobee cloud (REST API):** Ecobee has **cut off UDI / Polyglot Cloud access** for this integration. **Cloud mode only remains viable** if you use **your own Ecobee developer application key** that you registered **before** Ecobee stopped honoring requests for the old shared keys, and you configure **`api_key`** / PIN flow as documented for **local** Polyglot. Do not rely on historical OAuth or UDI-provided keys for new setups.

## Custom Configuration Parameters

Flat **Custom Params** (PG3). New installs: keys are seeded at startup so every row appears in the editor; adjust values and save.

| Parameter | Required | Description |
| --------- | -------- | ----------- |
| `backend` | No | **`homekit`** or **`cloud`**. If the key is missing, the plugin seeds **`homekit`** for a fresh NS and **`cloud`** when OAuth, **`api_key`**, Ecobee tokens/PIN in customdata, or other nodes besides the controller indicate a legacy install (**Before you start**). Saved values are never overwritten by seeding. **`cloud`**: only realistic with a **personal developer `api_key`** (UDI cloud OAuth is not available for new users). |
| `hk_ws_url` | For HomeKit | WebSocket URL of the **udi-poly-homekit** hub, e.g. `ws://127.0.0.1:8163`. Required when **`backend`** is **`homekit`**. |
| `hk_ws_token` | No | Optional bearer / hello token if the hub requires auth. |
| `use_celsius` | No | `auto`, `true`, or `false` for temperature units. Default `auto`. |
| `dry_run` | No | `true` or `false`. When `true`, the HomeKit path logs writes instead of applying them. Default `true`. |
| `api_key` | Cloud / PIN | Your **Ecobee developer application key** for the cloud API (required for PIN flow on **local** Polyglot; also the path if you still have a grandfathered personal key). **Not** the old UDI/Polyglot Cloud OAuth path—see **Before you start**. |

## Custom Typed Configuration Parameters

Use **Custom Typed Params** in PG3 for HomeKit mode:

| Section | Purpose |
| ------- | ------- |
| **HomeKit thermostat address overrides** | Map hub `device_id` to an Ecobee thermostat id for IoX address `t<id>`. |
| **HomeKit remote sensor address overrides** | Optional hints for `rs_*` sensor node addresses. |
| **Climate program labels** | Per `device_id`: override **climateList** slot labels (by index) for both **HomeKit** and **cloud**; **GV3** editors match **CT_*_\<tstat\>*** on both paths. |

See **README.md**: **Recommended setup (HomeKit)** and **HomeKit hub mode** first; **Initial setup (cloud backend only)** only if you use **`backend`** **`cloud`**.

In HomeKit mode, hub **`warnings`** (per udi-poly-homekit **PROTOCOL.md**) appear in PG3 **Notices** as **`homekit_hub_warnings`** and in **`logs/debug.log`** at WARNING/ERROR.

If the hub payload cannot be turned into a thermostat node, **Notice** **`homekit_no_thermostat`** includes a JSON snapshot of the **`devices[]`** list the plugin received from the hub.
