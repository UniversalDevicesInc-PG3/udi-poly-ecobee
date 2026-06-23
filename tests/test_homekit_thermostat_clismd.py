"""HomeKit thermostat CLISMD / resume-schedule unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from homekit_client.hap_apply import (
    hap_name_vendor_ecobee_clear_hold,
    vendor_ecobee_clear_hold_wire_values,
)
from node_funcs import climateMap
from nodes.backends.homekit.Thermostat import HomeKitThermostat


def _make_node() -> HomeKitThermostat:
    hk = MagicMock()
    hk.hub_command = MagicMock(return_value=True)
    hk.schedule_thermostat_refresh_after_hold_clear = MagicMock()
    node = HomeKitThermostat.__new__(HomeKitThermostat)
    node.hk = hk
    node.device_id_hub = 'dev-1'
    node.address = 't9243'
    node.set_driver_safe = MagicMock()
    node.getDriver = MagicMock(return_value='1')
    node._hub_write = MagicMock(return_value=True)
    node._hk_sp_sig_to_gv3 = {}
    node._hk_gv3_to_sp = {}
    node._hk_vendor_comfort_sp = {}
    return node


def test_hap_clear_hold_names_and_wire_sequence():
    assert hap_name_vendor_ecobee_clear_hold() == 'VENDOR_ECOBEE_CLEAR_HOLD'
    assert vendor_ecobee_clear_hold_wire_values() == (False, True)


def test_cmd_set_schedule_mode_resume_clears_hold_and_refreshes():
    node = _make_node()
    node.getDriver.return_value = '1'

    node.cmd_set_schedule_mode({'value': 0})

    assert node._hub_write.call_args_list == [
        (('VENDOR_ECOBEE_CLEAR_HOLD', False),),
        (('VENDOR_ECOBEE_CLEAR_HOLD', True),),
    ]
    node.set_driver_safe.assert_called_once_with('CLISMD', 0)
    node.hk.schedule_thermostat_refresh_after_hold_clear.assert_called_once_with(node)


def test_cmd_set_schedule_mode_resume_noop_when_already_running():
    node = _make_node()
    node.getDriver.return_value = '0'

    node.cmd_set_schedule_mode({'value': 0})

    node._hub_write.assert_not_called()
    node.set_driver_safe.assert_not_called()
    node.hk.schedule_thermostat_refresh_after_hold_clear.assert_not_called()


def test_cmd_set_schedule_mode_hold_next_records_local_only():
    node = _make_node()
    node.getDriver.return_value = '0'

    node.cmd_set_schedule_mode({'value': 1})

    node._hub_write.assert_not_called()
    node.set_driver_safe.assert_called_once_with('CLISMD', 1)
    node.hk.schedule_thermostat_refresh_after_hold_clear.assert_not_called()


def test_mark_hold_active_after_gv3_write():
    node = _make_node()
    node.getDriver.return_value = '0'

    node.cmd_set_gv3({'value': 1})

    node.set_driver_safe.assert_any_call('GV3', 1)
    node.set_driver_safe.assert_any_call('CLISMD', 1)


def test_gv3_hold_type_defaults_to_hold_next_without_query():
    node = _make_node()
    assert node._hold_type_from_cmd({}) == 1
    assert node._hold_type_from_cmd({'query': {}}) == 1


def test_gv3_hold_type_from_query():
    node = _make_node()
    node.getDriver.return_value = '0'

    node.cmd_set_gv3({'value': 2, 'query': {'HoldType.uom25': '2'}})

    node.set_driver_safe.assert_any_call('GV3', 2)
    node.set_driver_safe.assert_any_call('CLISMD', 2)


def test_cmd_set_gv3_vacation_writes_setpoints_then_hold():
    node = _make_node()
    node.getDriver.return_value = '3'
    node.use_celsius = False
    node.thermostat_id = '21892113032'
    node.device_id_hub = 'dev-1'
    node._configured_climate_refs = MagicMock(
        return_value=['home', 'away', 'sleep', 'vacation', 'smartAway']
    )
    node._hk_gv3_to_sp = {climateMap['vacation']: (50.0, 85.0)}
    node._hk_sp_sig_to_gv3 = {}
    node._hk_vendor_comfort_sp = {}
    node._hub_write_hold_setpoints = MagicMock(return_value=True)

    node.cmd_set_gv3({'value': climateMap['vacation']})

    node._hub_write_hold_setpoints.assert_called_once_with(50.0, 85.0)
    assert node._hub_write.call_args_list[0][0] == ('VENDOR_ECOBEE_SET_HOLD_SCHEDULE', 2)
    node.set_driver_safe.assert_any_call('GV3', climateMap['vacation'])
    node.set_driver_safe.assert_any_call('CLISPH', 50.0)
    node.set_driver_safe.assert_any_call('CLISPC', 85.0)


def test_cmd_set_gv3_temp_slot_aborts_without_known_setpoints():
    node = _make_node()
    node.getDriver.return_value = '3'
    node.thermostat_id = '21892113032'
    node.device_id_hub = 'dev-1'
    node._configured_climate_refs = MagicMock(
        return_value=['home', 'away', 'sleep', 'vacation', 'smartAway']
    )
    node._hk_gv3_to_sp = {}
    node._hk_sp_sig_to_gv3 = {}
    node._hk_vendor_comfort_sp = {}

    node.cmd_set_gv3({'value': climateMap['smart1']})

    node._hub_write.assert_not_called()
    node.set_driver_safe.assert_not_called()
