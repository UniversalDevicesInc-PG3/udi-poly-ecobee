"""Hub ``list_devices`` metadata: pairing row vs ``accessories[]`` thermostat detection."""

from __future__ import annotations

from types import SimpleNamespace

from nodes.backends.homekit.Controller import HomeKitBackend


def _hk():
    d = SimpleNamespace(
        poly=SimpleNamespace(),
        address='ctrl',
        Notices=SimpleNamespace(),
        Data={},
        Params={},
        TypedData={},
        effective_params={},
    )
    return HomeKitBackend(d)


def test_thermostat_rows_top_level_category_still_works():
    hk = _hk()
    devices = [
        {'device_id': 'AA:BB', 'category': 9, 'primary_aid': 1},
    ]
    rows = hk._thermostat_rows_from_hub(devices)
    assert len(rows) == 1
    assert hk._hub_device_id(rows[0]) == 'aa:bb'


def test_thermostat_rows_from_accessories_when_pairing_not_cat9():
    hk = _hk()
    devices = [
        {
            'device_id': 'AA:BB',
            'category': 2,
            'primary_aid': 1,
            'accessories': [
                {'aid': 3, 'category': 9},
                {'aid': 5, 'name': 'Other'},
            ],
        },
    ]
    rows = hk._thermostat_rows_from_hub(devices)
    assert len(rows) == 1
    assert hk._thermostat_primary_aid_from_hub_row(rows[0]) == 3


def test_thermostat_rows_thermostat_like_flag():
    hk = _hk()
    devices = [
        {
            'device_id': 'cc:dd',
            'category': 2,
            'accessories': [{'aid': 7, 'thermostat_like': True}],
        },
    ]
    rows = hk._thermostat_rows_from_hub(devices)
    assert len(rows) == 1
    assert hk._thermostat_primary_aid_from_hub_row(rows[0]) == 7


def test_thermostat_primary_aid_min_of_multiple_thermostat_aids():
    hk = _hk()
    dev = {
        'device_id': 'x',
        'primary_aid': 1,
        'accessories': [
            {'aid': 4, 'thermostat_like': True},
            {'aid': 2, 'category': 9},
        ],
    }
    assert hk._thermostat_primary_aid_from_hub_row(dev) == 2


def test_thermostat_primary_aid_falls_back_when_no_accessory_match():
    hk = _hk()
    dev = {'device_id': 'x', 'primary_aid': 3, 'accessories': [{'aid': 2, 'category': 5}]}
    assert hk._thermostat_primary_aid_from_hub_row(dev) == 3


def test_accessory_category_label_thermostat():
    hk = _hk()
    assert HomeKitBackend._hub_accessory_row_is_thermostat({'aid': 1, 'category_label': 'THERMOSTAT'})


def test_empty_devices_no_rows():
    hk = _hk()
    assert hk._thermostat_rows_from_hub([]) == []


def test_thermostat_display_name_prefers_matching_accessory_row():
    hk = _hk()
    dev = {
        'device_id': 'aa',
        'name': 'Lake Living Room Occupancy',
        'primary_aid': 2,
        'accessories': [
            {'aid': 2, 'name': 'Lake Living Room', 'category': 9},
            {'aid': 3, 'name': 'Bedroom', 'thermostat_like': False},
        ],
    }
    assert hk._thermostat_primary_aid_from_hub_row(dev) == 2
    assert hk._thermostat_display_name_from_hub_row(dev) == 'Lake Living Room'


def test_thermostat_display_name_falls_back_to_pairing_name():
    hk = _hk()
    dev = {'device_id': 'bb', 'name': 'Only Top-Level'}
    assert hk._thermostat_display_name_from_hub_row(dev) == 'Only Top-Level'


def test_hub_devices_topology_fingerprint_stable_under_accessory_order():
    hk = _hk()
    a = [
        {
            'device_id': 'dc:9b:cc:02:9a:fe',
            'primary_aid': 1,
            'accessories': [
                {'aid': 2, 'name': 'B', 'serial_number': 'x'},
                {'aid': 1, 'name': 'A', 'serial_number': 'y'},
            ],
        },
    ]
    b = [
        {
            'device_id': 'dc:9b:cc:02:9a:fe',
            'primary_aid': 1,
            'accessories': [
                {'aid': 1, 'name': 'A', 'serial_number': 'y'},
                {'aid': 2, 'name': 'B', 'serial_number': 'x'},
            ],
        },
    ]
    assert hk._hub_devices_topology_fingerprint(a) == hk._hub_devices_topology_fingerprint(b)


def test_hub_devices_topology_fingerprint_changes_when_aid_added():
    hk = _hk()
    before = [
        {'device_id': 'aa:bb', 'primary_aid': 1, 'accessories': [{'aid': 1, 'name': 'T'}]},
    ]
    after = [
        {
            'device_id': 'aa:bb',
            'primary_aid': 1,
            'accessories': [{'aid': 1, 'name': 'T'}, {'aid': 3, 'name': 'S'}],
        },
    ]
    assert hk._hub_devices_topology_fingerprint(before) != hk._hub_devices_topology_fingerprint(after)


def test_hub_devices_topology_fingerprint_ignores_volatile_model_string():
    hk = _hk()
    a = [{'device_id': 'aa:bb', 'primary_aid': 1, 'accessories': [{'aid': 1}], 'model': 'ecobee4'}]
    b = [{'device_id': 'aa:bb', 'primary_aid': 1, 'accessories': [{'aid': 1}], 'model': 'ecobee5'}]
    assert hk._hub_devices_topology_fingerprint(a) == hk._hub_devices_topology_fingerprint(b)
