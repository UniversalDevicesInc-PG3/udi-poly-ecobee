"""Apply HomeKit hub characteristic values to :class:`nodes.backends.homekit.Thermostat.HomeKitThermostat` drivers."""

from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

from node_funcs import climateMap, toF

from .char_map import CharBucket, classify, normalize_characteristic_label, normalize_hap_uuid

if TYPE_CHECKING:
    from nodes.backends.homekit.Thermostat import HomeKitThermostat

_LOG = logging.getLogger(__name__)

# aiohomekit ``CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE`` — Ecobee comfort index on the wire.
_ECOBEE_CURRENT_MODE_UUID_NORM = normalize_hap_uuid('B7DDB9A3-54BB-4572-91D2-F1F5B0510F8C')

# Ecobee HAP vendor comfort bytes (``VENDOR_ECOBEE_CURRENT_MODE`` / ``VENDOR_ECOBEE_SET_HOLD_SCHEDULE``):
# 0 = Home, 1 = Sleep, 2 = Away, 3 = Temp (thermostat “Temp” / custom comfort on the device).
# IoX ``GV3`` uses the same indices as cloud: ``node_funcs.climateMap`` / ``climateList`` order.
_ECOBEE_HK_COMFORT_HOME = 0
_ECOBEE_HK_COMFORT_SLEEP = 1
_ECOBEE_HK_COMFORT_AWAY = 2
_ECOBEE_HK_COMFORT_TEMP = 3

# Thermostat ``TargetFanState`` (HAP UUID …BF…). Ecobee uses **0 = On, 1 = Auto**; IoX ``CLIFS`` matches
# cloud ``fanMap`` (**auto = 0**, **on = 1**).
_HAP_TARGET_FAN_STATE_UUID_NORM = normalize_hap_uuid('000000BF-0000-1000-8000-0026BB765291')
_HAP_CURRENT_FAN_STATE_UUID_NORM = normalize_hap_uuid('000000AF-0000-1000-8000-0026BB765291')
_HAP_HEATING_COOLING_TARGET_UUID_NORM = normalize_hap_uuid('00000033-0000-1000-8000-0026BB765291')
_HAP_CURRENT_HEATING_COOLING_UUID_NORM = normalize_hap_uuid('0000000F-0000-1000-8000-0026BB765291')


def is_ecobee_current_mode_characteristic(characteristic: str) -> bool:
    """True for Ecobee vendor ``VENDOR_ECOBEE_CURRENT_MODE`` (name or UUID); value is remapped to IoX ``GV3``."""
    if not characteristic:
        return False
    if 'VENDOR_ECOBEE_CURRENT_MODE' in (characteristic or '').upper():
        return True
    nu = normalize_hap_uuid(characteristic)
    return bool(nu and nu == _ECOBEE_CURRENT_MODE_UUID_NORM)


def ecobee_hk_comfort_to_gv3(hub_byte: int) -> int:
    """Map Ecobee HAP comfort byte → IoX ``GV3`` (``climateMap`` index). Unknown high values pass through."""
    b = int(hub_byte)
    if b == _ECOBEE_HK_COMFORT_HOME:
        return int(climateMap['home'])
    if b == _ECOBEE_HK_COMFORT_SLEEP:
        return int(climateMap['sleep'])
    if b == _ECOBEE_HK_COMFORT_AWAY:
        return int(climateMap['away'])
    if b == _ECOBEE_HK_COMFORT_TEMP:
        return int(climateMap['smart1'])
    return b


def gv3_to_ecobee_set_hold_schedule(gv3: int) -> int:
    """Map IoX ``GV3`` → Ecobee ``VENDOR_ECOBEE_SET_HOLD_SCHEDULE`` byte (HAP **0–3** only).

    IoX uses full ``climateList`` indices (e.g. ``vacation`` = 10). Values outside 0–3 were
    previously forwarded as-is and the accessory rejected them (**-70410** invalid write).
    """
    g = int(gv3)
    if g == int(climateMap['home']):
        return _ECOBEE_HK_COMFORT_HOME
    if g == int(climateMap['sleep']):
        return _ECOBEE_HK_COMFORT_SLEEP
    if g == int(climateMap['away']):
        return _ECOBEE_HK_COMFORT_AWAY
    if g == int(climateMap['smart1']):
        return _ECOBEE_HK_COMFORT_TEMP
    for name in ('smart2', 'smart3', 'smart4', 'smart5', 'smart6', 'smart7'):
        if g == int(climateMap[name]):
            return _ECOBEE_HK_COMFORT_TEMP
    if g == int(climateMap['vacation']):
        return _ECOBEE_HK_COMFORT_AWAY
    if g == int(climateMap['smartAway']):
        return _ECOBEE_HK_COMFORT_AWAY
    if g == int(climateMap['smartHome']):
        return _ECOBEE_HK_COMFORT_HOME
    if g == int(climateMap['demandResponse']):
        return _ECOBEE_HK_COMFORT_AWAY
    if g == int(climateMap['unknown']):
        return _ECOBEE_HK_COMFORT_TEMP
    if g == int(climateMap['wakeup']):
        return _ECOBEE_HK_COMFORT_HOME
    _LOG.debug(
        'gv3_to_ecobee_set_hold_schedule: GV3=%s not in climateMap hold mapping; using TEMP (3)',
        g,
    )
    return _ECOBEE_HK_COMFORT_TEMP


