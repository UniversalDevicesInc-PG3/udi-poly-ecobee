"""Import smoke tests — catch packaging / syntax errors before eISY deploy."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_nodes_package_exports():
    from nodes import VERSION, Controller

    assert Controller is not None
    assert VERSION == (ROOT / 'profile' / 'version.txt').read_text(encoding='utf-8').strip()


def test_import_dispatcher_class():
    from nodes.Controller import Controller as C

    assert C.id == 'ECO_CTR'


def test_import_cloud_backend():
    from nodes.backends.cloud import CloudBackend

    assert CloudBackend.__name__ == 'CloudBackend'


def test_import_homekit_backend():
    from nodes.backends.homekit import HomeKitBackend, HomeKitSensor

    assert HomeKitBackend.__name__ == 'HomeKitBackend'
    assert HomeKitSensor.__name__ == 'HomeKitSensor'


def test_import_homekit_client():
    from homekit_client import HubMqttClient, HubWebSocketClient, PROTOCOL_VERSION

    assert PROTOCOL_VERSION == '1'
    assert HubWebSocketClient is not None
    assert HubMqttClient is not None


def test_const_has_controller_and_sensors():
    from const import driversMap

    assert 'ECO_CTR' in driversMap
    for key in ('ST', 'GV1', 'GV3', 'GV4', 'GV5'):
        names = {d['driver'] for d in driversMap['ECO_CTR']}
        assert key in names
    assert 'BATLVL' in {d['driver'] for d in driversMap['EcobeeSensorF']}


def test_controller_updateDrivers_merges_partial_pg3_list():
    """PG3 CONFIG can omit new drivers until IoX profile sync; merge must keep GV4/GV5."""
    from const import driversMap
    from nodes.Controller import Controller

    c = object.__new__(Controller)
    partial = [
        {'driver': 'ST', 'value': '1', 'uom': 25},
        {'driver': 'GV1', 'value': '1', 'uom': 2},
        {'driver': 'GV3', 'value': '0', 'uom': 2},
    ]
    Controller.updateDrivers(c, partial)
    names = [d['driver'] for d in c.drivers]
    assert names == [d['driver'] for d in driversMap['ECO_CTR']]
    by = {d['driver']: d for d in c.drivers}
    assert 'GV4' in by and 'GV5' in by
    assert by['GV1']['value'] == '1'
    assert by['GV4']['value'] == 0
