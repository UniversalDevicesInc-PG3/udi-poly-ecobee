# HomeKit Climate Type — status, commands, and setpoint cache

This supplements **README.md** and **CONFIG.md** for releases **4.1.6** and **4.1.7**.

IoX labels below match **`template/en_us.txt`** (e.g. **Climate Type**, **Schedule Mode**, **Heat Setpoint**, **Cool Setpoint**).

## Status (4.1.6)

When Ecobee reports HAP comfort byte **3** (Temp) for comforts beyond Home / Sleep / Away (e.g. **Vacation** and **Away Extended**), **Climate Type** status is resolved using **Heat Setpoint** / **Cool Setpoint** signatures against the thermostat’s configured comfort list — not always catalog **Smart1** (index 3).

## Commands (4.1.7)

Comforts that share the HAP **Temp** slot (or collide with **Away** on the wire) require explicit setpoints before `VENDOR_ECOBEE_SET_HOLD_SCHEDULE`:

1. Plugin resolves heat/cool from cache (see below).
2. Writes **Heat Setpoint** / **Cool Setpoint** thresholds to the hub.
3. Sends the vendor hold byte.
4. Aborts without updating IoX if setpoints are unknown.

**Home / Away / Sleep** **Climate Type** commands use the hold byte only (Ecobee applies program setpoints).

**Climate Type command index 3** (“Smart1” in the catalog) maps to the **first configured extra comfort** on that stat when **Smart1** is not in the program (e.g. **Vacation** on Office Hallway).

## Setpoint cache sources

| Source | What is cached |
|--------|----------------|
| **Startup / hub reconnect** | Debounced hub snapshot per thermostat (same as node **Query**) after hub connect and device list processing |
| **Vendor snapshot** | Target heat/cool for **Home**, **Sleep**, and **Away** (`VENDOR_ECOBEE_*_TARGET_*`) |
| **Program (cloud DISCOVER)** | Heat/cool for every configured comfort from the Ecobee API (`customData.climate_setpoints`) — optional if you use cloud |
| **Hub-learned (HomeKit-only)** | When the stat is on a custom comfort, **QUERY** records its heat/cool, persists to ``customData.climate_setpoints``, and auto-fills **Heat** / **Cool** on the matching typed row |
| **Typed data (read-only fields)** | **Heat** / **Cool** on each comfort row under **Climate program labels** — filled by the plugin when setpoints are learned (not manual entry) |
| **Learned signatures** | Heat/cool for **Vacation**, **Away Extended**, custom Smart slots when the stat has been on that comfort |

### HomeKit-only (no cloud API)

Ecobee HomeKit exposes vendor target setpoints only for **Home**, **Sleep**, and **Away**. Custom comforts (**Working**, **Vacation**, etc.) share HAP hold byte **Temp** and need explicit heat/cool before the hold command.

Without cloud you can still command them:

1. **Learn from the stat** — When the schedule or Ecobee app puts the stat on a custom comfort, run **QUERY** (or wait for the startup snapshot). The plugin caches heat/cool and writes them to typed data for later commands.
2. **Rename comforts** — Edit **Display name** under **Climate program labels** (e.g. rename ``smart1`` to **Workshop**). Saving typed data rebuilds the IoX profile automatically.
3. **Home / Away / Sleep** — Work from vendor targets on every **QUERY**; no cloud required.

Extra comforts that have **never** been active and have no manual setpoints cannot be commanded until one of the above fills the cache — HomeKit does not publish program setpoints for those comforts.

## Command list (4.1.8)

HomeKit **Climate Type** commands use the **same per-thermostat comfort list** as cloud (custom names from **Climate program labels**). Saving typed data pushes an updated profile to IoX. The plugin still maps each choice to the correct HomeKit hold byte and writes program/cached setpoints when required.

## Startup refresh (4.1.7)

After the hub connects (`hello OK`) and when the paired device list is processed, `HomeKitBackend._schedule_thermostat_startup_refresh()` runs a **1 s debounced** full snapshot on each HomeKit thermostat. No manual **Query** is required to cache **Home / Sleep / Away** targets.
