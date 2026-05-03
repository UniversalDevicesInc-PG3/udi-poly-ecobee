"""Import smoke tests — catch packaging / syntax errors before eISY deploy."""

from __future__ import annotations


def test_nodes_package_exports():
    from nodes import VERSION, Controller

    assert Controller is not None
    assert VERSION == '4.0.0'


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
    from homekit_client import HubWebSocketClient, PROTOCOL_VERSION

    assert PROTOCOL_VERSION == '1'
    assert HubWebSocketClient is not None


def test_const_has_controller_and_sensors():
    from const import driversMap

    assert 'ECO_CTR' in driversMap
    for key in ('ST', 'GV1', 'GV3'):
        names = {d['driver'] for d in driversMap['ECO_CTR']}
        assert key in names
    assert 'BATLVL' in {d['driver'] for d in driversMap['EcobeeSensorF']}
