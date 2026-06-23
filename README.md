# Ecobee Poly

## Help

Questions: [PG3 Ecobee SubForum](https://forum.universal-devices.com/forum/322-ecobee/) · [GitHub issues](https://github.com/UniversalDevicesInc-PG3/udi-poly-ecobee/issues)

## Start here

**[CONFIG.md](CONFIG.md)** — step-by-step setup for new installations.

For **HomeKit hub mode** (recommended): install and pair on **[udi-poly-homekit](https://github.com/UniversalDevicesInc-PG3/udi-poly-homekit)** first, then follow **[Ecobee quick start (HomeKit)](CONFIG.md#ecobee-quick-start-homekit)** in this repo's CONFIG.

## Cloud mode

Ecobee has **disabled UDI / Polyglot Cloud OAuth** for this integration. **New setups should use HomeKit hub mode.** Cloud mode only remains possible with a **personal Ecobee developer API key** you registered before shared keys stopped working — see **[CONFIG.md — Cloud backend (legacy)](CONFIG.md#cloud-backend-legacy)**.

## Node info

1. **Controller** — **NodeServer Online** (process status)
2. **Controller** — **Ecobee Connection Status** (hub or cloud communication)
3. **Thermostat** (`n00x_t`) — **Connected**
4. **Main sensor** (`n00x_s`) — **Responding** (sensor inside thermostat)
5. **Remote sensor** (`n00x_rs`) — **Responding** (dead battery or out-of-range if false)

On **HomeKit** thermostats, connection semantics differ from cloud **Connected**; see **[CONFIG.md](CONFIG.md)** for controller **Ecobee Connection Status** and **HomeKit MQTT**.

## HomeKit thermostat controls

HomeKit nodes use a slimmer control set than cloud. The main schedule-related controls are **separate** in the IoX UI (not a combined multi-select):

| IoX control | Purpose |
|-------------|---------|
| **Climate Type** | Hold away / home / sleep / temp on the hub (four HAP slots). Extra comforts (Vacation, Away Extended, etc.) are commanded with matching **Heat Setpoint** / **Cool Setpoint** values when cached — see [CONFIG.md — HomeKit Climate Type](CONFIG.md#homekit-climate-type-commands-and-setpoints). |
| **Schedule Mode** | **Running** = resume programmed schedule (clear hold on hub); **Hold Next** / **Hold Indefinite** = IoX record only |

On hub connect and Node Server start, each HomeKit thermostat automatically runs a debounced hub snapshot (same as **Query**) to cache comfort setpoints for **Climate Type** commands.

Changing **Climate Type** or **Heat Setpoint** / **Cool Setpoint** places a hold and defaults to **Hold Next** unless you set **Schedule Mode** separately first. **Schedule Mode = Running** is the IoX action to resume the Ecobee schedule after a manual hold.

**Climate Type status (4.1.6+):** disambiguates **Vacation**, **Away Extended**, and other temp-slot comforts using setpoint signatures (not always catalog **Smart1**).

**Climate Type commands (4.1.7+):** for comforts that need explicit setpoints, the plugin writes **Heat Setpoint** / **Cool Setpoint** before the vendor hold. **Home / Away / Sleep** use the hold byte only.

Full detail: **[CONFIG.md — HomeKit Climate Type](CONFIG.md#homekit-climate-type-commands-and-setpoints)** · **[docs/HOMEKIT_GV3_SETPOINTS.md](docs/HOMEKIT_GV3_SETPOINTS.md)** · **[CONFIG.md — HomeKit thermostat node](CONFIG.md#homekit-thermostat-node-drivers-and-commands)**.

## Monitoring

See [Polyglot NodeServer monitoring](https://forum.universal-devices.com/topic/25016-polyglot-nodeserver-monitoring/) for heartbeats. Cloud installs can also check thermostat **Connected** for Ecobee server visibility.

## Upgrading

Store releases typically appear within about an hour of publish.

1. Open the Polyglot web UI → Dashboard → **Restart** the Node Server
2. If the release notes mention **Profile Change**, close and reopen the Admin Console (or **Load Profile**) if nodes look stale — recent HomeKit profile updates split **Climate Type** and **Schedule Mode** controls (profile **4.1.7**+).

## Changelog

**[CHANGELOG.md](CHANGELOG.md)**

## Advanced documentation

HomeKit control details, hold behavior, limitations vs cloud, and full parameter tables: **[CONFIG.md](CONFIG.md)**