def hap_target_fan_state_to_clifs(hap_val: int) -> int:
    """HAP ``TargetFanState`` (Ecobee: 0 = On, 1 = Auto) → IoX ``CLIFS`` (cloud ``fanMap``: auto = 0, on = 1)."""
    v = int(hap_val)
    if v == 1:
        return 0
    if v == 0:
        return 1
    return v


def clifs_to_hap_fan_target(clifs: int) -> int:
    """IoX ``CLIFS`` → HAP ``TargetFanState`` (inverse of :func:`hap_target_fan_state_to_clifs`)."""
    v = int(clifs)
    if v == 0:
        return 1
    if v == 1:
        return 0
    return v


# HAP TargetHeatingCoolingMode / HeatingCoolingTarget style values → IoX CLIMD (subset 0–4).
_HAP_MODE_TO_CLIMD = {0: 0, 1: 1, 2: 2, 3: 3}


def hap_current_heating_cooling_to_clihcs(v: int, *, four_value_encoding: bool) -> int:
    """
    Map HAP ``CurrentHeatingCoolingState`` / ``HEATING_COOLING_CURRENT`` → IoX ``CLIHCS``
    (``EN_ECOHCS``: 0 Idle, 1 Heat, 2 Cool, …).

    **Standard HAP** (Apple thermostat, Ecobee): 0 = Off, 1 = Heat, 2 = Cool. Some stacks send
    3 as an alias for Cool — treat as Cool.

    **Extended** (rare): 0 = Off, 1 = Idle, 2 = Heat, 3 = Cool. When *four_value_encoding* is
    True (we observed value 3 at least once on this node), use this mapping.
    """
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    if n < 0:
        return 0
    if four_value_encoding:
        return {0: 0, 1: 0, 2: 1, 3: 2}.get(n, 0)
    if n >= 3:
        return 2
    return {0: 0, 1: 1, 2: 2}.get(n, 0)


def hap_current_fan_state_to_clifrs(v: int) -> int:
    """HAP ``CurrentFanState``: 0 Inactive, 1 Idle, 2 Blowing → IoX ``CLIFRS`` (editor subset 0/1)."""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    return 1 if n >= 2 else 0


def driver_st_from_hap_celsius(use_celsius: bool, celsius: float) -> float:
    if use_celsius:
        return round(float(celsius) * 2) / 2
    return float(toF(float(celsius)))


def _driver_st_to_hap_c(node: 'HomeKitThermostat', driver_val: float) -> float:
    if node.use_celsius:
        return float(driver_val)
    return (float(driver_val) - 32) / 1.8


def _climd_mode(node: 'HomeKitThermostat') -> int:
    """IoX CLIMD: 0 off, 1 heat, 2 cool, 3 auto, 4 aux; default auto if unknown."""
    try:
        raw = node.getDriver('CLIMD')
        if raw is None:
            return 3
        return int(float(raw))
    except (TypeError, ValueError):
        return 3


