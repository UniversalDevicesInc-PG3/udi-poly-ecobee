"""Hub WebSocket client: multiplexed RPC by correlation ``id``."""

from __future__ import annotations

import logging

import pytest

from homekit_client.ws_client import HubWebSocketClient


def _client() -> HubWebSocketClient:
    return HubWebSocketClient('ws://127.0.0.1:1', '', logger=logging.getLogger('test_hk_ws_mx'))


def test_multiplex_two_commands_complete_out_of_order():
    c = _client()
    r1, f1 = c._register_rpc('command', 'aa:bb')
    r2, f2 = c._register_rpc('command', 'aa:bb')
    assert r1 != r2
    c._route_rpc_message({'action': 'ack', 'for': 'command', 'id': r2})
    c._route_rpc_message({'action': 'ack', 'for': 'command', 'id': r1})
    assert f1.result(timeout=1.0) is True
    assert f2.result(timeout=1.0) is True
    assert not c._pending


def test_snapshot_and_command_concurrent():
    c = _client()
    rs, fs = c._register_rpc('snapshot', 'dc:9b:cc:02:9a:fe')
    rc, fc = c._register_rpc('command', 'dc:9b:cc:02:9a:fe')
    c._route_rpc_message(
        {'action': 'ack', 'for': 'command', 'id': rc},
    )
    c._route_rpc_message(
        {
            'action': 'snapshot',
            'device_id': 'dc:9b:cc:02:9a:fe',
            'id': rs,
            'values': [{'aid': 1, 'characteristic': 'X', 'value': 1}],
        },
    )
    assert fc.result(timeout=1.0) is True
    assert fs.result(timeout=1.0) == [{'aid': 1, 'characteristic': 'X', 'value': 1}]
    assert not c._pending


def test_finish_all_pending():
    c = _client()
    _r1, f1 = c._register_rpc('get', 'aa')
    _r2, f2 = c._register_rpc('snapshot', 'bb')
    c._finish_all_pending(RuntimeError('connection closed'))
    with pytest.raises(RuntimeError, match='connection closed'):
        f1.result(timeout=1.0)
    with pytest.raises(RuntimeError, match='connection closed'):
        f2.result(timeout=1.0)
    assert not c._pending


def test_legacy_single_command_ack_without_id():
    c = _client()
    _r, f = c._register_rpc('command', 'aa')
    c._route_rpc_message({'action': 'ack', 'for': 'command'})
    assert f.result(timeout=1.0) is True


def test_legacy_snapshot_without_id_matches_device():
    c = _client()
    _r, f = c._register_rpc('snapshot', 'aa:bb')
    c._route_rpc_message(
        {
            'action': 'snapshot',
            'device_id': 'aa:bb',
            'values': [{'v': 1}],
        },
    )
    assert f.result(timeout=1.0) == [{'v': 1}]
