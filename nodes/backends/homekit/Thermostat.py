"""IoX thermostat node for HomeKit hub path (EcobeeHKF/EcobeeHKC drivers; hub read/write)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TYPE_CHECKING

from udi_interface import LOGGER, Node

from const import driversMap
from homekit_client import hap_apply
from node_funcs import get_valid_node_name

if TYPE_CHECKING:
    from .Controller import HomeKitBackend


class HomeKitThermostat(Node):
    """Thermostat child; *hk* is the active :class:`HomeKitBackend` instance.

    Uses nodedefs ``EcobeeHKC_*`` / ``EcobeeHKF_*`` (slim vs cloud ``EcobeeC_*`` / ``EcobeeF_*``):
    only drivers/commands supported via HomeKit. See README.
    """

    hint = '0x010c0100'

    def __init__(
        self,
        controller,
        primary: str,
        address: str,
        name: str,
        thermostat_id: str,
        use_celsius: bool,
        device_id_hub: str,
        hk: 'HomeKitBackend',
    ):
        self.controller = controller
        self.thermostat_id = thermostat_id
        self.device_id_hub = device_id_hub
        self.use_celsius = use_celsius
        self.hk = hk
        # Set True after HAP ``CurrentHeatingCoolingState`` value 3 is seen (extended 4-value encoding).
        self._hap_cur_hc_four_value = False
        self._hk_last_comfort_byte: int | None = None
        self._hk_sp_sig_to_gv3: dict[tuple[float, float], int] = {}
        self._hk_gv3_to_sp: dict[int, tuple[float, float]] = {}
        self._hk_vendor_comfort_sp: dict[str, tuple[float, float]] = {}
        self._hk_vendor_partial: dict[tuple[str, str], float] = {}
        base = 'EcobeeHKC' if use_celsius else 'EcobeeHKF'
        self.drivers = deepcopy(driversMap[base])
        self.id = f'{base}_{thermostat_id}'
        nm = get_valid_node_name(name)
        super().__init__(controller.poly, primary, address, nm)
        self.name = nm

    def set_driver_safe(self, driver: str, val: Any, report: bool = True) -> None:
        try:
            self.setDriver(driver, val, report=report, force=True)
        except Exception:
            LOGGER.debug('setDriver %s=%r failed for %s', driver, val, self.address, exc_info=True)

    def set_st(self, val: float) -> None:
        self.set_driver_safe('ST', val)

    def set_climd(self, val: int) -> None:
        self.set_driver_safe('CLIMD', int(val))

    def set_clihcs(self, val: int) -> None:
        self.set_driver_safe('CLIHCS', int(val))

    def set_clifs(self, val: int) -> None:
        self.set_driver_safe('CLIFS', int(val))

    def set_clifrs(self, val: int) -> None:
        self.set_driver_safe('CLIFRS', int(val))

    def set_clisph(self, val: float, from_hap_c: bool = True) -> None:
        _ = from_hap_c
        self.set_driver_safe('CLISPH', float(val))
        self.refresh_gv3_after_hk_setpoint()

    def set_clispc(self, val: float, from_hap_c: bool = True) -> None:
        _ = from_hap_c
        self.set_driver_safe('CLISPC', float(val))
        self.refresh_gv3_after_hk_setpoint()

    def _configured_climate_refs(self) -> list[str]:
        if self.hk:
            return self.hk.command_climate_refs_for(self.thermostat_id, self.device_id_hub)
        return []

    def hk_comfort_gv3_resolver(self, hub_byte: int) -> int:
        """Resolve IoX ``GV3`` from Ecobee HAP comfort byte (uses setpoints for Temp / byte 3)."""
        self._hk_last_comfort_byte = int(hub_byte)
        gv3 = self._resolve_hk_comfort_gv3()
        if int(hub_byte) == hap_apply.ECOBEE_HK_COMFORT_TEMP:
            self._remember_hk_comfort_signature(gv3)
        return gv3

    def refresh_gv3_after_hk_setpoint(self) -> None:
        if getattr(self, '_hk_last_comfort_byte', None) != hap_apply.ECOBEE_HK_COMFORT_TEMP:
            return
        gv3 = self._resolve_hk_comfort_gv3()
        self.set_driver_safe('GV3', gv3)

    def _resolve_hk_comfort_gv3(self) -> int:
        heat = cool = None
        try:
            heat = float(self.getDriver('CLISPH'))
            cool = float(self.getDriver('CLISPC'))
        except (TypeError, ValueError):
            pass
        hub_byte = self._hk_last_comfort_byte if self._hk_last_comfort_byte is not None else 0
        cache_in = getattr(self, '_hk_sp_sig_to_gv3', None) or {}
        gv3, cache = hap_apply.resolve_hk_comfort_gv3(
            hub_byte,
            heat_sp=heat,
            cool_sp=cool,
            configured_refs=self._configured_climate_refs(),
            sp_sig_to_gv3=cache_in,
        )
        self._hk_sp_sig_to_gv3 = cache
        return gv3

    def _remember_hk_comfort_signature(self, gv3: int) -> None:
        heat = cool = None
        try:
            heat = float(self.getDriver('CLISPH'))
            cool = float(self.getDriver('CLISPC'))
        except (TypeError, ValueError):
            return
        if heat is None or cool is None:
            return
        if not hasattr(self, '_hk_sp_sig_to_gv3'):
            self._hk_sp_sig_to_gv3 = {}
        if not hasattr(self, '_hk_gv3_to_sp'):
            self._hk_gv3_to_sp = {}
        self._hk_sp_sig_to_gv3[hap_apply.comfort_setpoint_key(heat, cool)] = int(gv3)
        self._hk_gv3_to_sp[int(gv3)] = (float(heat), float(cool))
        ref = hap_apply.gv3_to_comfort_ref(int(gv3), self._configured_climate_refs())
        if ref and self.hk:
            self.hk.persist_comfort_setpoint(
                self.thermostat_id,
                ref,
                float(heat),
                float(cool),
                device_id=self.device_id_hub,
            )

    def remember_hk_vendor_comfort_target(self, ref: str, band: str, hap_celsius: float) -> None:
        """Cache Ecobee vendor comfort target heat/cool from hub snapshot (home / sleep / away)."""
        r = str(ref or '').strip()
        b = str(band or '').strip().lower()
        if not r or b not in ('heat', 'cool'):
            return
        sp = hap_apply.driver_st_from_hap_celsius(self.use_celsius, float(hap_celsius))
        self._hk_vendor_partial[(r, b)] = float(sp)
        heat = self._hk_vendor_partial.get((r, 'heat'))
        cool = self._hk_vendor_partial.get((r, 'cool'))
        if heat is None or cool is None:
            return
        self._hk_vendor_comfort_sp[r] = (float(heat), float(cool))

    def _program_comfort_sp(self) -> dict[str, tuple[float, float]]:
        if self.hk:
            return self.hk.program_comfort_setpoints_for(self.thermostat_id)
        return {}

    def seed_comfort_setpoints_from_query(self) -> None:
        """After hub snapshot, seed GV3→setpoint cache from program + vendor targets."""
        from ecobee_program import seed_gv3_to_sp_from_comfort_maps
        from node_funcs import climateMap

        seed_gv3_to_sp_from_comfort_maps(
            self._hk_gv3_to_sp,
            program_sp=self._program_comfort_sp(),
            vendor_sp=self._hk_vendor_comfort_sp,
            climate_map=climateMap,
        )
        if getattr(self, '_hk_last_comfort_byte', None) == hap_apply.ECOBEE_HK_COMFORT_TEMP:
            gv3 = self._resolve_hk_comfort_gv3()
            self._remember_hk_comfort_signature(gv3)

    def _comfort_setpoints_for_gv3_command(self, gv3: int) -> tuple[float, float] | None:
        return hap_apply.resolve_gv3_comfort_setpoints(
            int(gv3),
            configured_refs=self._configured_climate_refs(),
            vendor_comfort_sp=self._hk_vendor_comfort_sp,
            program_comfort_sp=self._program_comfort_sp(),
            gv3_to_sp=self._hk_gv3_to_sp,
            sp_sig_to_gv3=self._hk_sp_sig_to_gv3,
        )

    def _hub_write_hold_setpoints(self, heat: float, cool: float) -> bool:
        """Write heat/cool thresholds for a comfort hold (auto and fixed-band modes)."""
        span = self._heat_cool_min_span()
        if cool < heat + span:
            cool = heat + span
        hv = hap_apply.iox_temp_to_hap_celsius(self, heat, fahrenheit_wire_bias='low')
        cv = hap_apply.iox_temp_to_hap_celsius(self, cool, fahrenheit_wire_bias='low')
        if self._hub_write(
            hap_apply.hap_name_heating_threshold(), hv
        ) and self._hub_write(hap_apply.hap_name_cooling_threshold(), cv):
            return True
        m = self._climd_write_mode()
        if m in (1, 4):
            return self._hub_write(hap_apply.hap_name_target_temperature(), hv)
        if m == 2:
            return self._hub_write(hap_apply.hap_name_target_temperature(), cv)
        return False

    def set_clismd(self, val: int) -> None:
        self.set_driver_safe('CLISMD', int(val))

    def _hold_type_from_cmd(self, cmd: dict, default: int = 1) -> int:
        """IoX optional ``HoldType`` on multi-select commands; default hold-next when omitted."""
        query = cmd.get('query') or {}
        raw = query.get('HoldType.uom25')
        if raw is None or raw == '':
            return default
        try:
            v = int(float(raw))
        except (TypeError, ValueError):
            return default
        return v if v in (1, 2) else default

    def _mark_hold_active(self, cmd: dict | None = None, hold_type: int | None = None) -> None:
        """Setpoint / comfort holds imply a manual hold; HAP does not expose hold duration."""
        if hold_type is None:
            hold_type = self._hold_type_from_cmd(cmd or {}, default=1)
        self.set_clismd(hold_type)

    def _hub_clear_hold(self) -> bool:
        """Resume programmed schedule via Ecobee vendor clear-hold button."""
        c = hap_apply.hap_name_vendor_ecobee_clear_hold()
        ok = True
        for val in hap_apply.vendor_ecobee_clear_hold_wire_values():
            if not self._hub_write(c, val):
                ok = False
        return ok

    def apply_hub_characteristic(self, characteristic: str, value: Any) -> bool:
        # Delegate to hap_apply (handles vendor UUIDs before :func:`classify` marks them UNKNOWN).
        return hap_apply.apply_characteristic_to_thermostat(self, characteristic, value, log=LOGGER)

    def query(self, cmd=None):
        if self.hk:
            self.hk.refresh_thermostat(self)
        self.reportDrivers()

    def _hub_write(self, hap_name: str, hap_value: Any) -> bool:
        if not self.hk:
            return False
        return self.hk.hub_command(self.device_id_hub, hap_name, hap_value)

    def _climd_write_mode(self) -> int:
        """IoX ``CLIMD`` for hub writes: 0 off, 1 heat, 2 cool, 3 auto, 4 aux."""
        try:
            return int(float(self.getDriver('CLIMD')))
        except (TypeError, ValueError):
            return 3

    def _heat_cool_min_span(self) -> float:
        """Minimum heat/cool separation when writing both thresholds (auto / CLIMD 3).

        HomeKit sends independent heating and cooling thresholds. Ecobee firmware enforces a
        **compressor minimum delta** (commonly **3 °F** in the app, user-configurable). If we
        only reserve **1 °F** here, writes succeed on the bus but the stat bumps the cooling
        setpoint (e.g. 72 → 73) when heat is 70 — see plugin debug logs vs physical display.

        Celsius thermostats: use ~**1.67 °C** (same as 3 °F) so both unit paths stay consistent.
        """
        return 5.0 / 3.0 if self.use_celsius else 3.0

    def _hap_char_for_heat_driver_write(self) -> str:
        """HAP name for **CLISPH** writes.

        **Auto** uses heating/cooling **thresholds**. **Heat / aux** use the single
        ``TEMPERATURE_TARGET`` (Ecobee rejects threshold writes in single-setpoint modes).
        **Cool** keeps the heat **threshold** (inactive band for auto).
        """
        m = self._climd_write_mode()
        if m == 3:
            return hap_apply.hap_name_heating_threshold()
        if m == 2:
            return hap_apply.hap_name_heating_threshold()
        return hap_apply.hap_name_target_temperature()

    def _hap_char_for_cool_driver_write(self) -> str:
        """HAP name for **CLISPC** writes (inverse of :meth:`_hap_char_for_heat_driver_write`)."""
        m = self._climd_write_mode()
        if m == 3:
            return hap_apply.hap_name_cooling_threshold()
        if m in (1, 4):
            return hap_apply.hap_name_cooling_threshold()
        return hap_apply.hap_name_target_temperature()

    def cmd_set_pf(self, cmd):
        driver = cmd.get('cmd')
        if driver == 'CLISPH':
            heat = float(cmd['value'])
            m = self._climd_write_mode()
            span = self._heat_cool_min_span()
            if m == 3:
                cool = float(self.getDriver('CLISPC'))
                if cool < heat + span:
                    cool = heat + span
                hv = hap_apply.iox_temp_to_hap_celsius(
                    self, heat, fahrenheit_wire_bias='low'
                )
                cv = hap_apply.iox_temp_to_hap_celsius(
                    self, cool, fahrenheit_wire_bias='low'
                )
                if self._hub_write(
                    hap_apply.hap_name_heating_threshold(), hv
                ) and self._hub_write(hap_apply.hap_name_cooling_threshold(), cv):
                    self.set_clisph(heat)
                    self.set_clispc(cool)
                    self._mark_hold_active(cmd)
                return
            c = self._hap_char_for_heat_driver_write()
            v = hap_apply.iox_temp_to_hap_celsius(
                self, heat, fahrenheit_wire_bias='low'
            )
            if self._hub_write(c, v):
                self.set_clisph(heat)
                self._mark_hold_active(cmd)
        elif driver == 'CLISPC':
            cool = float(cmd['value'])
            m = self._climd_write_mode()
            span = self._heat_cool_min_span()
            if m == 3:
                heat = float(self.getDriver('CLISPH'))
                if heat > cool - span:
                    heat = cool - span
                hv = hap_apply.iox_temp_to_hap_celsius(
                    self, heat, fahrenheit_wire_bias='low'
                )
                cv = hap_apply.iox_temp_to_hap_celsius(
                    self, cool, fahrenheit_wire_bias='low'
                )
                if self._hub_write(
                    hap_apply.hap_name_heating_threshold(), hv
                ) and self._hub_write(hap_apply.hap_name_cooling_threshold(), cv):
                    self.set_clisph(heat)
                    self.set_clispc(cool)
                    self._mark_hold_active(cmd)
                return
            c = self._hap_char_for_cool_driver_write()
            v = hap_apply.iox_temp_to_hap_celsius(
                self, cool, fahrenheit_wire_bias='low'
            )
            if self._hub_write(c, v):
                self.set_clispc(cool)
                self._mark_hold_active(cmd)
        elif driver == 'CLIFS':
            c = hap_apply.hap_name_target_fan_state()
            v = int(cmd['value'])
            hap_v = hap_apply.clifs_to_hap_fan_target(v)
            if self._hub_write(c, hap_v):
                self.set_clifs(v)

    def cmd_set_mode(self, cmd):
        v = hap_apply.climd_to_hap_target_mode(int(cmd['value']))
        name = hap_apply.hap_name_target_heating_cooling()
        if self._hub_write(name, v):
            self.set_climd(int(cmd['value']))

    def cmd_set_humidity(self, cmd):
        if self._hub_write('TargetRelativeHumidity', int(cmd['value'])):
            self.set_driver_safe('GV1', int(cmd['value']))

    def cmd_set_gv3(self, cmd):
        """Climate / comfort index: maps to Ecobee ``VENDOR_ECOBEE_SET_HOLD_SCHEDULE`` on the hub."""
        try:
            v = int(float(cmd['value']))
        except (KeyError, TypeError, ValueError):
            LOGGER.debug('cmd_set_gv3: bad value %r', cmd)
            return
        c = hap_apply.hap_name_vendor_ecobee_set_hold_schedule()
        hub_byte = hap_apply.gv3_to_ecobee_set_hold_schedule(v)
        comfort_sp = None
        if hap_apply.gv3_command_needs_setpoints(v):
            comfort_sp = self._comfort_setpoints_for_gv3_command(v)
            if comfort_sp is None:
                ref = hap_apply.gv3_to_comfort_ref(v, self._configured_climate_refs())
                LOGGER.info(
                    'HomeKit %s: GV3=%s (%s) needs comfort setpoints but none are cached yet; '
                    'run QUERY while the stat is on this comfort, or activate it once on the Ecobee '
                    'app so the plugin can learn heat/cool, then retry.',
                    self.address,
                    v,
                    ref or '?',
                )
                return
            if not self._hub_write_hold_setpoints(comfort_sp[0], comfort_sp[1]):
                return
        if self._hub_write(c, hub_byte):
            self._hk_last_comfort_byte = int(hub_byte)
            self.set_driver_safe('GV3', v)
            if comfort_sp is not None:
                self.set_driver_safe('CLISPH', comfort_sp[0])
                self.set_driver_safe('CLISPC', comfort_sp[1])
            self._remember_hk_comfort_signature(v)
            self._mark_hold_active(cmd)

    def cmd_set_schedule_mode(self, cmd):
        """Schedule mode: **CLISMD** 0 = resume program; 1/2 recorded locally only on HomeKit."""
        try:
            v = int(float(cmd['value']))
        except (KeyError, TypeError, ValueError):
            LOGGER.debug('cmd_set_schedule_mode: bad value %r', cmd)
            return
        try:
            cur = int(float(self.getDriver('CLISMD')))
        except (TypeError, ValueError):
            cur = None
        if cur == v:
            return
        if v == 0:
            if self._hub_clear_hold():
                self.set_clismd(0)
                if self.hk:
                    self.hk.schedule_thermostat_refresh_after_hold_clear(self)
            return
        self.set_clismd(v)
        LOGGER.info(
            'HomeKit %s: CLISMD=%s stored locally; hold-next/indefinite are not set via HAP. '
            'Use GV3 or setpoints to place a hold, or CLISMD=0 to resume the schedule.',
            self.address,
            v,
        )

    def set_point(self, cmd):
        step = float(cmd.get('value', 1))
        if cmd.get('cmd') == 'DIM':
            step = -step
        mode = int(self.getDriver('CLIMD'))
        if mode == 0:
            return
        h_c = hap_apply.hap_name_heating_threshold()
        c_c = hap_apply.hap_name_cooling_threshold()
        t_t = hap_apply.hap_name_target_temperature()
        min_span = self._heat_cool_min_span()
        if mode == 3:
            heat = float(self.getDriver('CLISPH')) + step
            cool = float(self.getDriver('CLISPC')) + step
            if cool < heat + min_span:
                cool = heat + min_span
            hv = hap_apply.iox_temp_to_hap_celsius(
                self, heat, fahrenheit_wire_bias='low'
            )
            cv = hap_apply.iox_temp_to_hap_celsius(
                self, cool, fahrenheit_wire_bias='low'
            )
            if self._hub_write(h_c, hv) and self._hub_write(c_c, cv):
                self.set_clisph(heat)
                self.set_clispc(cool)
                self._mark_hold_active(cmd)
            return
        if mode == 1 or mode == 4:
            cur = float(self.getDriver('CLISPH'))
            nxt = cur + step
            v = hap_apply.iox_temp_to_hap_celsius(
                self, nxt, fahrenheit_wire_bias='low'
            )
            if self._hub_write(t_t, v):
                self.set_clisph(nxt)
                self._mark_hold_active(cmd)
            return
        cur = float(self.getDriver('CLISPC'))
        nxt = cur + step
        v = hap_apply.iox_temp_to_hap_celsius(
            self, nxt, fahrenheit_wire_bias='low'
        )
        if self._hub_write(t_t, v):
            self.set_clispc(nxt)
            self._mark_hold_active(cmd)

    commands = {
        'QUERY': query,
        'CLISPH': cmd_set_pf,
        'CLISPC': cmd_set_pf,
        'CLIFS': cmd_set_pf,
        'CLIMD': cmd_set_mode,
        'GV1': cmd_set_humidity,
        'CLISMD': cmd_set_schedule_mode,
        'GV3': cmd_set_gv3,
        'BRT': set_point,
        'DIM': set_point,
    }
