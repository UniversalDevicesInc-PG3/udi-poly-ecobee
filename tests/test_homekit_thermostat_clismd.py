"""HomeKit thermostat CLISMD / resume-schedule unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from homekit_client.hap_apply import (
    hap_name_vendor_ecobee_clear_hold,
    vendor_ecobee_clear_hold_wire_values,
)
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
