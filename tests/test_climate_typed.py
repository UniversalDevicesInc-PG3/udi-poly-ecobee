"""climate_typed unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from climate_typed import (
    ensure_climate_typed_data,
    profile_climates_for_thermostat,
    seed_climate_rows,
    sync_climate_typed_store,
)
from node_funcs import climateList, climateMap


def test_seed_climate_rows_from_api():
    api = [{'ref': 'home', 'name': 'Main Floor'}, {'ref': 'smart2', 'name': 'Movie'}]
    rows = seed_climate_rows(api_climates=api)
    assert {r['climateRef'] for r in rows} == {'home', 'smart2'}
    assert rows[0]['name'] == 'Main Floor'



def test_ensure_climate_typed_data_creates_thermostat_row():
    rows, changed = ensure_climate_typed_data(
        [],
        [{'thermostat_id': '9243', 'name': 'Downstairs'}],
    )
    assert changed is True
    assert rows[0]['thermostat_id'] == '9243'
    assert rows[0]['name'] == 'Downstairs'
    assert len(rows[0]['climates']) >= 4


def test_ensure_merges_api_names_without_overwriting_custom():
    existing = [
        {
            'thermostat_id': '9243',
            'name': 'Downstairs',
            'climates': [
                {'climateRef': 'home', 'name': 'My Home'},
                {'climateRef': 'away', 'name': 'Away'},
            ],
        }
    ]
    rows, changed = ensure_climate_typed_data(
        existing,
        [
            {
                'thermostat_id': '9243',
                'name': 'Downstairs',
                'api_climates': [
                    {'ref': 'home', 'name': 'API Home'},
                    {'ref': 'smart2', 'name': 'Workshop'},
                ],
            }
        ],
    )
    home = next(c for c in rows[0]['climates'] if c['climateRef'] == 'home')
    assert home['name'] == 'My Home'
    smart2 = next(c for c in rows[0]['climates'] if c['climateRef'] == 'smart2')
    assert smart2['name'] == 'Workshop'


def test_profile_climates_for_thermostat_uses_nested_names():
    typed = [
        {
            'thermostat_id': '9243',
            'climates': [
                {'climateRef': 'smart2', 'name': 'Movie Night'},
            ],
        }
    ]
    profile = profile_climates_for_thermostat(typed, '9243', climate_catalog=climateList[:8])
    assert profile[climateMap['smart2']]['name'] == 'Movie Night'
    assert profile[climateMap['away']]['name'] == 'Away'


def test_sync_climate_typed_store_persists_when_changed():
    store = MagicMock()
    store.keys.return_value = []
    sync_climate_typed_store(
        store,
        [{'thermostat_id': '1', 'name': 'Stat'}],
        climate_catalog=climateList[:6],
    )
    store.load.assert_called_once()
    payload = store.load.call_args[0][0]
    assert 'climate_programs' in payload
    assert payload['climate_programs'][0]['thermostat_id'] == '1'
