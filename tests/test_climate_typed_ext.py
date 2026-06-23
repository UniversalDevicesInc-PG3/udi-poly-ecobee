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
