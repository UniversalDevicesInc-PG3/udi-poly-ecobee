"""MQTT hello retry behavior for delayed udi-poly-homekit hub startup."""

from __future__ import annotations

import asyncio
import logging

from homekit_client.mqtt_client import HubMqttClient


def _client() -> HubMqttClient:
    return HubMqttClient('127.0.0.1', logger=logging.getLogger('test_hk_mqtt_retry'))


def test_hello_retry_loop_retries_until_ack():
    client = _client()
    client._mqtt_pub = object()
    sent: list[int] = []

    async def fake_send_hello() -> None:
        sent.append(len(sent) + 1)
        if len(sent) >= 3:
            client._hello_ok.set()

    client._send_hello = fake_send_hello  # type: ignore[method-assign]

    asyncio.run(client._hello_retry_loop(schedule=(0.0, 0.0, 0.0)))

    assert sent == [1, 2, 3]
    assert client.wait_hello(0.0) is True
