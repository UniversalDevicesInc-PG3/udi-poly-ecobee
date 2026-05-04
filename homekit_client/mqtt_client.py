"""Async MQTT client for udi-poly-homekit hub (dedicated thread + reconnect)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import aiomqtt

PROTOCOL_VERSION = "1"
# aiomqtt 2.x uses ``qos: int``; there is no ``aiomqtt.QoS`` (MQTT QoS 1 = at least once).
MQTT_QOS_AT_LEAST_ONCE = 1

ROOT = "udi/homekit/hubs"

BackoffSchedule = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0)


def _norm_rpc_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


class HubMqttClient:
    """
    Threaded asyncio MQTT client: connect, subscribe to hub egress topics, publish ``hello`` on
    ``in``, then process ``out/rpc`` and ``out/event`` (same JSON as WebSocket text frames).

    ``snapshot`` / ``get`` / ``command`` multiplexing matches :class:`HubWebSocketClient`.
    """

    def __init__(
        self,
        host: str,
        port: int = 1884,
        *,
        hub_slug: str = "default",
        client_slug: str = "udi-poly-ecobee",
        username: str = "",
        password: str = "",
        client_id: str = "udi-poly-ecobee",
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_list_devices: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_warnings: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
        on_transport_error: Optional[Callable[[str], None]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._host = (host or "localhost").strip() or "localhost"
        self._port = int(port) if port else 1884
        self._hub_slug = (hub_slug or "default").strip() or "default"
        self._client_slug = (client_slug or "udi-poly-ecobee").strip() or "udi-poly-ecobee"
        self._username = (username or "").strip()
        self._password = str(password or "")
        self._client_id = client_id
        self._on_event = on_event
        self._on_list_devices = on_list_devices
        self._on_warnings = on_warnings
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._on_transport_error = on_transport_error
        self._log = logger or logging.getLogger(__name__)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._devices: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._mqtt_pub: Any = None
        self._rpc_lock = threading.Lock()
        self._rpc_seq = 0
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._hello_ok = threading.Event()
        self._hub_rx_log_max = 65536
        self._in_topic = f"{ROOT}/{self._hub_slug}/clients/{self._client_slug}/in"
        self._rpc_topic = f"{ROOT}/{self._hub_slug}/clients/{self._client_slug}/out/rpc"
        self._event_topic = f"{ROOT}/{self._hub_slug}/clients/{self._client_slug}/out/event"

    @property
    def devices(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._devices)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main, name="ecobee-hk-mqtt", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._hello_ok.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=6.0)
        self._thread = None

    def wait_hello(self, timeout: float = 60.0) -> bool:
        return self._hello_ok.wait(timeout)

    def snapshot_sync(self, device_id: str, timeout: float = 45.0) -> List[Dict[str, Any]]:
        if not self.wait_hello(timeout):
            raise TimeoutError("HomeKit hub hello timeout")
        did = str(device_id or "").strip().lower()
        rid, fut = self._register_rpc("snapshot", did)
        asyncio.run_coroutine_threadsafe(self._send_snapshot(did, rid), self._must_loop())
        return fut.result(timeout=timeout)

    def get_sync(
        self,
        device_id: str,
        characteristics: List[str],
        timeout: float = 45.0,
    ) -> List[Dict[str, Any]]:
        if not self.wait_hello(timeout):
            raise TimeoutError("HomeKit hub hello timeout")
        did = str(device_id or "").strip().lower()
        rid, fut = self._register_rpc("get", did)
        asyncio.run_coroutine_threadsafe(self._send_get(did, characteristics, rid), self._must_loop())
        return fut.result(timeout=timeout)

    def command_sync(
        self,
        device_id: str,
        characteristic: str,
        value: Any,
        timeout: float = 30.0,
    ) -> bool:
        if not self.wait_hello(timeout):
            raise TimeoutError("HomeKit hub hello timeout")
        did = str(device_id or "").strip().lower()
        rid, fut = self._register_rpc("command", did)
        asyncio.run_coroutine_threadsafe(
            self._send_command(did, characteristic, value, rid),
            self._must_loop(),
        )
        return bool(fut.result(timeout=timeout))

    def send_subscribe(self, device_id: str, characteristic: str) -> None:
        asyncio.run_coroutine_threadsafe(
            self._send_json(
                {
                    "version": PROTOCOL_VERSION,
                    "action": "subscribe",
                    "device_id": device_id,
                    "characteristic": characteristic,
                }
            ),
            self._must_loop(),
        )

    def send_list_devices(self) -> None:
        asyncio.run_coroutine_threadsafe(
            self._send_json({"version": PROTOCOL_VERSION, "action": "list_devices"}),
            self._must_loop(),
        )

    def _must_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            raise RuntimeError("HomeKit MQTT event loop not started")
        return self._loop

    def _log_hub_inbound(self, data: Dict[str, Any]) -> None:
        if not self._log.isEnabledFor(logging.DEBUG):
            return
        try:
            s = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        except (TypeError, ValueError):
            s = repr(data)
        cap = int(getattr(self, "_hub_rx_log_max", 65536) or 65536)
        n = len(s)
        if n > cap:
            s = s[:cap] + f"\n... [homekit hub rx truncated, total {n} chars]"
        self._log.debug("homekit hub mqtt rx: %s", s)

    def _dispatch_hub_warnings(self, data: Dict[str, Any]) -> None:
        if "warnings" not in data:
            return
        raw = data.get("warnings")
        if raw is None:
            return
        if not isinstance(raw, list):
            self._log.debug("hub warnings: expected list, got %s", type(raw).__name__)
            return
        if not self._on_warnings:
            if raw:
                for w in raw:
                    if isinstance(w, dict):
                        self._log.warning("HomeKit hub (no on_warnings): %s", w)
            return
        try:
            self._on_warnings(raw)
        except Exception:
            self._log.exception("on_warnings callback failed")

    def _register_rpc(self, kind: str, device_id: Optional[str]) -> tuple[str, concurrent.futures.Future]:
        with self._rpc_lock:
            self._rpc_seq += 1
            rid = str(self._rpc_seq)
            fut: concurrent.futures.Future = concurrent.futures.Future()
            self._pending[rid] = {"kind": kind, "device_id": device_id, "fut": fut}
            return rid, fut

    def _finish_rpc_by_id(self, rid: str, result: Any = None, error: Optional[BaseException] = None) -> None:
        with self._rpc_lock:
            ctx = self._pending.pop(rid, None)
        if ctx is None:
            return
        fut = ctx["fut"]
        if fut.done():
            return
        if error is not None:
            fut.set_exception(error)
        else:
            fut.set_result(result)

    def _finish_all_pending(self, error: BaseException) -> None:
        with self._rpc_lock:
            items = list(self._pending.items())
            self._pending.clear()
        for _rid, ctx in items:
            fut = ctx["fut"]
            if not fut.done():
                fut.set_exception(error)

    def _pending_rids_for_kind(self, kind: str) -> List[str]:
        with self._rpc_lock:
            return [rid for rid, c in self._pending.items() if c.get("kind") == kind]

    def _pending_rids_for_kind_device(self, kind: str, device_id: str) -> List[str]:
        did = str(device_id or "").strip().lower()
        with self._rpc_lock:
            return [
                rid
                for rid, c in self._pending.items()
                if c.get("kind") == kind and str(c.get("device_id") or "").strip().lower() == did
            ]

    def _finish_rpc_legacy_command_ok(self) -> None:
        cands = self._pending_rids_for_kind("command")
        if len(cands) == 1:
            self._finish_rpc_by_id(cands[0], result=True)
        elif len(cands) > 1:
            self._log.warning("HomeKit hub command ack without id: %d pending; need hub echo id", len(cands))

    def _finish_rpc_legacy_snapshot_get(self, data: Dict[str, Any], kind: str) -> None:
        did = str(data.get("device_id") or "").strip().lower()
        cands = self._pending_rids_for_kind_device(kind, did)
        if len(cands) == 1:
            self._finish_rpc_by_id(cands[0], result=data.get("values") or [])
        elif len(cands) > 1:
            self._log.warning(
                "HomeKit hub %s without id: ambiguous device_id=%r (%d pending)",
                kind,
                did,
                len(cands),
            )

    def _finish_rpc_legacy_error(self, for_what: Any, message: str) -> None:
        fw = str(for_what or "")
        cands = self._pending_rids_for_kind(fw) if fw in ("command", "snapshot", "get") else []
        if len(cands) == 1:
            self._finish_rpc_by_id(cands[0], error=RuntimeError(message))
        elif not cands:
            self._log.warning("HomeKit hub error (no pending %s): %s", fw, message)
        else:
            self._log.warning("HomeKit hub error without id: ambiguous for=%s (%d pending)", fw, len(cands))

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_forever())

    async def _run_forever(self) -> None:
        attempt = 0
        while not self._stop.is_set():
            try:
                await self._one_connection()
                attempt = 0
            except Exception as err:
                self._log.warning("HomeKit hub MQTT error: %s", err, exc_info=True)
                self._hello_ok.clear()
                if self._on_transport_error:
                    try:
                        self._on_transport_error(str(err))
                    except Exception:
                        self._log.exception("on_transport_error callback failed")
                if self._on_disconnected:
                    try:
                        self._on_disconnected()
                    except Exception:
                        pass
                self._finish_all_pending(RuntimeError(str(err)))
                delay = BackoffSchedule[min(attempt, len(BackoffSchedule) - 1)]
                attempt += 1
                t0 = time.monotonic()
                while time.monotonic() - t0 < delay:
                    if self._stop.is_set():
                        return
                    await asyncio.sleep(0.05)

    async def _one_connection(self) -> None:
        self._hello_ok.clear()
        with self._lock:
            self._devices = []
        client_kw: dict[str, Any] = {"hostname": self._host, "port": self._port}
        if self._username:
            client_kw["username"] = self._username
            client_kw["password"] = self._password
        self._log.info(
            "HomeKit hub MQTT: connecting to %s:%s (ingress publish topic %s)",
            self._host,
            self._port,
            self._in_topic,
        )
        async with aiomqtt.Client(**client_kw) as client:
            self._mqtt_pub = client
            await client.subscribe(self._rpc_topic, qos=MQTT_QOS_AT_LEAST_ONCE)
            await client.subscribe(self._event_topic, qos=MQTT_QOS_AT_LEAST_ONCE)
            self._log.info(
                "HomeKit hub MQTT: subscribed to %s and %s; sending hello",
                self._rpc_topic,
                self._event_topic,
            )
            await self._send_hello()
            try:
                await self._read_loop(client)
            finally:
                self._mqtt_pub = None
                self._hello_ok.clear()
                self._finish_all_pending(RuntimeError("connection closed"))

    async def _send_json(self, msg: Dict[str, Any]) -> None:
        if self._mqtt_pub is None:
            raise RuntimeError("HomeKit hub MQTT not connected")
        line = json.dumps(msg)
        await self._mqtt_pub.publish(
            self._in_topic,
            payload=line.encode("utf-8"),
            qos=MQTT_QOS_AT_LEAST_ONCE,
            retain=False,
        )

    async def _send_hello(self) -> None:
        msg: Dict[str, Any] = {
            "version": PROTOCOL_VERSION,
            "action": "hello",
            "client": self._client_id,
        }
        await self._send_json(msg)

    async def _send_snapshot(self, device_id: str, rid: str) -> None:
        try:
            await self._send_json(
                {
                    "version": PROTOCOL_VERSION,
                    "action": "snapshot",
                    "device_id": device_id,
                    "id": rid,
                }
            )
        except Exception as e:
            self._finish_rpc_by_id(rid, error=e)

    async def _send_get(self, device_id: str, characteristics: List[str], rid: str) -> None:
        try:
            await self._send_json(
                {
                    "version": PROTOCOL_VERSION,
                    "action": "get",
                    "device_id": device_id,
                    "characteristics": characteristics,
                    "id": rid,
                }
            )
        except Exception as e:
            self._finish_rpc_by_id(rid, error=e)

    async def _send_command(self, device_id: str, characteristic: str, value: Any, rid: str) -> None:
        try:
            await self._send_json(
                {
                    "version": PROTOCOL_VERSION,
                    "action": "command",
                    "device_id": device_id,
                    "characteristic": characteristic,
                    "value": value,
                    "id": rid,
                }
            )
        except Exception as e:
            self._finish_rpc_by_id(rid, error=e)

    def _route_rpc_message(self, data: Dict[str, Any]) -> None:
        act = data.get("action")
        rid = _norm_rpc_id(data.get("id"))

        if act == "error":
            msg = data.get("message", "hub error")
            for_what = data.get("for")
            if rid:
                self._finish_rpc_by_id(rid, error=RuntimeError(str(msg)))
                return
            self._finish_rpc_legacy_error(for_what, str(msg))
            return

        if rid:
            if act == "ack" and data.get("for") == "command":
                with self._rpc_lock:
                    ctx = self._pending.get(rid)
                    ok = ctx is not None and ctx.get("kind") == "command"
                if ok:
                    self._finish_rpc_by_id(rid, result=True)
                else:
                    self._log.debug("command ack id=%s no matching pending command", rid)
                return
            if act == "snapshot":
                with self._rpc_lock:
                    ctx = self._pending.get(rid)
                    ok = ctx is not None and ctx.get("kind") == "snapshot"
                if ok:
                    self._finish_rpc_by_id(rid, result=data.get("values") or [])
                else:
                    self._log.debug("snapshot id=%s no matching pending snapshot", rid)
                return
            if act == "get":
                with self._rpc_lock:
                    ctx = self._pending.get(rid)
                    ok = ctx is not None and ctx.get("kind") == "get"
                if ok:
                    self._finish_rpc_by_id(rid, result=data.get("values") or [])
                else:
                    self._log.debug("get id=%s no matching pending get", rid)
                return
            return

        if act == "ack" and data.get("for") == "command":
            self._finish_rpc_legacy_command_ok()
            return
        if act == "snapshot":
            self._finish_rpc_legacy_snapshot_get(data, "snapshot")
            return
        if act == "get":
            self._finish_rpc_legacy_snapshot_get(data, "get")
            return

    async def _read_loop(self, client: Any) -> None:
        hello_ok = False
        try:
            async for message in client.messages:
                if self._stop.is_set():
                    break
                topic_s = str(message.topic)
                payload = message.payload
                if isinstance(payload, (bytes, bytearray)):
                    raw = bytes(payload).decode("utf-8")
                else:
                    raw = str(payload)
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict):
                    continue
                self._log_hub_inbound(data)
                act = data.get("action")
                if topic_s == self._event_topic:
                    if not hello_ok:
                        continue
                    if act == "event" and self._on_event:
                        try:
                            self._on_event(data)
                        except Exception:
                            self._log.exception("on_event callback failed")
                    continue
                if topic_s != self._rpc_topic:
                    continue
                if act == "error" and not hello_ok:
                    raise RuntimeError(data.get("message", "hub error"))
                if act == "ack" and data.get("for") == "hello":
                    hello_ok = True
                    self._hello_ok.set()
                    self._dispatch_hub_warnings(data)
                    raw_devs = data.get("devices")
                    devs = list(raw_devs) if isinstance(raw_devs, list) else []
                    with self._lock:
                        self._devices = devs
                    if self._on_list_devices:
                        self._on_list_devices(devs)
                    if self._on_connected:
                        try:
                            self._on_connected()
                        except Exception:
                            self._log.exception("on_connected callback failed")
                    continue
                if not hello_ok:
                    self._log.debug("Ignoring pre-hello message: %s", data)
                    continue
                if act == "event":
                    if self._on_event:
                        try:
                            self._on_event(data)
                        except Exception:
                            self._log.exception("on_event callback failed")
                    continue
                if act == "list_devices":
                    self._dispatch_hub_warnings(data)
                    devs = data.get("devices") or []
                    with self._lock:
                        self._devices = devs
                    if self._on_list_devices:
                        self._on_list_devices(devs)
                    continue
                self._route_rpc_message(data)
        finally:
            if self._on_disconnected:
                try:
                    self._on_disconnected()
                except Exception:
                    pass
