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
| **Learned signatures** | Heat/cool for **Vacation**, **Away Extended**, custom Smart slots when the stat has been on that comfort |

Extra comforts that have **never** been active may still need one activation from the **Ecobee app** (or cloud backend) before IoX can command them over HomeKit — HomeKit does not expose vendor target characteristics for those comforts.

## Startup refresh (4.1.7)

After the hub connects (`hello OK`) and when the paired device list is processed, `HomeKitBackend._schedule_thermostat_startup_refresh()` runs a **1 s debounced** full snapshot on each HomeKit thermostat. No manual **Query** is required to cache **Home / Sleep / Away** targets.
