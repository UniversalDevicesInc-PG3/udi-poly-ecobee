"""ecobee_program unit tests."""

from __future__ import annotations

from ecobee_program import (
    climate_setpoints_for_storage,
    climate_setpoints_from_program_climates,
    climate_setpoints_from_stored,
    comfort_setpoints_from_typed_rows,
    ecobee_api_temp_to_driver,
    seed_gv3_to_sp_from_comfort_maps,
)
from node_funcs import climateMap


def test_ecobee_api_temp_to_driver_fahrenheit():
    assert ecobee_api_temp_to_driver(730, use_celsius=False) == 73.0
    assert ecobee_api_temp_to_driver(780, use_celsius=False) == 78.0


def test_climate_setpoints_from_program_climates():
    climates = [
        {'climateRef': 'smart1', 'heatTemp': 730, 'coolTemp': 780},
        {'climateRef': 'home', 'heatTemp': 710, 'coolTemp': 760},
    ]
    sp = climate_setpoints_from_program_climates(climates, use_celsius=False)
    assert sp['smart1'] == (73.0, 78.0)
    assert sp['home'] == (71.0, 76.0)


def test_climate_setpoints_round_trip_storage():
    by_ref = {'smart1': (73.0, 78.0)}
    stored = {'climate_setpoints': {'9243': climate_setpoints_for_storage(by_ref)}}
    assert climate_setpoints_from_stored(stored, '9243') == by_ref


def test_comfort_setpoints_from_typed_rows():
    rows = [
        {
            'thermostat_id': '9243',
            'climates': [
                {'climateRef': 'smart1', 'name': 'Working', 'heat': 73, 'cool': 78},
            ],
        }
    ]
    sp = comfort_setpoints_from_typed_rows(rows, '9243')
    assert sp['smart1'] == (73.0, 78.0)


def test_seed_gv3_to_sp_from_comfort_maps():
    gv3_to_sp: dict[int, tuple[float, float]] = {}
    seed_gv3_to_sp_from_comfort_maps(
        gv3_to_sp,
        program_sp={'smart1': (73.0, 78.0)},
        vendor_sp={'home': (71.0, 76.0)},
    )
    assert gv3_to_sp[climateMap['smart1']] == (73.0, 78.0)
    assert gv3_to_sp[climateMap['home']] == (71.0, 76.0)
