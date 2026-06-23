"""homekit_client.hap_apply unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from homekit_client.hap_apply import (
    ECOBEE_HK_COMFORT_TEMP,
    apply_characteristic_to_thermostat,
    clifs_to_hap_fan_target,
    gv3_command_needs_setpoints,
    gv3_to_comfort_ref,
    gv3_to_ecobee_set_hold_schedule,
    hap_current_fan_state_to_clifrs,
    hap_current_heating_cooling_to_clihcs,
    iox_temp_to_hap_celsius,
    parse_ecobee_vendor_comfort_target,
    resolve_gv3_comfort_setpoints,
    resolve_hk_comfort_gv3,
)
from node_funcs import climateMap


def test_apply_ecobee_vendor_current_mode_maps_comfort_to_gv3():
    """Hub comfort bytes 0–3 map to the same ``GV3`` indices as cloud ``climateMap``."""
    node = MagicMock()
    node.use_celsius = False
    u = 'B7DDB9A3-54BB-4572-91D2-F1F5B0510F8C'
    assert apply_characteristic_to_thermostat(node, u, 0) is True
    node.set_driver_safe.assert_called_once_with('GV3', climateMap['home'])


def test_apply_ecobee_vendor_current_mode_away_maps_to_climate_index():
    node = MagicMock()
    node.use_celsius = False
    assert apply_characteristic_to_thermostat(node, 'VENDOR_ECOBEE_CURRENT_MODE', 2) is True
    node.set_driver_safe.assert_called_once_with('GV3', climateMap['away'])


def test_apply_ecobee_vendor_current_mode_passes_through_unknown_index():
    node = MagicMock()
    node.use_celsius = False
    assert apply_characteristic_to_thermostat(node, 'VENDOR_ECOBEE_CURRENT_MODE', 7) is True
    node.set_driver_safe.assert_called_once_with('GV3', 7)


def test_apply_heating_cooling_current_sets_clihcs():
    """Standard HAP: 2 = Cool → IoX CLIHCS 2 (not Heat)."""
    node = MagicMock()
    node.use_celsius = False
    node._hap_cur_hc_four_value = False
    assert apply_characteristic_to_thermostat(node, 'HEATING_COOLING_CURRENT', 2) is True
    node.set_clihcs.assert_called_once_with(2)


def test_apply_heating_cooling_current_by_uuid_sets_clihcs():
    node = MagicMock()
    node.use_celsius = False
    node._hap_cur_hc_four_value = False
    u = '0000000F-0000-1000-8000-0026BB765291'
    assert apply_characteristic_to_thermostat(node, u, 2) is True
    node.set_clihcs.assert_called_once_with(2)


def test_hap_current_heating_cooling_three_value():
    assert hap_current_heating_cooling_to_clihcs(0, four_value_encoding=False) == 0
    assert hap_current_heating_cooling_to_clihcs(1, four_value_encoding=False) == 1
    assert hap_current_heating_cooling_to_clihcs(2, four_value_encoding=False) == 2
    assert hap_current_heating_cooling_to_clihcs(3, four_value_encoding=False) == 2


def test_hap_current_heating_cooling_four_value():
    assert hap_current_heating_cooling_to_clihcs(1, four_value_encoding=True) == 0
    assert hap_current_heating_cooling_to_clihcs(2, four_value_encoding=True) == 1
    assert hap_current_heating_cooling_to_clihcs(3, four_value_encoding=True) == 2


def test_hap_current_fan_state_to_clifrs_binary():
    assert hap_current_fan_state_to_clifrs(0) == 0
    assert hap_current_fan_state_to_clifrs(1) == 0
    assert hap_current_fan_state_to_clifrs(2) == 1


def test_apply_current_fan_state_maps_blowing_to_on():
    node = MagicMock()
    node.use_celsius = False
    assert apply_characteristic_to_thermostat(node, 'FAN_STATE_CURRENT', 2) is True
    node.set_clifrs.assert_called_once_with(1)


def test_apply_heating_cooling_target_by_uuid_sets_climd():
    node = MagicMock()
    node.use_celsius = False
    u = '00000033-0000-1000-8000-0026BB765291'
    assert apply_characteristic_to_thermostat(node, u, 3) is True
    node.set_climd.assert_called_once_with(3)


def test_apply_temperature_target_auto_does_not_mirror_both_setpoints():
    """In Auto (CLIMD 3), TargetTemperature must not overwrite both thresholds (Ecobee sends heat/cool separately)."""
    node = MagicMock()
    node.use_celsius = False
    node.getDriver.return_value = 3
    assert apply_characteristic_to_thermostat(node, 'TEMPERATURE_TARGET', 20.0) is True
    node.set_clisph.assert_not_called()
    node.set_clispc.assert_not_called()


def test_apply_temperature_target_heat_sets_heat_only():
    node = MagicMock()
    node.use_celsius = False
    node.getDriver.return_value = 1
    assert apply_characteristic_to_thermostat(node, 'TEMPERATURE_TARGET', 20.0) is True
    node.set_clisph.assert_called_once()
    node.set_clispc.assert_not_called()


def test_apply_temperature_target_cool_sets_cool_only():
    node = MagicMock()
    node.use_celsius = False
    node.getDriver.return_value = 2
    assert apply_characteristic_to_thermostat(node, 'TEMPERATURE_TARGET', 20.0) is True
    node.set_clispc.assert_called_once()
    node.set_clisph.assert_not_called()


def test_iox_temp_to_hap_fahrenheit_low_bias_picks_min_tenth_c():
    """Cooling: lowest 0.1 °C bin with same ``toF`` as target (avoids Ecobee UI +1 °F)."""
    node = MagicMock()
    node.use_celsius = False
    assert iox_temp_to_hap_celsius(node, 72, fahrenheit_wire_bias='low') == 22.0
    assert iox_temp_to_hap_celsius(node, 75, fahrenheit_wire_bias='low') == 23.7
    assert iox_temp_to_hap_celsius(node, 74, fahrenheit_wire_bias='low') == 23.1
    assert iox_temp_to_hap_celsius(node, 73, fahrenheit_wire_bias='low') == 22.6


def test_iox_temp_to_hap_fahrenheit_high_bias_picks_max_tenth_c():
    node = MagicMock()
    node.use_celsius = False
    assert iox_temp_to_hap_celsius(node, 75, fahrenheit_wire_bias='high') == 24.1


def test_iox_temp_to_hap_celsius_rounds_driver_to_tenth():
    node = MagicMock()
    node.use_celsius = True
    assert iox_temp_to_hap_celsius(node, 20.15, fahrenheit_wire_bias='low') == 20.2


def test_apply_target_fan_state_maps_to_cloud_clifs():
    """HAP TargetFanState (1 = Auto) → IoX CLIFS 0 (auto per ``fanMap``)."""
    node = MagicMock()
    node.use_celsius = False
    assert apply_characteristic_to_thermostat(node, 'TargetFanState', 1) is True
    node.set_clifs.assert_called_once_with(0)


def test_apply_target_fan_state_by_uuid_maps_fan():
    node = MagicMock()
    node.use_celsius = False
    u = '000000BF-0000-1000-8000-0026BB765291'
    assert apply_characteristic_to_thermostat(node, u, 0) is True
    node.set_clifs.assert_called_once_with(1)


def test_gv3_to_ecobee_set_hold_schedule_round_trip_home():
    g = climateMap['home']
    assert gv3_to_ecobee_set_hold_schedule(g) == 0


def test_gv3_to_ecobee_set_hold_schedule_vacation_maps_to_hap_away():
    """``vacation`` (GV3 10) must not be sent as wire 10 — HAP allows only 0–3 (-70410)."""
    assert gv3_to_ecobee_set_hold_schedule(climateMap['vacation']) == 2


def test_gv3_to_ecobee_set_hold_schedule_smart_away_maps_to_hap_away():
    assert gv3_to_ecobee_set_hold_schedule(climateMap['smartAway']) == 2


def test_gv3_to_ecobee_set_hold_schedule_smart2_maps_to_hap_temp():
    assert gv3_to_ecobee_set_hold_schedule(climateMap['smart2']) == 3


def test_gv3_to_ecobee_set_hold_schedule_unknown_high_maps_to_temp():
    assert gv3_to_ecobee_set_hold_schedule(99) == 3


def test_clifs_to_hap_fan_auto_is_one():
    assert clifs_to_hap_fan_target(0) == 1


def test_resolve_hk_temp_mode_maps_vacation_and_smartaway_by_setpoints():
    """Office-style comforts: vacation (50/85) and Away Extended / smartAway (45/85) share HAP byte 3."""
    refs = ('home', 'away', 'sleep', 'vacation', 'smartAway')
    gv_vac, cache = resolve_hk_comfort_gv3(
        ECOBEE_HK_COMFORT_TEMP,
        heat_sp=50.0,
        cool_sp=85.0,
        configured_refs=refs,
    )
    assert gv_vac == climateMap['vacation']
    gv_ext, cache = resolve_hk_comfort_gv3(
        ECOBEE_HK_COMFORT_TEMP,
        heat_sp=45.0,
        cool_sp=85.0,
        configured_refs=refs,
        sp_sig_to_gv3=cache,
    )
    assert gv_ext == climateMap['smartAway']


def test_resolve_hk_temp_mode_reuses_learned_signature():
    refs = ('home', 'away', 'sleep', 'vacation', 'smartAway')
    cache = {(50.0, 85.0): climateMap['vacation']}
    gv, out = resolve_hk_comfort_gv3(
        ECOBEE_HK_COMFORT_TEMP,
        heat_sp=50.0,
        cool_sp=85.0,
        configured_refs=refs,
        sp_sig_to_gv3=cache,
    )
    assert gv == climateMap['vacation']
    assert out == cache


def test_resolve_hk_home_byte_ignores_setpoints():
    gv, cache = resolve_hk_comfort_gv3(0, heat_sp=45.0, cool_sp=85.0, configured_refs=('home',))
    assert gv == climateMap['home']
    assert cache == {}


def test_parse_ecobee_vendor_comfort_target_home_heat():
    assert parse_ecobee_vendor_comfort_target('VENDOR_ECOBEE_HOME_TARGET_HEAT') == ('home', 'heat')


def test_gv3_command_needs_setpoints_for_temp_and_vacation():
    assert gv3_command_needs_setpoints(climateMap['smart1']) is True
    assert gv3_command_needs_setpoints(climateMap['vacation']) is True
    assert gv3_command_needs_setpoints(climateMap['home']) is False


def test_gv3_to_comfort_ref_maps_hk_slot_three_to_first_extra():
    refs = ('home', 'away', 'sleep', 'vacation', 'smartAway')
    assert gv3_to_comfort_ref(climateMap['smart1'], refs) == 'vacation'


def test_resolve_gv3_comfort_setpoints_uses_vendor_cache():
    sp = resolve_gv3_comfort_setpoints(
        climateMap['home'],
        configured_refs=('home', 'away', 'sleep'),
        vendor_comfort_sp={'home': (71.0, 76.0)},
    )
    assert sp == (71.0, 76.0)


def test_resolve_gv3_comfort_setpoints_uses_program_cache():
    sp = resolve_gv3_comfort_setpoints(
        climateMap['smart1'],
        configured_refs=('home', 'away', 'sleep', 'smart1'),
        program_comfort_sp={'smart1': (73.0, 78.0)},
    )
    assert sp == (73.0, 78.0)


def test_resolve_gv3_comfort_setpoints_hk_slot_finds_learned_vacation():
    refs = ('home', 'away', 'sleep', 'vacation', 'smartAway')
    cache = {(50.0, 85.0): climateMap['vacation']}
    sp = resolve_gv3_comfort_setpoints(
        climateMap['smart1'],
        configured_refs=refs,
        sp_sig_to_gv3=cache,
    )
    assert sp == (50.0, 85.0)


def test_apply_vendor_home_target_heat_caches_on_node():
    node = MagicMock()
    node.use_celsius = False
    node.remember_hk_vendor_comfort_target = MagicMock()
    type(node).__name__ = 'HomeKitThermostat'
    assert apply_characteristic_to_thermostat(node, 'VENDOR_ECOBEE_HOME_TARGET_HEAT', 21.8) is True
    node.remember_hk_vendor_comfort_target.assert_called_once_with('home', 'heat', 21.8)
