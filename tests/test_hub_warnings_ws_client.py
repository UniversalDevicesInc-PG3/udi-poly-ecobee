"""Hub WebSocket ``warnings`` dispatch (udi-poly-homekit-hub PROTOCOL)."""

from __future__ import annotations

import logging

from homekit_client.ws_client import HubWebSocketClient


def test_dispatch_hub_warnings_calls_callback():
    captured: list = []

    def cb(w):
        captured.append(list(w))

    c = HubWebSocketClient(
        'ws://127.0.0.1:1',
        '',
        on_warnings=cb,
        logger=logging.getLogger('test_hk_ws'),
    )
    c._dispatch_hub_warnings(
        {
            'warnings': [
                {'level': 'warning', 'code': 'metadata_incomplete', 'message': 'detail', 'device_id': 'aa:bb'},
            ]
        }
    )
    assert len(captured) == 1
    assert captured[0][0]['code'] == 'metadata_incomplete'


def test_dispatch_hub_warnings_empty_list_still_invokes():
    captured: list = []

    def cb(w):
        captured.append(w)

    c = HubWebSocketClient(
        'ws://127.0.0.1:1',
        '',
        on_warnings=cb,
        logger=logging.getLogger('test_hk_ws'),
    )
    c._dispatch_hub_warnings({'warnings': []})
    assert captured == [[]]


def test_dispatch_hub_warnings_omitted_key_no_callback():
    captured: list = []

    def cb(w):
        captured.append(w)

    c = HubWebSocketClient(
        'ws://127.0.0.1:1',
        '',
        on_warnings=cb,
        logger=logging.getLogger('test_hk_ws'),
    )
    c._dispatch_hub_warnings({'devices': []})
    assert captured == []
