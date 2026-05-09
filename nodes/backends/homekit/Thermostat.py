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

    def set_clispc(self, val: float, from_hap_c: bool = True) -> None:
        _ = from_hap_c
        self.set_driver_safe('CLISPC', float(val))

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
                    self, heat, fahrenheit_wire_bias='high'
                )
                cv = hap_apply.iox_temp_to_hap_celsius(
                    self, cool, fahrenheit_wire_bias='low'
                )
                if self._hub_write(
                    hap_apply.hap_name_heating_threshold(), hv
                ) and self._hub_write(hap_apply.hap_name_cooling_threshold(), cv):
                    self.set_clisph(heat)
                    self.set_clispc(cool)
                return
            c = self._hap_char_for_heat_driver_write()
            v = hap_apply.iox_temp_to_hap_celsius(
                self, heat, fahrenheit_wire_bias='high'
            )
            if self._hub_write(c, v):
                self.set_clisph(heat)
        elif driver == 'CLISPC':
            cool = float(cmd['value'])
            m = self._climd_write_mode()
            span = self._heat_cool_min_span()
            if m == 3:
                heat = float(self.getDriver('CLISPH'))
                if heat > cool - span:
                    heat = cool - span
                hv = hap_apply.iox_temp_to_hap_celsius(
                    self, heat, fahrenheit_wire_bias='high'
                )
                cv = hap_apply.iox_temp_to_hap_celsius(
                    self, cool, fahrenheit_wire_bias='low'
                )
                if self._hub_write(
                    hap_apply.hap_name_heating_threshold(), hv
                ) and self._hub_write(hap_apply.hap_name_cooling_threshold(), cv):
                    self.set_clisph(heat)
                    self.set_clispc(cool)
                return
            c = self._hap_char_for_cool_driver_write()
            v = hap_apply.iox_temp_to_hap_celsius(
                self, cool, fahrenheit_wire_bias='low'
            )
            if self._hub_write(c, v):
                self.set_clispc(cool)
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
        if self._hub_write(c, hub_byte):
            self.set_driver_safe('GV3', v)

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
                self, heat, fahrenheit_wire_bias='high'
            )
            cv = hap_apply.iox_temp_to_hap_celsius(
                self, cool, fahrenheit_wire_bias='low'
            )
            if self._hub_write(h_c, hv) and self._hub_write(c_c, cv):
                self.set_clisph(heat)
                self.set_clispc(cool)
            return
        if mode == 1 or mode == 4:
            cur = float(self.getDriver('CLISPH'))
            nxt = cur + step
            v = hap_apply.iox_temp_to_hap_celsius(
                self, nxt, fahrenheit_wire_bias='high'
            )
            if self._hub_write(t_t, v):
                self.set_clisph(nxt)
            return
        cur = float(self.getDriver('CLISPC'))
        nxt = cur + step
        v = hap_apply.iox_temp_to_hap_celsius(
            self, nxt, fahrenheit_wire_bias='low'
        )
        if self._hub_write(t_t, v):
            self.set_clispc(nxt)

    commands = {
        'QUERY': query,
        'CLISPH': cmd_set_pf,
        'CLISPC': cmd_set_pf,
        'CLIFS': cmd_set_pf,
        'CLIMD': cmd_set_mode,
        'GV1': cmd_set_humidity,
        'GV3': cmd_set_gv3,
        'BRT': set_point,
        'DIM': set_point,
    }
