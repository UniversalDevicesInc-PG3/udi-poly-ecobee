"""homekit_client.char_map unit tests."""

from __future__ import annotations

import pytest

from homekit_client.char_map import (
    CharBucket,
    accessory_display_name_from_snapshot_rows,
    builtin_motion_sensor_ambient_mirror,
    builtin_motion_sensor_mirror_characteristic,
    classify,
    classify_uuid_normalized,
    informational_uuids_normalized,
    invert_mapped_uuids,
    is_builtin_room_sensor_signal,
    mapped_uuids_normalized,
    normalize_hap_uuid,
    thermostat_control_aid_from_snapshot_values,
)


@pytest.mark.parametrize(
    'name,aid,bucket',
    [
        ('', 1, CharBucket.UNKNOWN),
        ('VENDOR_ECOBEE_CURRENT_MODE', 1, CharBucket.INFORMATIONAL),
        ('TEMPERATURE_CURRENT', 1, CharBucket.MAPPED),
        ('RELATIVE_HUMIDITY_CURRENT', 2, CharBucket.MAPPED),
        ('BATTERY_LEVEL', 3, CharBucket.MAPPED),
        ('STATUS_LOW_BATTERY', 1, CharBucket.MAPPED),
        ('SomeFutureHapName', 1, CharBucket.UNKNOWN),
        ('VENDOR_OTHER_WIDGET', 1, CharBucket.UNKNOWN),
        ('MOTION_DETECTED', 1, CharBucket.MAPPED),
        ('Manufacturer', 1, CharBucket.INFORMATIONAL),
        ('StatusActive', 1, CharBucket.INFORMATIONAL),
        ('PRODUCT_DATA', 1, CharBucket.INFORMATIONAL),
        ('AccessoryProperties', 1, CharBucket.INFORMATIONAL),
        ('TemperatureDisplayUnits', 1, CharBucket.INFORMATIONAL),
        ('TEMPERATURE_UNITS', 1, CharBucket.INFORMATIONAL),
        ('Version', 1, CharBucket.INFORMATIONAL),
    ],
)
def test_classify(name, aid, bucket):
    assert classify(name, aid) == bucket


def test_classify_full_uuid():
    u = '00000011-0000-1000-8000-0026BB765291'
    assert classify(u, 1) == CharBucket.MAPPED


@pytest.mark.parametrize(
    'ch,expected',
    [
        ('', False),
        ('MotionDetected', True),
        ('MOTION_DETECTED', True),
        ('00000022-0000-1000-8000-0026BB765291', True),
        ('OccupancyDetected', True),
        ('OCCUPANCY_DETECTED', True),
        ('00000071-0000-1000-1000-8000-0026BB765291', False),
        ('00000071-0000-1000-8000-0026BB765291', True),
        ('TargetTemperature', False),
        ('CURRENT_TEMPERATURE', False),
    ],
)
def test_is_builtin_room_sensor_signal(ch, expected):
    assert is_builtin_room_sensor_signal(ch) is expected


@pytest.mark.parametrize(
    'ch,expected',
    [
        ('MotionDetected', False),
        ('00000011-0000-1000-8000-0026BB765291', True),
        ('CurrentTemperature', True),
        ('RELATIVE_HUMIDITY_CURRENT', True),
        ('RELATIVE_HUMIDITY_TARGET', False),
        ('TargetTemperature', False),
    ],
)
def test_builtin_motion_sensor_ambient_mirror(ch, expected):
    assert builtin_motion_sensor_ambient_mirror(ch) is expected


def test_builtin_motion_sensor_mirror_includes_motion_and_temp():
    assert builtin_motion_sensor_mirror_characteristic('MotionDetected') is True
    assert builtin_motion_sensor_mirror_characteristic('CurrentTemperature') is True


def test_classify_informational_metadata_uuids():
    assert classify('00000036-0000-1000-8000-0026BB765291', 1) == CharBucket.INFORMATIONAL
    assert classify('00000037-0000-1000-8000-0026BB765291', 1) == CharBucket.INFORMATIONAL
    assert classify('00000220-0000-1000-8000-0026BB765291', 1) == CharBucket.INFORMATIONAL
    assert classify('34AB8811-AC7F-4340-BAC3-FD6A85F9943B', 1) == CharBucket.INFORMATIONAL


def test_normalize_hap_uuid():
    assert normalize_hap_uuid('00000011-0000-1000-8000-0026BB765291') == (
        '000000110000100080000026bb765291'
    )
    assert normalize_hap_uuid('not-a-uuid') is None