def apply_characteristic_to_thermostat(
    node: 'HomeKitThermostat',
    characteristic: str,
    value: Any,
    *,
    log: Optional[logging.Logger] = None,
) -> bool:
    """
    Map one HAP characteristic to IoX drivers. Returns True if *characteristic* was handled
    (including INFORMATIONAL / unknown no-ops that were classified).
    """
    lg = log or _LOG
    # Vendor UUID is not in :func:`classify` mapped table → ``UNKNOWN``; handle before classify.
    if value is not None and is_ecobee_current_mode_characteristic(characteristic):
        try:
            raw = int(value)
        except (TypeError, ValueError):
            try:
                raw = int(float(value))
            except (TypeError, ValueError):
                return True
        node.set_driver_safe('GV3', ecobee_hk_comfort_to_gv3(raw))
        return True

    bucket = classify(characteristic, 0)
    if bucket == CharBucket.UNKNOWN:
        return False
    if bucket == CharBucket.INFORMATIONAL:
        return True
    if value is None:
        return True

    norm = normalize_characteristic_label(characteristic or '')
    nu_chr = normalize_hap_uuid(characteristic or '')

    try:
        if 'CURRENT_TEMPERATURE' in norm or norm.endswith('TEMPERATURE_CURRENT'):
            node.set_st(driver_st_from_hap_celsius(node.use_celsius, float(value)))
            return True
        if (
            nu_chr == _HAP_CURRENT_HEATING_COOLING_UUID_NORM
            or 'CURRENT_HEATING_COOLING' in norm
            or 'HEATING_COOLING_CURRENT' in norm
        ):
            try:
                v = int(value)
            except (TypeError, ValueError):
                v = int(float(value))
            if v == 3:
                try:
                    setattr(node, '_hap_cur_hc_four_value', True)
                except Exception:
                    pass
            four = bool(getattr(node, '_hap_cur_hc_four_value', False))
            node.set_clihcs(hap_current_heating_cooling_to_clihcs(v, four_value_encoding=four))
            return True
        if (
            nu_chr == _HAP_HEATING_COOLING_TARGET_UUID_NORM
            or 'HEATING_COOLING_TARGET' in norm
            or 'TARGET_HEATING_COOLING' in norm
            or ('HEATING_COOLING' in norm and 'CURRENT' not in norm)
        ):
            try:
                v = int(value)
            except (TypeError, ValueError):
                v = int(float(value))
            node.set_climd(_HAP_MODE_TO_CLIMD.get(v, v))
            return True
        if 'HEATING_THRESHOLD' in norm or 'HEAT_TARGET' in norm:
            node.set_clisph(driver_st_from_hap_celsius(node.use_celsius, float(value)), from_hap_c=False)
            return True
        if 'COOLING_THRESHOLD' in norm or 'COOL_TARGET' in norm:
            node.set_clispc(driver_st_from_hap_celsius(node.use_celsius, float(value)), from_hap_c=False)
            return True
        if (
            ('TARGET_TEMPERATURE' in norm or 'TEMPERATURE_TARGET' in norm)
            and 'THRESHOLD' not in norm
        ):
            # TargetTemperature / TEMPERATURE_TARGET: in **Auto** (CLIMD 3), Ecobee still emits this
            # alongside separate heating/cooling thresholds. Mirroring the target to *both* IoX
            # setpoints desyncs one side when the hub sends TargetTemperature and only one threshold
            # afterward (see logs: cool stuck at ~73°F while heat updates to 70°F).
            mode = _climd_mode(node)
            if mode == 3:
                return True
            t = driver_st_from_hap_celsius(node.use_celsius, float(value))
            if mode in (1, 4):
                node.set_clisph(t, from_hap_c=False)
                return True
            if mode == 2:
                node.set_clispc(t, from_hap_c=False)
                return True
            return True
        if 'RELATIVE_HUMIDITY' in norm and 'TARGET' in norm:
            node.set_driver_safe('GV1', int(round(float(value))))
            return True
        if 'RELATIVE_HUMIDITY' in norm:
            node.set_driver_safe('CLIHUM', int(round(float(value))))
            return True
        if (
            nu_chr == _HAP_TARGET_FAN_STATE_UUID_NORM
            or 'TARGET_FAN' in norm
            or ('FAN' in norm and 'TARGET' in norm)
        ):
            try:
                v = int(value)
            except (TypeError, ValueError):
                v = int(float(value))
            node.set_clifs(hap_target_fan_state_to_clifs(v))
            return True
        if (
            nu_chr == _HAP_CURRENT_FAN_STATE_UUID_NORM
            or 'CURRENT_FAN' in norm
            or ('FAN' in norm and 'CURRENT' in norm)
        ):
            try:
                v = int(value)
            except (TypeError, ValueError):
                v = int(float(value))
            node.set_clifrs(hap_current_fan_state_to_clifrs(v))
            return True
    except Exception:
        lg.debug('hap_apply failed for %s=%r', characteristic, value, exc_info=True)
        return True

    lg.debug('MAPPED but unhandled characteristic %s norm=%s', characteristic, norm)
    return True


