# Ecobee Poly

## Help

Questions: [PG3 Ecobee SubForum](https://forum.universal-devices.com/forum/322-ecobee/) · [GitHub issues](https://github.com/UniversalDevicesInc-PG3/udi-poly-ecobee/issues)

## Start here

**[CONFIG.md](CONFIG.md)** — step-by-step setup for new installations.

For **HomeKit hub mode** (recommended): install and pair on **[udi-poly-homekit](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit)** first, then follow **[Ecobee quick start (HomeKit)](CONFIG.md#ecobee-quick-start-homekit)** in this repo's CONFIG.

## Cloud mode

Ecobee has **disabled UDI / Polyglot Cloud OAuth** for this integration. **New setups should use HomeKit hub mode.** Cloud mode only remains possible with a **personal Ecobee developer API key** you registered before shared keys stopped working — see **[CONFIG.md — Cloud backend (legacy)](CONFIG.md#cloud-backend-legacy)**.

## Node info

1. **Controller** — Nodeserver Online (process status)
2. **Controller** — Ecobee Connection Status (hub or cloud communication)
3. **Thermostat** (`n00x_t`) — Connected
4. **Main sensor** (`n00x_s`) — Responding (sensor inside thermostat)
5. **Remote sensor** (`n00x_rs`) — Responding (dead battery or out-of-range if false)

On **HomeKit** thermostats, connection semantics differ from cloud **GV8**; see **[CONFIG.md](CONFIG.md)** for controller **GV1** / **GV5** status.

## Monitoring

See [Polyglot NodeServer monitoring](https://forum.universal-devices.com/topic/25016-polyglot-nodeserver-monitoring/) for heartbeats. Cloud installs can also check thermostat **GV8** for Ecobee server visibility.

## Upgrading

Store releases typically appear within about an hour of publish.

1. Open the Polyglot web UI → Dashboard → **Restart** the Node Server
2. If the release notes mention **Profile Change**, close and reopen the Admin Console if nodes look stale

## Changelog

**[CHANGELOG.md](CHANGELOG.md)**

## Advanced documentation

HomeKit driver details, GV3 hold behavior, limitations vs cloud, and full parameter tables: **[CONFIG.md](CONFIG.md)**
