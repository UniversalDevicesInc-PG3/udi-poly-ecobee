"""climate_typed_ext unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from climate_typed_ext import (
    sync_climate_typed_store,
    sync_learned_setpoint_in_typed_store,
)


def test_sync_learned_setpoint_in_typed_store_writes_heat_cool():
    store = MagicMock()
    store.keys.return_value = ['climate_programs']
    store.__getitem__.side_effect = lambda k: {
        'climate_programs': [
            {
                'thermostat_id': '001',
                'climates': [
                    {'climateRef': 'smart1', 'name': 'Workshop'},
                ],
            }
        ]
    }[k]

    changed = sync_learned_setpoint_in_typed_store(store, '001', 'smart1', 70.0, 74.0)
    assert changed is True
    store.load.assert_called_once()
    payload = store.load.call_args[0][0]
    row = payload['climate_programs'][0]
    smart1 = next(c for c in row['climates'] if c['climateRef'] == 'smart1')
    assert smart1['heat'] == '70.0'
    assert smart1['cool'] == '74.0'


def test_sync_climate_typed_store_restores_blank_heat_cool_from_stored():
    """A restart must not leave learned heat/cool blank when custom data still has them."""
    programs = [
        {
            'thermostat_id': '411956665463',
            'name': 'JimBo Dev',
            'device_id': '34:29:62:b4:da:31',
            'climates': [
                {'climateRef': 'away', 'name': 'Away'},
                {'climateRef': 'home', 'name': 'Home', 'heat': '70', 'cool': '78'},
            ],
        }
    ]
    store = MagicMock()
    store.keys.return_value = ['climate_programs']
    store.__getitem__.side_effect = lambda k: {'climate_programs': programs}[k]
    sync_climate_typed_store(
        store,
        [{'thermostat_id': '411956665463', 'name': 'JimBo Dev', 'device_id': '34:29:62:b4:da:31'}],
        stored_setpoints={
            '411956665463': {
                'away': {'heat': 68, 'cool': 76},
                'home': {'heat': 64, 'cool': 82},
            }
        },
    )
    store.load.assert_called_once()
    saved = store.load.call_args[0][0]['climate_programs'][0]['climates']
    away = next(c for c in saved if c['climateRef'] == 'away')
    home = next(c for c in saved if c['climateRef'] == 'home')
    assert away['heat'] == '68.0'
    assert away['cool'] == '76.0'
    assert home['heat'] == '70'
    assert home['cool'] == '78'


def test_sync_climate_typed_store_preserves_learned_setpoints():
    store = MagicMock()
    store.keys.return_value = ['climate_programs']
    store.__getitem__.side_effect = lambda k: {
        'climate_programs': [
            {
                'thermostat_id': '001',
                'name': 'Downstairs',
                'climates': [
                    {'climateRef': 'home', 'name': 'Home'},
                    {'climateRef': 'smart1', 'name': 'Workshop', 'heat': '68', 'cool': '72'},
                ],
            }
        ]
    }[k]

    sync_climate_typed_store(
        store,
        [{'thermostat_id': '001', 'name': 'Downstairs', 'api_climates': [{'ref': 'home', 'name': 'Home'}]}],
    )
    if store.load.called:
        payload = store.load.call_args[0][0]
        row = payload['climate_programs'][0]
        smart1 = next(c for c in row['climates'] if c['climateRef'] == 'smart1')
        assert smart1.get('heat') == '68'
        assert smart1.get('cool') == '72'


def test_sync_climate_typed_store_idempotent_when_setpoints_present():
    """Repeated hub sync must not re-save typed data (Polyglot echo loop)."""
    store = MagicMock()
    store.keys.return_value = ['climate_programs']
    store.__getitem__.side_effect = lambda k: {
        'climate_programs': [
            {
                'thermostat_id': '001',
                'name': 'Downstairs',
                'climates': [
                    {'climateRef': 'home', 'name': 'Home'},
                    {'climateRef': 'smart1', 'name': 'Workshop', 'heat': '68', 'cool': '72'},
                ],
            }
        ]
    }[k]

    specs = [{'thermostat_id': '001', 'name': 'Downstairs', 'api_climates': [{'ref': 'home', 'name': 'Home'}]}]
    sync_climate_typed_store(store, specs)
    store.reset_mock()
    sync_climate_typed_store(store, specs)
    store.load.assert_not_called()
