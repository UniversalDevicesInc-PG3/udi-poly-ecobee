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
| **Climate Type** | Switch among configured comforts (Home, Away, Sleep, Smart1–Smart7, Vacation, etc.). Home / Sleep / Away use HAP hold bytes; others write cached setpoints then hold. |
| **Schedule Mode** | **Running** = resume programmed schedule (clear hold on hub); **Hold Next** / **Hold Indefinite** = IoX record only |

### HomeKit Climate Type (no cloud API)

HomeKit does **not** expose Ecobee comfort **names** (only a comfort byte plus current heat/cool). The plugin maps comforts using **Climate program labels** typed data:

1. Open the Ecobee Node Server → **Typed Data** → **Climate program labels**.
2. Find your thermostat row (e.g. thermostat id `001` for node `t001`).
3. Under nested **Comfort programs**, match each `climateRef` to your Ecobee app name:
   - `home` → **Home**
   - `away` → **Away**
   - `sleep` → **Sleep**
   - `smart1` → rename display name to your custom comfort (e.g. **Workshop**)
   - `smart2` … `smart7` for additional custom comforts
4. **Save** typed data — the plugin rebuilds the IoX profile and pushes it automatically; the **Climate Type** command list updates with your display names.

**Heat** and **Cool** columns on each comfort row are filled **automatically** when the plugin learns setpoints from the hub (Node Server start, **QUERY**, or while the stat is on that comfort). You do not need to type them in.

**How commands work**

| Comfort kind | Behavior |
|--------------|----------|
| Home, Away, Sleep | Vendor hold byte only (setpoints come from the hub program). |
| Custom (Smart1–Smart7, Vacation, …) | Plugin writes learned heat/cool to the hub, then places the hold. |

If a custom comfort has no cached setpoints yet, run **QUERY** while the thermostat is **on that comfort** in the Ecobee app, or switch to it once on the stat so the plugin can learn heat/cool. Then refresh the PG3 Config page and you should see the values.

On hub connect and Node Server start, each HomeKit thermostat automatically runs a debounced hub snapshot (same as **Query**) to cache comfort setpoints for **Climate Type** commands.

Changing **Climate Type** or **Heat Setpoint** / **Cool Setpoint** places a hold and defaults to **Hold Next** unless you set **Schedule Mode** separately first. **Schedule Mode = Running** is the IoX action to resume the Ecobee schedule after a manual hold.

**Heat/cool minimum delta (HomeKit):** In **Auto** mode the plugin keeps at least a configured gap between heat and cool setpoints before writing to the hub (Ecobee **compressor minimum delta**). Default is **3** degrees; if your Ecobee app uses **2**, set Custom Param **`hk_heat_cool_min_delta`** to **`2`** (in the stat's display units, °F or °C). See **[CONFIG.md](CONFIG.md#reference-custom-configuration-parameters)**.

**Climate Type status (4.1.6+):** disambiguates **Vacation**, **Away Extended**, and other temp-slot comforts using setpoint signatures (not always catalog **Smart1**).

**Climate Type commands (4.1.7+):** for comforts that need explicit setpoints, the plugin writes **Heat Setpoint** / **Cool Setpoint** before the vendor hold. **Home / Away / Sleep** use the hold byte only.

Full detail: **[CONFIG.md — HomeKit Climate Type](CONFIG.md#homekit-climate-type-commands-and-setpoints)** · **[docs/HOMEKIT_GV3_SETPOINTS.md](docs/HOMEKIT_GV3_SETPOINTS.md)** · **[CONFIG.md — HomeKit thermostat node](CONFIG.md#homekit-thermostat-node-drivers-and-commands)**.

## Monitoring

See [Polyglot NodeServer monitoring](https://forum.universal-devices.com/topic/25016-polyglot-nodeserver-monitoring/) for heartbeats. Cloud installs can also check thermostat **Connected** for Ecobee server visibility.

## Upgrading

Store releases typically appear within about an hour of publish.

1. Open the Polyglot web UI → Dashboard → **Restart** the Node Server
2. If the release notes mention **Profile Change**, close and reopen the Admin Console if nodes look stale — the Node Server pushes an updated profile on restart (profile **4.1.7**+ split **Climate Type** and **Schedule Mode**).

## Changelog

**[CHANGELOG.md](CHANGELOG.md)**

## Advanced documentation

HomeKit control details, hold behavior, limitations vs cloud, and full parameter tables: **[CONFIG.md](CONFIG.md)**