def test_classify_uuid_normalized():
    nu = '000000110000100080000026bb765291'
    assert classify_uuid_normalized(nu) == CharBucket.MAPPED
    name_nu = normalize_hap_uuid('00000023-0000-1000-8000-0026BB765291')
    assert name_nu is not None
    assert classify_uuid_normalized(name_nu) == CharBucket.INFORMATIONAL
    motion_nu = normalize_hap_uuid('00000022-0000-1000-8000-0026BB765291')
    assert classify_uuid_normalized(motion_nu) == CharBucket.MAPPED
    assert classify_uuid_normalized('ffffffffffffffffffffffffffffffff') is None


def test_informational_vendor_uuids():
    u = informational_uuids_normalized()
    assert normalize_hap_uuid('A8F798E0-4A40-11E6-BDF4-0800200C9A66') in u


def test_mapped_uuids_and_invert():
    s = mapped_uuids_normalized()
    assert '000000110000100080000026bb765291' in s
    inv = invert_mapped_uuids()
    assert inv == set(s)


def test_accessory_display_name_from_snapshot_rows_hap_name_uuid():
    rows = [
        {'characteristic': '00000023-0000-1000-8000-0026BB765291', 'value': 'Kitchen'},
        {'characteristic': '00000011-0000-1000-8000-0026BB765291', 'value': 22.0},
    ]
    assert accessory_display_name_from_snapshot_rows(rows) == 'Kitchen'


def test_accessory_display_name_prefers_configured_name_uuid():
    rows = [
        {'characteristic': '00000023-0000-1000-8000-0026BB765291', 'value': 'Ecobee Sensor'},
        {'characteristic': '000000E3-0000-1000-8000-0026BB765291', 'value': 'Lake Living Room'},
    ]
    assert accessory_display_name_from_snapshot_rows(rows) == 'Lake Living Room'


def test_accessory_display_name_configured_name_label():
    rows = [{'characteristic': 'ConfiguredName', 'value': '  Porch  '}]
    assert accessory_display_name_from_snapshot_rows(rows) == 'Porch'


def test_accessory_display_name_ecobee_multiple_name_prefers_lowest_iid():
    """Multiple **Name** rows: lowest ``iid`` matches Accessory Information primary (e.g. …/2)."""
    rows = [
        {'characteristic': 'NAME', 'iid': 27, 'value': 'Lake Living Room'},
        {'characteristic': 'NAME', 'iid': 2, 'value': 'Lake Living Room'},
        {'characteristic': 'NAME', 'iid': 28, 'value': 'Lake Living Room Motion'},
        {'characteristic': 'NAME', 'iid': 29, 'value': 'Lake Living Room Occupancy'},
    ]
    assert accessory_display_name_from_snapshot_rows(rows) == 'Lake Living Room'


def test_accessory_display_name_uses_lowest_iid_when_only_service_labels():
    """If only later **Name** rows exist, take the lowest ``iid`` (no string rewriting)."""
    rows = [
        {'characteristic': 'NAME', 'iid': 210, 'value': 'Kitchen Temperature'},
        {'characteristic': 'NAME', 'iid': 28, 'value': 'Kitchen Motion'},
    ]
    assert accessory_display_name_from_snapshot_rows(rows) == 'Kitchen Motion'


def test_thermostat_control_aid_prefers_accessory_with_mode_target():
    occ_aid = 2
    therm_aid = 5
    rows = [
        {'aid': occ_aid, 'characteristic': 'CurrentTemperature', 'value': 22.0},
        {
            'aid': therm_aid,
            'characteristic': '00000033-0000-1000-8000-0026BB765291',
            'value': 3,
        },
        {
            'aid': therm_aid,
            'characteristic': '00000012-0000-1000-8000-0026BB765291',
            'value': 20.0,
        },
    ]
    assert thermostat_control_aid_from_snapshot_values(rows) == therm_aid


def test_thermostat_control_aid_tie_prefers_lower_aid():
    rows = [
        {'aid': 1, 'characteristic': 'HeatingThresholdTemperature', 'value': 19.0},
        {'aid': 2, 'characteristic': 'CoolingThresholdTemperature', 'value': 25.0},
    ]
    assert thermostat_control_aid_from_snapshot_values(rows) == 1


def test_thermostat_control_aid_empty():
    assert thermostat_control_aid_from_snapshot_values([]) is None
    assert thermostat_control_aid_from_snapshot_values(None) is None