def iox_temp_to_hap_celsius(
    node: 'HomeKitThermostat',
    driver_val: float,
    *,
    fahrenheit_wire_bias: Optional[str] = None,
) -> float:
    """IoX thermostat temp driver → HAP **celsius** for ``put_characteristics``.

    Round to **0.1 °C** so accessories (e.g. Ecobee) do not reject long binary floats (-70410).

    **Fahrenheit** (``EcobeeHKF``): naive rounding of :math:`(F-32)/1.8` can land **just above**
    the target whole °F on the wire (e.g. **75 °F → 23.9 °C → 75.02 °F** exact). Ecobee’s UI
    then rounds **up**, so the user sees **76 °F** while IoX sent **75**. Mitigate by choosing a
    0.1 °C bin that still maps back to the same whole °F via :func:`node_funcs.toF` (used on
    inbound HAP). In practice the **lowest** compatible bin is safest for Ecobee display parity;
    the optional **high** bias is kept available for troubleshooting / alternate accessories.
    """
    if node.use_celsius:
        c = float(driver_val)
        return round(float(c) * 10.0) / 10.0

    if fahrenheit_wire_bias in ('low', 'high'):
        t = int(round(float(driver_val)))
        k0 = int(round((float(driver_val) - 32) / 1.8 * 10.0))
        bins = []
        for dk in range(-40, 41):
            c = (k0 + dk) / 10.0
            if toF(c) != t:
                continue
            bins.append(c)
        if bins:
            return min(bins) if fahrenheit_wire_bias == 'low' else max(bins)

    c = _driver_st_to_hap_c(node, driver_val)
    return round(float(c) * 10.0) / 10.0


def climd_to_hap_target_mode(climd: int) -> int:
    return int(climd) if int(climd) in (0, 1, 2, 3) else 0


# aiohomekit ``CharacteristicsTypes`` attribute names for hub ``command`` / ``get`` (or a HAP UUID).
# udi-poly-homekit resolves these via ``hasattr(CharacteristicsTypes, spec)`` — not Apple PascalCase.
def hap_name_target_heating_cooling() -> str:
    return 'HEATING_COOLING_TARGET'


def hap_name_target_temperature() -> str:
    return 'TEMPERATURE_TARGET'


def hap_name_heating_threshold() -> str:
    return 'TEMPERATURE_HEATING_THRESHOLD'


def hap_name_cooling_threshold() -> str:
    return 'TEMPERATURE_COOLING_THRESHOLD'


def hap_name_target_fan_state() -> str:
    return 'FAN_STATE_TARGET'


def hap_name_vendor_ecobee_set_hold_schedule() -> str:
    """Ecobee vendor: request a comfort / schedule hold (uint8 index). Writable via HomeKit."""
    return 'VENDOR_ECOBEE_SET_HOLD_SCHEDULE'


def hap_name_vendor_ecobee_current_mode() -> str:
    """Ecobee vendor: current comfort / program index (``GV3``). Readable via hub ``get`` / snapshot."""
    return 'VENDOR_ECOBEE_CURRENT_MODE'


def hap_name_vendor_ecobee_clear_hold() -> str:
    """Ecobee vendor: cancel manual hold and resume the programmed schedule (HAP button)."""
    return 'VENDOR_ECOBEE_CLEAR_HOLD'


def vendor_ecobee_clear_hold_wire_values() -> tuple[bool, ...]:
    """Wire values for :func:`hap_name_vendor_ecobee_clear_hold`.

    Ecobee often ignores a lone ``true`` press; ``false`` then ``true`` matches Home Assistant's
    proven HomeKit controller sequence and reliably clears the hold.
    """
    return (False, True)


def apply_characteristic_to_sensor(
    node: Any,
    characteristic: str,
    value: Any,
    *,
    log: Optional[logging.Logger] = None,
) -> bool:
    """Map HAP values to EcobeeSensorF/C (or HF/HC) drivers."""
    lg = log or _LOG
    bucket = classify(characteristic, 0)
    if bucket == CharBucket.UNKNOWN:
        return False
    if bucket == CharBucket.INFORMATIONAL:
        return True
    if value is None:
        return True
    norm = normalize_characteristic_label(characteristic or '')
    try:
        if 'CURRENT_TEMPERATURE' in norm or norm.endswith('TEMPERATURE_CURRENT'):
            node.set_driver_safe('ST', driver_st_from_hap_celsius(node.use_celsius, float(value)))
            node.set_driver_safe('GV2', 1)
            return True
        if 'RELATIVE_HUMIDITY' in norm and 'TARGET' not in norm:
            node.set_driver_safe('CLIHUM', int(round(float(value))))
            return True
        if 'OCCUPANCY' in norm or 'MOTION_DETECTED' in norm:
            node.set_driver_safe('GV1', 1 if value else 0)
            return True
        if 'BATTERY_LEVEL' in norm:
            node.set_driver_safe('BATLVL', int(round(float(value))))
            return True
        if 'STATUS_LO_BATT' in norm or 'STATUS_LOW_BATTERY' in norm:
            node.set_driver_safe('BATLOW', 1 if value else 0)
            return True
    except Exception:
        lg.debug('sensor hap_apply failed for %s=%r', characteristic, value, exc_info=True)
        return True
    return True
