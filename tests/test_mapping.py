"""homekit_client.mapping unit tests."""

from __future__ import annotations

from homekit_client.mapping import remote_sensor_address, resolve_thermostat_address, sanitize_address_part


def test_sanitize_address_part():
    assert sanitize_address_part('AA:BB:CC') == 'aabbcc'
    assert sanitize_address_part('') == ''


def test_resolve_override():
    addr, reason = resolve_thermostat_address(
        'aa:bb:cc',
        serial_number='123',
        accessory_name='T',
        existing_addresses=[],
        id_override='999',
    )
    assert addr == 't999'
    assert reason == 'hk_id_overrides'


def test_resolve_exact_serial():
    addr, reason = resolve_thermostat_address(
        'aa:bb:cc',
        serial_number='511892759243',
        accessory_name=None,
        existing_addresses=['t511892759243', 'tother'],
    )
    assert addr == 't511892759243'
    assert reason == 'exact_serial'


def test_resolve_digit_suffix_single_match():
    addr, reason = resolve_thermostat_address(
        'd',
        serial_number='XX511892759243',
        accessory_name=None,
        existing_addresses=['t9243', 'tnope'],
    )
    assert addr == 't9243'
    assert reason == 'digit_suffix'


def test_resolve_mint_serial():
    addr, reason = resolve_thermostat_address(
        'd',
        serial_number='NEW123',
        accessory_name=None,
        existing_addresses=['tother'],
    )
    assert addr == 't123'
    assert reason == 'mint_serial'


def test_resolve_name_digits_single():
    # No digit-suffix match from serial; accessory name carries the ecobee id.
    addr, reason = resolve_thermostat_address(
        'd',
        serial_number='NEW888',
        accessory_name='Ecobee - Basement 9243',
        existing_addresses=['t9243', 't8888'],
    )
    assert addr == 't9243'
    assert reason == 'name_digits'


def test_resolve_ambiguous_digit_suffix_uses_name():
    # Plain serial digits end with two different existing suffixes (500243 and 243).
    addr, reason = resolve_thermostat_address(
        'd',
        serial_number='XX12500243',
        accessory_name='Ecobee - Upstairs 500243',
        existing_addresses=['t500243', 't243'],
    )
    assert addr == 't500243'
    assert reason == 'name_digits'


def test_resolve_ambiguous_mints_full_serial():
    addr, reason = resolve_thermostat_address(
        'd',
        serial_number='511892759243',
        accessory_name=None,
        existing_addresses=['t243', 't9243'],
    )
    assert addr == 't511892759243'
    assert reason == 'mint_serial'


def test_resolve_device_id_fallback_no_serial():
    addr, reason = resolve_thermostat_address(
        'AA:BB:CC:DD:EE:FF',
        serial_number=None,
        accessory_name=None,
        existing_addresses=[],
    )
    assert addr == 'taabbccddeeff'
    assert reason == 'device_id_fallback'


def test_remote_sensor_override():
    assert remote_sensor_address('d', 2, 'Kitchen', code_override='ABCD') == 'rs_abcd'


def test_remote_sensor_mint_from_name():
    a = remote_sensor_address('d', 2, 'Bedroom Sensor', None)
    assert a.startswith('rs_')


def test_remote_sensor_address_respects_14_char_limit():
    """IoX/PG3 rejects node addresses longer than 14 characters (e.g. rs_mastermotion = 15)."""
    a = remote_sensor_address('d', 1, 'Master Motion', None)
    assert len(a) <= 14
    assert a == 'rs_mastermotio'


def test_remote_sensor_override_truncated():
    long_ov = 'VeryLongOverrideCodeThatMustTruncate'
    a = remote_sensor_address('d', 1, 'X', code_override=long_ov)
    assert len(a) <= 14
