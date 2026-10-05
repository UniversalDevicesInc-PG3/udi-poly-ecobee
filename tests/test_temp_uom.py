"""Celsius / Fahrenheit IoX driver UOM helpers."""

from __future__ import annotations

from copy import deepcopy

from const import (
    UOM_CELSIUS,
    UOM_FAHRENHEIT,
    UOM_TSTAT_MODE,
    driver_uom_from_list,
    driversMap,
    restore_template_uoms,
    temperature_uom,
)
from types import SimpleNamespace
from unittest.mock import MagicMock

from nodes.backends.homekit.Controller import HomeKitBackend
from nodes.backends.homekit.Sensor import HomeKitSensor
from nodes.backends.homekit.Thermostat import HomeKitThermostat


def _uoms(key: str) -> dict[str, str]:
    return {d['driver']: str(d['uom']) for d in driversMap[key]}


def test_celsius_thermostat_maps_use_uom_4_and_mode_67():
    for key in ('EcobeeC', 'EcobeeHKC', 'EcobeewAQC'):
        u = _uoms(key)
        assert u['ST'] == UOM_CELSIUS
        assert u['CLISPH'] == UOM_CELSIUS
        assert u['CLISPC'] == UOM_CELSIUS
        assert u['CLIMD'] == UOM_TSTAT_MODE


def test_fahrenheit_thermostat_maps_use_uom_17():
    for key in ('EcobeeF', 'EcobeeHKF', 'EcobeewAQF'):
        u = _uoms(key)
        assert u['ST'] == UOM_FAHRENHEIT
        assert u['CLISPH'] == UOM_FAHRENHEIT
        assert u['CLISPC'] == UOM_FAHRENHEIT
        assert u['CLIMD'] == UOM_TSTAT_MODE


def test_temperature_uom_helper():
    assert temperature_uom(True) == UOM_CELSIUS
    assert temperature_uom(False) == UOM_FAHRENHEIT


def test_restore_template_uoms_overrides_stale_fahrenheit():
    drivers = deepcopy(driversMap['EcobeeHKC'])
    for d in drivers:
        if d['driver'] in ('ST', 'CLISPH', 'CLISPC'):
            d['uom'] = UOM_FAHRENHEIT
            d['value'] = 21
    n = restore_template_uoms(drivers, driversMap['EcobeeHKC'])
    assert n == 3
    by = {d['driver']: d for d in drivers}
    assert by['ST']['uom'] == UOM_CELSIUS
    assert by['CLISPH']['uom'] == UOM_CELSIUS
    assert by['CLISPC']['uom'] == UOM_CELSIUS
    assert by['ST']['value'] == 21


def test_driver_uom_from_list():
    assert driver_uom_from_list(driversMap['EcobeeHKC'], 'CLISPH') == UOM_CELSIUS
    assert driver_uom_from_list(driversMap['EcobeeHKF'], 'ST') == UOM_FAHRENHEIT
    assert driver_uom_from_list(driversMap['EcobeeHKC'], 'NOPE') is None


def _bare_thermostat(use_celsius: bool) -> HomeKitThermostat:
    node = HomeKitThermostat.__new__(HomeKitThermostat)
    node.use_celsius = use_celsius
    node.thermostat_id = '123'
    base = 'EcobeeHKC' if use_celsius else 'EcobeeHKF'
    node.id = f'{base}_123'
    node.drivers = deepcopy(driversMap[base])
    return node


def test_apply_display_units_switches_nodedef_and_preserves_values():
    node = _bare_thermostat(False)
    node.drivers[0]['value'] = 70
    assert node.apply_display_units(True) is True
    assert node.use_celsius is True
    assert node.id == 'EcobeeHKC_123'
    by = {d['driver']: d for d in node.drivers}
    assert by['ST']['uom'] == UOM_CELSIUS
    assert by['ST']['value'] == 70
    assert by['CLISPC']['uom'] == UOM_CELSIUS
    assert by['CLIMD']['uom'] == UOM_TSTAT_MODE
    assert node.apply_display_units(True) is False


def test_apply_display_units_fixes_stale_uom_same_nodedef():
    node = _bare_thermostat(True)
    for d in node.drivers:
        if d['driver'] == 'ST':
            d['uom'] = UOM_FAHRENHEIT
    assert node.apply_display_units(True) is True
    assert driver_uom_from_list(node.drivers, 'ST') == UOM_CELSIUS


def _bare_sensor(use_celsius: bool) -> HomeKitSensor:
    node = HomeKitSensor.__new__(HomeKitSensor)
    node.use_celsius = use_celsius
    node.id = 'EcobeeSensorHC' if use_celsius else 'EcobeeSensorHF'
    node.drivers = deepcopy(driversMap[node.id])
    return node


def test_use_celsius_true_false_auto():
    hk = HomeKitBackend(
        SimpleNamespace(
            poly=SimpleNamespace(),
            address='ctrl',
            Notices=SimpleNamespace(),
            Data={},
            Params={},
            TypedData={},
            effective_params={'use_celsius': 'true'},
        )
    )
    assert hk._use_celsius() is True
    hk.dispatcher.effective_params['use_celsius'] = 'false'
    assert hk._use_celsius() is False
    hk.dispatcher.effective_params['use_celsius'] = 'auto'
    assert hk._use_celsius() is False


def test_republish_if_units_changed_adds_node():
    hk = HomeKitBackend(
        SimpleNamespace(
            poly=SimpleNamespace(),
            address='ctrl',
            Notices=SimpleNamespace(),
            Data={},
            Params={},
            TypedData={},
            effective_params={},
        )
    )
    hk.add_node = MagicMock()
    node = _bare_thermostat(False)
    node.address = 't123'
    node.reportDrivers = MagicMock()
    assert hk._republish_if_units_changed(node, True) is True
    hk.add_node.assert_called_once_with(node)
    node.reportDrivers.assert_called_once()
    assert node.id == 'EcobeeHKC_123'


def test_sensor_apply_display_units_switches_nodedef():
    node = _bare_sensor(False)
    node.drivers[0]['value'] = 68
    assert node.apply_display_units(True) is True
    assert node.id == 'EcobeeSensorHC'
    assert driver_uom_from_list(node.drivers, 'ST') == UOM_CELSIUS
    assert node.drivers[0]['value'] == 68
