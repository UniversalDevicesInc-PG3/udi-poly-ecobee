#!/usr/bin/env python3
"""HomeKit hub backend: WebSocket to udi-poly-homekit, node sync (incremental)."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from udi_interface import LOG_HANDLER, LOGGER

from homekit_client import HubMqttClient, HubWebSocketClient
from homekit_client.hap_apply import hap_name_vendor_ecobee_current_mode, is_ecobee_current_mode_characteristic
from homekit_client.char_map import (
    CharBucket,
    accessory_display_name_from_snapshot_rows,
    builtin_motion_sensor_ambient_mirror,
    builtin_motion_sensor_mirror_characteristic,
    classify,
    is_builtin_room_sensor_signal,
    normalize_hap_uuid,
    thermostat_control_aid_from_snapshot_values,
)
from homekit_client.mapping import remote_sensor_address, resolve_thermostat_address
from homekit_client.profile_writer import (
    homekit_climate_details_for_device,
    profile_needs_update,
    write_ecobee_climate_profile,
)
from node_funcs import (
    climateList,
    customdata_load_payload,
    customdata_user_snapshot,
    get_profile_info,
    get_valid_node_name,
    notice_html_with_timestamp,
)
from params_flat import DEFAULT_EFFECTIVE

from .Sensor import HomeKitSensor
from .Thermostat import HomeKitThermostat

# Must match typed param ``name`` in :class:`nodes.Controller` (schema only; avoid importing Controller).
_TYPED_HK_ID_OVERRIDES = 'hk_id_overrides'
_TYPED_HK_SENSOR_OVERRIDES = 'hk_sensor_overrides'
_TYPED_CLIMATE_PROGRAMS = 'climate_programs'

# HAP UUIDs: hub may emit only UUID strings; refresh snapshot when these change (picks up GV3 etc.).
_THERM_SNAPSHOT_REFRESH_UUID_NORM = frozenset(
    x
    for x in (
        normalize_hap_uuid('00000012-0000-1000-8000-0026BB765291'),
        normalize_hap_uuid('0000000D-0000-1000-8000-0026BB765291'),
        normalize_hap_uuid('00000033-0000-1000-8000-0026BB765291'),
    )
    if x
)

# IoX controller **GV4** (WebSocket) / **GV5** (MQTT), UOM 25 index (same labels as udi-poly-homekit hub **GV1**).
_HK_PATH_UNUSED = 0
_HK_PATH_NOT_CONNECTED = 1
_HK_PATH_CONNECTED = 2

_HK_TRANSPORT_RESTART_KEYS: Tuple[str, ...] = (
    'hk_transport',
    'hk_ws_url',
    'hk_ws_token',
    'hk_mqtt_host',
    'hk_mqtt_port',
    'hk_mqtt_username',
    'hk_mqtt_password',
    'hk_mqtt_hub_slug',
    'hk_mqtt_client_slug',
)

# Avoid flooding PG3 Notices when the hub client drops and reconnects in a tight loop.
_HK_DISCONNECT_NOTICE_DEBOUNCE_SEC = 45.0


def _normalize_hap_command_value(characteristic: str, value: Any) -> Any:
    """Round noisy float targets from IoX (e.g. °F→°C) before HAP ``put_characteristics``."""
    if not isinstance(value, float):
        return value
    ch = str(characteristic or '')
    if 'Temperature' not in ch:
        return value
    return round(value, 2)


class HomeKitBackend:
    """Runs against :class:`nodes.Controller` (dispatcher) for IoX node lifecycle."""

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.poly = dispatcher.poly
        self.address = dispatcher.address
        self.name = 'Ecobee Controller'
        self.Notices = dispatcher.Notices
        self.Data = dispatcher.Data
        self.Params = dispatcher.Params
        self.TypedData = dispatcher.TypedData
        self.hb = 0
        self.ready = False
        self._ws: Optional[HubWebSocketClient | HubMqttClient] = None
        self.handler_config_st = None
        self.handler_config_done_st = None
        self.handler_params_st = None
        self.handler_data_st = None
        self.handler_nsdata_st = True
        self.n_queue: List[str] = []
        self._thermostat_by_device: Dict[str, HomeKitThermostat] = {}
        self._thermostat_primary_aid: Dict[str, int] = {}
        self._sensor_by_key: Dict[Tuple[str, int], HomeKitSensor] = {}
        self._motion_sensor_by_device: Dict[str, HomeKitSensor] = {}
        self._hk_existing_sensor_addnode_retried: Set[str] = set()
        self._unknown_char_logged: Set[str] = set()
        self._list_devices_lock = threading.Lock()
        self._thermostat_snapshot_timers: Dict[str, threading.Timer] = {}
        self._thermostat_snapshot_timer_lock = threading.Lock()
        # Skip redundant full snapshot after duplicate ``list_devices`` / hello ``devices[]`` (same topology).
        self._list_devices_topology_fp: Optional[str] = None
        self._list_devices_force_snapshot_resync: bool = False
        self._hk_suppress_transport_callbacks: bool = False
        self._hk_client_generation: int = 0
        self._hk_active_transport: Optional[str] = None
        self._hk_last_transport_snap: Optional[Dict[str, str]] = None
        self._hk_last_disconnect_notice_monotonic: float = 0.0
        self._unknown_char_notice_lines: List[str] = []

    def _set_notice_html(self, key: str, body_html: str) -> None:
        self.Notices[key] = notice_html_with_timestamp(body_html)

    def _pg3_warn_and_notice(
        self,
        notice_key: str,
        *,
        title: str,
        log_message: str,
        notice_html: str,
        emit_notice: bool = True,
    ) -> None:
        """Log **WARNING** and optionally set a PG3 **Notice** (HTML body is concatenated after the title).

        Same pattern as **udi-poly-homekit** ``nodes.Controller._pg3_warn_and_notice`` (duplicated on purpose so
        each Node Server stays self-contained—no cross-package coupling).
        """
        LOGGER.warning('%s', log_message)
        if not emit_notice:
            return
        try:
            self._set_notice_html(
                notice_key,
                f'<p><b>{html.escape(title)}</b></p>'
                f'{notice_html}'
                '<p>See the Node Server log for details.</p>',
            )
        except Exception:
            LOGGER.exception('HomeKit: failed to set PG3 Notice %r', notice_key)

    def _notice_homekit_hub_rpc_command_error(
        self,
        *,
        device_id: str,
        characteristic: str,
        value: Any,
        message: str,
    ) -> None:
        """Mirror **udi-poly-homekit** hub ``hub_rpc_error_notice`` on **this** Node Server’s Notices.

        The hub asyncio bridge sets ``homekit_hub_rpc_error`` on the HomeKit NS only; Ecobee’s
        :meth:`hub_command` runs here and must set the same key so operators see the failure on
        the Ecobee PG3 notices panel.
        """
        did = str(device_id or '').strip()
        ch = str(characteristic or '').strip()
        msg = str(message or '').strip() or 'hub error'
        parts: list[str] = [f'<p><code>command</code>: {html.escape(msg)}</p>']
        if did:
            parts.append(f'<p>device_id: <code>{html.escape(did)}</code></p>')
        tr = str(self.dispatcher.effective_params.get('hk_transport', DEFAULT_EFFECTIVE['hk_transport'])).strip().lower()
        if tr == 'mqtt':
            slug = str(self.dispatcher.effective_params.get('hk_mqtt_client_slug') or '').strip()
            if not slug:
                slug = 'udi-poly-ecobee'
            parts.append(f'<p>MQTT client_slug: <code>{html.escape(slug)}</code></p>')
        else:
            parts.append('<p>Transport: <code>WebSocket</code></p>')
        if ch:
            parts.append(f'<p>characteristic: <code>{html.escape(ch)}</code></p>')
        try:
            v_repr = repr(value)
            if len(v_repr) > 200:
                v_repr = v_repr[:200] + '…'
            parts.append(f'<p>value: <code>{html.escape(v_repr)}</code></p>')
        except Exception:
            pass
        self._pg3_warn_and_notice(
            'homekit_hub_rpc_error',
            title='HomeKit hub client RPC error',
            log_message=f'HomeKit hub RPC error (command): {msg}',
            notice_html=''.join(parts),
        )

    def _plugin_root(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent.parent

    def node_queue(self, data: Dict[str, Any]) -> None:
        self.n_queue.append(data['address'])

    def wait_for_node_done(self) -> None:
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()

    def add_node(self, node: Any) -> Any:
        anode = self.poly.addNode(node)
        LOGGER.debug('HomeKit addNode -> %s', anode)
        self.wait_for_node_done()
        if anode is None:
            LOGGER.error('HomeKit: failed to add node')
        return anode

    def close(self) -> None:
        self._hk_suppress_transport_callbacks = True
        try:
            self._hk_client_generation += 1
            self._hk_active_transport = None
            self._cancel_all_thermostat_snapshot_timers()
            self._list_devices_topology_fp = None
            self._list_devices_force_snapshot_resync = False
            if self._ws is not None:
                client = self._ws
                # Prevent a retiring retry thread from re-adding stale disconnect notices
                # after a transport switch (for example WebSocket -> MQTT).
                for attr in ('_on_connected', '_on_disconnected', '_on_transport_error'):
                    try:
                        setattr(client, attr, None)
                    except Exception:
                        LOGGER.debug('detach HomeKit client callback %s failed', attr, exc_info=True)
                client.stop()
                self._ws = None
        finally:
            self._hk_suppress_transport_callbacks = False

    def _hk_transport_snap(self) -> Dict[str, str]:
        p = self.dispatcher.effective_params
        return {k: str(p.get(k, '') or '') for k in _HK_TRANSPORT_RESTART_KEYS}

    def _set_hk_ws_path_driver(self, code: int) -> None:
        try:
            self.dispatcher.setDriver('GV4', int(code), uom=25, report=True, force=True)
        except Exception:
            LOGGER.exception('setDriver GV4 (HomeKit WebSocket path) failed')

    def _set_hk_mqtt_path_driver(self, code: int) -> None:
        try:
            self.dispatcher.setDriver('GV5', int(code), uom=25, report=True, force=True)
        except Exception:
            LOGGER.exception('setDriver GV5 (HomeKit MQTT path) failed')

    def _prime_hk_path_drivers_for_transport(self, tr: str) -> None:
        """Inactive path = **0**, active path = **1** (connecting) before the client thread starts."""
        if tr == 'mqtt':
            self._set_hk_ws_path_driver(_HK_PATH_UNUSED)
            self._set_hk_mqtt_path_driver(_HK_PATH_NOT_CONNECTED)
        else:
            self._set_hk_mqtt_path_driver(_HK_PATH_UNUSED)
            self._set_hk_ws_path_driver(_HK_PATH_NOT_CONNECTED)

    def handler_config(self, cfg_data):
        LOGGER.info('hk cfg_data=%s', cfg_data)
        self.cfg_longPoll = int(cfg_data['longPoll'])
        self.handler_config_st = True

    def handler_config_done(self):
        LOGGER.info('hk config done')
        self.poly.addLogLevel('DEBUG_SESSION', 9, 'Debug + Session')
        self.poly.addLogLevel('DEBUG_SESSION_VERBOSE', 8, 'Debug + Session Verbose')
        self.handler_config_done_st = True

    def handler_params(self, params):
        LOGGER.debug('hk handler_params')
        self.Params.load(params)
        self.handler_params_st = True
        new_snap = self._hk_transport_snap()
        prev = self._hk_last_transport_snap
        if self.ready and prev is not None and new_snap != prev:
            changed = sorted(k for k in new_snap if new_snap.get(k) != prev.get(k))
            LOGGER.info(
                'HomeKit hub transport or broker/WS settings changed (%s); restarting client (%s)',
                ', '.join(changed) if changed else 'keys',
                str(self.dispatcher.effective_params.get('hk_transport', DEFAULT_EFFECTIVE['hk_transport'])).strip().lower(),
            )
            self._start_ws()
        else:
            self._hk_last_transport_snap = new_snap

    def sync_param_notices(self) -> None:
        """Refresh HomeKit notices that depend on flat params (e.g. dry_run)."""
        dr = str(self.dispatcher.effective_params.get('dry_run', 'false')).strip().lower()
        if dr == 'true':
            self._set_notice_html(
                'homekit_dry_run',
                'HomeKit <b>dry_run</b> is enabled: commands to the hub are logged only, not sent. '
                'Set Custom Param <code>dry_run</code> to <code>false</code> to allow writes.',
            )
        else:
            try:
                self.Notices.delete('homekit_dry_run')
            except Exception:
                LOGGER.debug('delete homekit_dry_run notice failed', exc_info=True)

    def handler_data(self, data):
        LOGGER.debug('hk handler_data')
        if data is None:
            self.handler_data_st = False
            return
        payload = customdata_load_payload(data)
        if payload is None:
            payload = {}
        self.Data.load(payload)
        self.handler_data_st = True

    def handler_typed_params(self, _data):
        # Climate labels live in TypedData; :meth:`handler_typed_data` loads them then calls
        # ``_on_list_devices``, which rebuilds the profile. Avoid syncing here (stale TypedData).
        return

    def handler_typed_data(self, data):
        if data is not None:
            self.TypedData.load(data)
        devs = self._ws.devices if self._ws else []
        if devs:
            self._on_list_devices(devs)

    def handler_log_level(self, level):
        lvl = level.get('level', 10) if isinstance(level, dict) else 10
        if lvl < 10:
            LOG_HANDLER.set_basic_config(True, logging.DEBUG)
        else:
            LOG_HANDLER.set_basic_config(True, logging.WARNING)

    def handler_start(self):
        self.Notices.clear()
        self._unknown_char_logged.clear()
        self._unknown_char_notice_lines.clear()
        LOGGER.info('Started Ecobee NodeServer (HomeKit backend) %s', self.poly.serverdata.get('version'))
        cnt = 10
        while (
            (self.handler_config_done_st is None or self.handler_params_st is None or self.handler_data_st is None)
            or self.handler_config_st is None
        ) and cnt > 0:
            LOGGER.warning(
                'HK waiting for PG3 handlers config=%s done=%s params=%s data=%s cnt=%s',
                self.handler_config_st,
                self.handler_config_done_st,
                self.handler_params_st,
                self.handler_data_st,
                cnt,
            )
            time.sleep(1)
            cnt -= 1
        if cnt == 0:
            LOGGER.error('HomeKit backend: timed out waiting for PG3 startup handlers')
        self.dispatcher.setDriver('GV1', 0)
        self.dispatcher.setDriver('GV3', 0)
        try:
            self.dispatcher.setDriver('GV4', _HK_PATH_UNUSED, uom=25, report=True, force=True)
            self.dispatcher.setDriver('GV5', _HK_PATH_UNUSED, uom=25, report=True, force=True)
        except Exception:
            LOGGER.exception('setDriver GV4/GV5 at HomeKit backend start')
        self.sync_param_notices()
        self._start_ws()
        self.ready = True

    def _start_ws(self) -> None:
        p = self.dispatcher.effective_params
        tr = str(p.get('hk_transport', DEFAULT_EFFECTIVE['hk_transport'])).strip().lower()
        self._prime_hk_path_drivers_for_transport(tr)
        self.close()
        self._hk_client_generation += 1
        gen = self._hk_client_generation
        self._hk_active_transport = tr
        if tr == 'mqtt':
            try:
                port = int(str(p.get('hk_mqtt_port') or DEFAULT_EFFECTIVE['hk_mqtt_port']).strip())
            except (TypeError, ValueError):
                port = int(DEFAULT_EFFECTIVE['hk_mqtt_port'])
            mqtt_client_slug = str(
                p.get('hk_mqtt_client_slug') or DEFAULT_EFFECTIVE['hk_mqtt_client_slug']
            ).strip()
            host = str(p.get('hk_mqtt_host') or DEFAULT_EFFECTIVE.get('hk_mqtt_host') or 'localhost').strip() or 'localhost'
            hub_slug = str(p.get('hk_mqtt_hub_slug') or 'default').strip() or 'default'
            LOGGER.info(
                'HomeKit hub: starting MQTT client %s:%s hub_slug=%r client_slug=%r',
                host,
                port,
                hub_slug,
                mqtt_client_slug,
            )
            self._ws = HubMqttClient(
                host,
                port,
                hub_slug=hub_slug,
                client_slug=mqtt_client_slug,
                username=str(p.get('hk_mqtt_username') or ''),
                password=str(p.get('hk_mqtt_password') or ''),
                client_id=mqtt_client_slug,
                on_event=self._on_hap_event,
                on_list_devices=self._on_list_devices,
                on_warnings=self._on_hub_warnings,
                on_connected=lambda tr=tr, gen=gen: self._on_ws_connected(tr, gen),
                on_disconnected=lambda tr=tr, gen=gen: self._on_ws_disconnected(tr, gen),
                on_transport_error=lambda message, tr=tr, gen=gen: self._on_ws_transport_error(message, tr, gen),
                logger=LOGGER,
            )
        else:
            url = p.get('hk_ws_url', 'ws://127.0.0.1:8163')
            token = p.get('hk_ws_token', '') or ''
            LOGGER.info('HomeKit hub: starting WebSocket client %r', url)
            self._ws = HubWebSocketClient(
                url,
                token,
                on_event=self._on_hap_event,
                on_list_devices=self._on_list_devices,
                on_warnings=self._on_hub_warnings,
                on_connected=lambda tr=tr, gen=gen: self._on_ws_connected(tr, gen),
                on_disconnected=lambda tr=tr, gen=gen: self._on_ws_disconnected(tr, gen),
                on_transport_error=lambda message, tr=tr, gen=gen: self._on_ws_transport_error(message, tr, gen),
                logger=LOGGER,
            )
        self._ws.start()
        self._hk_last_transport_snap = self._hk_transport_snap()

    def _hk_callback_is_current(self, generation: Optional[int]) -> bool:
        if self._hk_suppress_transport_callbacks:
            return False
        if generation is None:
            return True
        if generation != self._hk_client_generation:
            LOGGER.debug(
                'Ignoring stale HomeKit transport callback generation=%s current=%s',
                generation,
                self._hk_client_generation,
            )
            return False
        return True

    def _hk_callback_transport(self, transport: Optional[str]) -> str:
        tr = str(transport or self._hk_active_transport or '').strip().lower()
        if tr in ('websocket', 'mqtt'):
            return tr
        return str(
            self.dispatcher.effective_params.get('hk_transport', DEFAULT_EFFECTIVE['hk_transport'])
        ).strip().lower()

    def _on_hub_warnings(self, warnings: List[Dict[str, Any]]) -> None:
        """
        Hub PROTOCOL ``warnings`` on hello ``ack`` and ``list_devices`` (udi-poly-homekit).
        Log each entry and mirror to PG3 Notices under ``homekit_hub_warnings``.
        """
        if not warnings:
            try:
                self.Notices.delete('homekit_hub_warnings')
            except Exception:
                LOGGER.debug('delete homekit_hub_warnings failed', exc_info=True)
            return
        lines: List[str] = []
        for w in warnings:
            if not isinstance(w, dict):
                continue
            lvl = str(w.get('level') or 'warning').strip().lower()
            code = html.escape(str(w.get('code') or 'unknown'))
            msg = html.escape(str(w.get('message') or ''))
            did = w.get('device_id')
            pa = w.get('primary_aid')
            extra_parts: List[str] = []
            if did is not None and str(did).strip():
                extra_parts.append(f'device <code>{html.escape(str(did).strip())}</code>')
            if pa is not None and str(pa).strip() != '':
                extra_parts.append(f'primary_aid={html.escape(str(pa))}')
            extra = ' (' + ', '.join(extra_parts) + ')' if extra_parts else ''
            line = f'<b>{html.escape(lvl)}</b> <code>{code}</code>: {msg}{extra}'
            lines.append(line)
            raw_msg = str(w.get('message') or '')
            if lvl == 'error':
                LOGGER.error('HomeKit hub warning %s: %s', w.get('code'), raw_msg)
            else:
                LOGGER.warning('HomeKit hub warning %s: %s', w.get('code'), raw_msg)
        if not lines:
            try:
                self.Notices.delete('homekit_hub_warnings')
            except Exception:
                pass
            return
        self._set_notice_html(
            'homekit_hub_warnings',
            '<p>From <b>udi-poly-homekit</b> hub (<code>warnings</code> in PROTOCOL):</p>'
            + '<br/>'.join(lines),
        )

    def _on_ws_connected(self, transport: Optional[str] = None, generation: Optional[int] = None) -> None:
        if not self._hk_callback_is_current(generation):
            return
        self.dispatcher.setDriver('GV1', 1)
        tr = self._hk_callback_transport(transport)
        if tr == 'mqtt':
            self._set_hk_ws_path_driver(_HK_PATH_UNUSED)
            self._set_hk_mqtt_path_driver(_HK_PATH_CONNECTED)
        else:
            self._set_hk_ws_path_driver(_HK_PATH_CONNECTED)
            self._set_hk_mqtt_path_driver(_HK_PATH_UNUSED)
        LOGGER.warning('HomeKit hub: hello OK (%s transport)', tr)
        for nk in ('homekit_hub_unreachable', 'homekit_hub_disconnected'):
            try:
                self.Notices.delete(nk)
            except Exception:
                LOGGER.debug('delete %s failed', nk, exc_info=True)
        # Pairing list is applied from hello ``ack`` ``devices[]`` in ``HubWebSocketClient`` (no bootstrap
        # ``list_devices`` on the hub). Proactive hub ``list_devices`` after pair/unpair still arrives here.

    def _on_ws_transport_error(
        self,
        message: str,
        transport: Optional[str] = None,
        generation: Optional[int] = None,
    ) -> None:
        """Hub transport connect/hello failure (WebSocket or MQTT)."""
        if not self._hk_callback_is_current(generation):
            return
        tr = self._hk_callback_transport(transport)
        if tr == 'mqtt':
            self._set_hk_mqtt_path_driver(_HK_PATH_NOT_CONNECTED)
        else:
            self._set_hk_ws_path_driver(_HK_PATH_NOT_CONNECTED)
        detail = html.escape(str(message or 'connection failed'))
        log_line = f'HomeKit hub transport error ({tr}): {message}'
        if tr == 'mqtt':
            self._pg3_warn_and_notice(
                'homekit_hub_unreachable',
                title='HomeKit hub MQTT failed',
                log_message=log_line,
                notice_html=(
                    f'<p><code>{detail}</code></p>'
                    '<p>Install and configure <b>udi-poly-homekit</b> with <code>mqtt_enable=true</code> and a LAN '
                    'broker, then set this Node Server <code>hk_transport</code> to <code>mqtt</code> and match '
                    '<code>hk_mqtt_*</code> Custom Params to the hub (<code>hk_mqtt_hub_slug</code> must match the '
                    'hub, <code>hk_mqtt_client_slug</code> must match the MQTT topic segment). See <b>README.md</b> '
                    'and <b>udi-poly-homekit</b> <b>PROTOCOL.md</b>.</p>'
                ),
            )
        else:
            self._pg3_warn_and_notice(
                'homekit_hub_unreachable',
                title='HomeKit hub WebSocket failed',
                log_message=log_line,
                notice_html=(
                    f'<p><code>{detail}</code></p>'
                    '<p>Install and configure <b>udi-poly-homekit</b> in Polyglot, pair your Ecobee(s), enable the '
                    'hub WebSocket (<code>ws_host</code> / <code>ws_port</code>), then set this Node Server '
                    'Custom Params <code>hk_ws_url</code> (and <code>hk_ws_token</code> if the hub requires it). '
                    'See <b>README.md</b> and <b>CONFIG.md</b>.</p>'
                ),
            )

    def _on_ws_disconnected(self, transport: Optional[str] = None, generation: Optional[int] = None) -> None:
        if not self._hk_callback_is_current(generation):
            return
        self.dispatcher.setDriver('GV1', 0)
        tr = self._hk_callback_transport(transport)
        if tr == 'mqtt':
            self._set_hk_mqtt_path_driver(_HK_PATH_NOT_CONNECTED)
        else:
            self._set_hk_ws_path_driver(_HK_PATH_NOT_CONNECTED)
        label = 'MQTT' if tr == 'mqtt' else 'WebSocket'
        log_line = (
            f'HomeKit hub {label} transport disconnected; the client will retry if the hub or broker is reachable.'
        )
        now = time.monotonic()
        if now - self._hk_last_disconnect_notice_monotonic >= _HK_DISCONNECT_NOTICE_DEBOUNCE_SEC:
            self._hk_last_disconnect_notice_monotonic = now
            self._pg3_warn_and_notice(
                'homekit_hub_disconnected',
                title=f'HomeKit hub {label} disconnected',
                log_message=log_line,
                notice_html=(
                    '<p>The hub client lost its session (network flap, hub restart, or broker drop). '
                    'If this keeps appearing, verify <b>udi-poly-homekit</b> is running, '
                    '<code>hk_transport</code> matches the hub, and broker ACLs allow this client.</p>'
                ),
            )
        else:
            LOGGER.warning('%s (PG3 Notice deduped for %.0fs)', log_line, _HK_DISCONNECT_NOTICE_DEBOUNCE_SEC)

    def _typed_list(self, key: str) -> List[Dict[str, Any]]:
        try:
            td = self.TypedData
            if key not in td:
                return []
            v = td[key]
            return v if isinstance(v, list) else []
        except Exception:
            LOGGER.debug('typed list %s unavailable', key, exc_info=True)
            return []

    def _existing_t_addresses(self) -> List[str]:
        out: List[str] = []
        try:
            for n in self.poly.nodes():
                a = getattr(n, 'address', None)
                if a and str(a).startswith('t'):
                    out.append(str(a))
        except Exception:
            LOGGER.debug('existing t* scan failed', exc_info=True)
        return out

    def _hk_id_override(self, device_id: str) -> Optional[str]:
        did = str(device_id or '').strip().lower()
        for row in self._typed_list(_TYPED_HK_ID_OVERRIDES):
            if str(row.get('device_id', '')).strip().lower() != did:
                continue
            tid = row.get('thermostat_id')
            if tid is not None and str(tid).strip():
                return str(tid).strip()
        return None

    def _hk_sensor_code_override(self, device_id: str, aid: int, accessory_name: Optional[str]) -> Optional[str]:
        did = str(device_id or '').strip().lower()
        aid_s = str(int(aid))
        name_l = (accessory_name or '').strip().lower()
        for row in self._typed_list(_TYPED_HK_SENSOR_OVERRIDES):
            if str(row.get('device_id', '')).strip().lower() != did:
                continue
            row_aid = str(row.get('aid', '')).strip()
            if row_aid and row_aid != aid_s:
                continue
            acc = str(row.get('accessory_name', '')).strip().lower()
            if acc and name_l and acc != name_l:
                continue
            code = row.get('code')
            if code is not None and str(code).strip():
                return str(code).strip()
        return None

    def _use_celsius(self) -> bool:
        uc = str(self.dispatcher.effective_params.get('use_celsius', 'auto')).lower()
        if uc == 'true':
            return True
        if uc == 'false':
            return False
        return False

    def _dry_run(self) -> bool:
        return str(self.dispatcher.effective_params.get('dry_run', 'false')).strip().lower() == 'true'

    def _maybe_update_profile(self, climates: Dict[str, List[Dict[str, str]]]) -> None:
        info = get_profile_info(LOGGER)
        ver = str(info.get('version', ''))
        data_dump = customdata_user_snapshot(self.Data)
        if not profile_needs_update(data_dump, ver, climates):
            return
        write_ecobee_climate_profile(
            self._plugin_root(),
            climates,
            log_prefix=f'{self.address}:hk_profile:',
            logger=LOGGER,
        )
        self.poly.updateProfile()
        self.Data['profile_info'] = info
        self.Data['climates'] = climates

    def _normalize_primary_aid(self, dev: Dict[str, Any]) -> int:
        try:
            p = int(dev.get('primary_aid') or 0)
        except (TypeError, ValueError):
            p = 0
        return p if p > 0 else 1

    @staticmethod
    def _hub_accessory_row_is_thermostat(acc: Any) -> bool:
        """True when per-accessory summary marks this aid as thermostat-like (hub PROTOCOL ``accessories[]``)."""
        if not isinstance(acc, dict):
            return False
        cat = acc.get('category')
        try:
            ci = int(cat) if cat is not None else 0
        except (TypeError, ValueError):
            ci = 0
        label = str(acc.get('category_label') or '').upper()
        if ci == 9 or label == 'THERMOSTAT':
            return True
        tl = acc.get('thermostat_like')
        if tl is True:
            return True
        if isinstance(tl, str) and tl.strip().lower() in ('true', '1', 'yes'):
            return True
        return False

    def _thermostat_aids_from_accessories(self, dev: Dict[str, Any]) -> List[int]:
        raw = dev.get('accessories')
        if not isinstance(raw, list) or not raw:
            return []
        aids: List[int] = []
        for acc in raw:
            if not self._hub_accessory_row_is_thermostat(acc):
                continue
            try:
                a = int(acc.get('aid') or 0)
            except (TypeError, ValueError):
                continue
            if a > 0:
                aids.append(a)
        return aids

    def _hub_row_has_thermostat_accessory(self, dev: Dict[str, Any]) -> bool:
        return bool(self._thermostat_aids_from_accessories(dev))

    def _thermostat_primary_aid_from_hub_row(self, dev: Dict[str, Any]) -> int:
        aids = self._thermostat_aids_from_accessories(dev)
        if aids:
            return min(aids)
        return self._normalize_primary_aid(dev)

    def _thermostat_display_name_from_hub_row(self, dev: Dict[str, Any]) -> str:
        """Prefer the Accessory Information name for the thermostat ``aid`` from ``accessories[]``."""
        prim = self._thermostat_primary_aid_from_hub_row(dev)
        raw = dev.get('accessories')
        if isinstance(raw, list):
            for acc in raw:
                if not isinstance(acc, dict):
                    continue
                try:
                    a = int(acc.get('aid') or 0)
                except (TypeError, ValueError):
                    continue
                if a != prim:
                    continue
                nm = str(acc.get('name') or '').strip()
                if nm:
                    return nm
        top = str(dev.get('name') or '').strip()
        return top or 'Thermostat'

    def _prefetch_remote_sensors_from_accessories(
        self,
        dev: Dict[str, Any],
        device_id: str,
        thermostat_addr: str,
        use_c: bool,
        prim_aid: int,
    ) -> None:
        """Register sensor nodes early using hub ``accessories[]`` names (snapshot may follow)."""
        raw = dev.get('accessories')
        if not isinstance(raw, list) or not raw:
            return
        did = device_id.strip().lower()
        for acc in raw:
            if not isinstance(acc, dict):
                continue
            try:
                aid = int(acc.get('aid') or 0)
            except (TypeError, ValueError):
                continue
            if aid <= 0 or aid == prim_aid:
                continue
            nm = str(acc.get('name') or '').strip()
            if not nm:
                continue
            self._ensure_remote_sensor(
                did,
                aid,
                thermostat_addr,
                use_c,
                accessory_name=nm,
                register_only=False,
            )

    @staticmethod
    def _hap_category_int(dev: Dict[str, Any]) -> int:
        c = dev.get('category')
        if c is None:
            return 0
        try:
            return int(c)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _hub_device_id(dev: Any) -> str:
        """Hub PROTOCOL ``device_id`` on each ``list_devices`` / hello ``devices[]`` row."""
        if not isinstance(dev, dict):
            return ''
        v = dev.get('device_id')
        if v is None:
            return ''
        return str(v).strip().lower()

    def _thermostat_rows_from_hub(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Thermostat rows: pairing-level category 9 / THERMOSTAT, or per-aid summaries in ``accessories[]``."""
        rows: List[Dict[str, Any]] = []
        for d in devices:
            if not isinstance(d, dict) or not self._hub_device_id(d):
                continue
            cat = self._hap_category_int(d)
            label = str(d.get('category_label') or '').upper()
            if cat == 9 or label == 'THERMOSTAT' or self._hub_row_has_thermostat_accessory(d):
                rows.append(d)
        if rows:
            return rows
        snap: List[Dict[str, Any]] = []
        for d in devices:
            if not isinstance(d, dict):
                continue
            rid = self._hub_device_id(d)
            if not rid:
                continue
            snap.append(
                {
                    'device_id': rid,
                    'category': d.get('category'),
                    'category_label': d.get('category_label'),
                    'manufacturer': d.get('manufacturer'),
                    'model': d.get('model'),
                    'name': d.get('name'),
                    'accessories': d.get('accessories'),
                }
            )
        if snap:
            LOGGER.warning(
                'HomeKit: no thermostat rows (need category 9 / THERMOSTAT, or hub accessories[] '
                'with thermostat-like children). Paired device metadata: %s',
                snap,
            )
        return []

    @staticmethod
    def _hub_devices_topology_fingerprint(devices: list) -> str:
        """Stable hash of pairing topology (device_id, primary_aid, accessory aids). Ignores volatile metadata."""
        rows: List[tuple] = []
        for d in devices or []:
            if not isinstance(d, dict):
                continue
            did = str(d.get('device_id') or '').strip().lower()
            if not did:
                continue
            pa = d.get('primary_aid')
            try:
                pa_v = int(pa) if pa is not None else None
            except (TypeError, ValueError):
                pa_v = None
            aids: List[tuple] = []
            acc = d.get('accessories')
            if isinstance(acc, list):
                for a in acc:
                    if not isinstance(a, dict):
                        continue
                    try:
                        aid_v = int(a.get('aid'))
                    except (TypeError, ValueError):
                        continue
                    aids.append(
                        (
                            aid_v,
                            str(a.get('serial_number') or '').strip(),
                            str(a.get('name') or '').strip().lower(),
                        )
                    )
            aids.sort(key=lambda t: t[0])
            rows.append((did, pa_v, tuple(aids)))
        rows.sort(key=lambda r: r[0])
        blob = json.dumps(rows, separators=(',', ':'))
        return hashlib.sha256(blob.encode('utf-8')).hexdigest()

    def _notice_no_thermostat_metadata(self, devices: list) -> None:
        """PG3 Notice when hub sent device rows but none qualify as thermostats."""
        try:
            blob = json.dumps(devices, default=str, indent=2)
            if len(blob) > 4500:
                blob = blob[:4500] + '\n…'
            safe = html.escape(blob)
            self._set_notice_html(
                'homekit_no_thermostat',
                '<p><b>HomeKit</b>: could not derive a thermostat from hub <code>list_devices</code>. '
                'Each row needs a non-empty <code>device_id</code> and either pairing-level HAP '
                '<b>category</b> 9 / <code>category_label</code> THERMOSTAT, or per-aid summaries in '
                '<code>accessories[]</code> (category 9, THERMOSTAT, or <code>thermostat_like</code>). '
                'Update <b>udi-poly-homekit</b> if metadata is incomplete; see hub PROTOCOL.</p>'
                f'<pre style="white-space:pre-wrap">{safe}</pre>',
            )
        except Exception:
            LOGGER.exception('homekit_no_thermostat notice failed')

    def _on_list_devices(self, devices: list) -> None:
        """
        Hub invokes this from the WebSocket asyncio thread. Do not call ``snapshot_sync`` here:
        it blocks that thread and prevents the read loop from receiving the snapshot reply
        (deadlock / ``RPC busy``). Process on a background thread.
        """
        snap = list(devices or [])

        def worker() -> None:
            try:
                with self._list_devices_lock:
                    self._on_list_devices_inner(snap)
            except Exception:
                LOGGER.exception('HomeKit _on_list_devices worker failed')

        threading.Thread(target=worker, daemon=True, name='hk-on-list-devices').start()

    def _on_list_devices_inner(self, devices: list) -> None:
        try:
            self.Notices.delete('homekit_no_thermostat')
        except Exception:
            LOGGER.debug('delete homekit_no_thermostat failed', exc_info=True)
        LOGGER.info(
            'HomeKit hub paired devices: %s',
            [self._hub_device_id(d) if isinstance(d, dict) else d for d in (devices or [])],
        )
        if devices:
            self.dispatcher.setDriver('GV3', 1)
        else:
            self.dispatcher.setDriver('GV3', 0)
        thermostats = self._thermostat_rows_from_hub(list(devices or []))
        if not thermostats:
            if devices:
                self._notice_no_thermostat_metadata(list(devices or []))
            self._list_devices_topology_fp = None
            return
        topo_fp = self._hub_devices_topology_fingerprint(list(devices or []))
        force_snap = self._list_devices_force_snapshot_resync
        if force_snap:
            self._list_devices_force_snapshot_resync = False
        skip_snapshot = (
            not force_snap
            and self._list_devices_topology_fp is not None
            and topo_fp == self._list_devices_topology_fp
        )
        if skip_snapshot:
            LOGGER.debug(
                'HomeKit list_devices: topology unchanged (fp=%s…); skip snapshot prefetch/sync',
                topo_fp[:12],
            )
        else:
            self._list_devices_topology_fp = topo_fp
        rows_climate = self._typed_list(_TYPED_CLIMATE_PROGRAMS)
        existing = self._existing_t_addresses()
        climates: Dict[str, List[Dict[str, str]]] = {}
        pairs: List[tuple] = []
        for dev in thermostats:
            did = self._hub_device_id(dev)
            serial = dev.get('serial_number')
            display_name = self._thermostat_display_name_from_hub_row(dev)
            override = self._hk_id_override(did)
            addr, reason = resolve_thermostat_address(
                did,
                str(serial).strip() if serial else None,
                display_name,
                existing,
                id_override=override,
            )
            LOGGER.info(
                'HomeKit thermostat map device_id=%s -> %s (%s)',
                did,
                addr,
                reason,
            )
            if addr not in existing:
                existing.append(addr)
            key = addr[1:] if addr.startswith('t') else addr
            climates[key] = homekit_climate_details_for_device(did, rows_climate, climateList)
            pairs.append((dev, addr, key))
        try:
            self._maybe_update_profile(climates)
        except Exception:
            LOGGER.exception('HomeKit profile update failed')
        use_c = self._use_celsius()
        for dev, addr, key in pairs:
            try:
                did = self._hub_device_id(dev).strip().lower()
                prim = self._thermostat_primary_aid_from_hub_row(dev)
                self._thermostat_primary_aid[did] = prim
                node = self.poly.getNode(addr)
                created = False
                if node is None:
                    label = get_valid_node_name(f"Ecobee - {self._thermostat_display_name_from_hub_row(dev)}")
                    node = HomeKitThermostat(
                        self.dispatcher,
                        addr,
                        addr,
                        label,
                        key,
                        use_c,
                        did,
                        hk=self,
                    )
                    self.add_node(node)
                    node = self.poly.getNode(addr)
                    created = True
                if isinstance(node, HomeKitThermostat):
                    self._thermostat_by_device[did] = node
                do_snapshot = (not skip_snapshot) or created
                if do_snapshot:
                    try:
                        self._prefetch_remote_sensors_from_accessories(dev, did, addr, use_c, prim)
                    except Exception:
                        LOGGER.debug(
                            'HomeKit prefetch sensors from hub accessories failed for %s',
                            did,
                            exc_info=True,
                        )
                    try:
                        self._sync_remote_sensors_from_snapshot(did, addr, use_c)
                    except Exception:
                        LOGGER.warning(
                            'HomeKit sensor sync from snapshot failed for %s (events may still populate)',
                            did,
                            exc_info=True,
                        )
                    if isinstance(node, HomeKitThermostat):
                        try:
                            node.reportDrivers()
                        except Exception:
                            LOGGER.debug(
                                'HomeKit thermostat reportDrivers after list_devices failed for %s',
                                did,
                                exc_info=True,
                            )
            except Exception:
                LOGGER.exception('HomeKit add thermostat %s failed', addr)

    def _sensor_nodedef_homekit(self, use_celsius: bool) -> str:
        return 'EcobeeSensorHC' if use_celsius else 'EcobeeSensorHF'

    def _snapshot_values_with_retry(self, device_id: str) -> List[Dict[str, Any]]:
        """Fetch hub snapshot rows (hub RPCs are serialized; retry is a narrow safety net)."""
        if not self._ws:
            return []
        did = device_id.strip().lower()
        try:
            return self._ws.snapshot_sync(did)
        except RuntimeError as e:
            msg = str(e).lower()
            if 'rpc busy' not in msg and 'busy' not in msg:
                raise
            time.sleep(0.08)
            return self._ws.snapshot_sync(did)

    def _get_values_with_retry(self, device_id: str, characteristics: List[str]) -> List[Dict[str, Any]]:
        """Hub ``get`` for selected characteristics (same row shape as ``snapshot`` ``values``)."""
        if not self._ws:
            return []
        did = device_id.strip().lower()
        chs = [str(c) for c in characteristics if c]
        if not chs:
            return []
        try:
            return self._ws.get_sync(did, chs)
        except RuntimeError as e:
            msg = str(e).lower()
            if 'rpc busy' not in msg and 'busy' not in msg:
                raise
            time.sleep(0.08)
            return self._ws.get_sync(did, chs)

    def _sync_remote_sensors_from_snapshot(self, device_id: str, thermostat_addr: str, use_c: bool) -> List[Dict[str, Any]]:
        if not self._ws:
            return []
        did = device_id.strip().lower()
        values = self._snapshot_values_with_retry(did)
        if not values:
            return []
        hub_prim = self._thermostat_primary_aid.get(did, 1)
        ctrl_aid = thermostat_control_aid_from_snapshot_values(values)
        if ctrl_aid is not None:
            if ctrl_aid != hub_prim:
                LOGGER.info(
                    'HomeKit: thermostat control aid=%s for device_id=%s (hub primary_aid=%s)',
                    ctrl_aid,
                    did,
                    hub_prim,
                )
            self._thermostat_primary_aid[did] = ctrl_aid
        prim = self._thermostat_primary_aid.get(did, 1)
        by_aid: Dict[int, List[Dict[str, Any]]] = {}
        for row in values:
            try:
                aid = int(row.get('aid'))
            except (TypeError, ValueError):
                continue
            by_aid.setdefault(aid, []).append(row)
        tnode = self._thermostat_by_device.get(did)
        prim_rows = by_aid.get(prim, [])
        if tnode and prim_rows:
            tlabel = accessory_display_name_from_snapshot_rows(prim_rows)
            if tlabel:
                new_nm = get_valid_node_name(f'Ecobee - {tlabel}')
                if new_nm != getattr(tnode, 'name', None):
                    try:
                        tnode.rename(new_nm)
                        tnode.name = new_nm
                    except Exception:
                        LOGGER.debug(
                            'HomeKit thermostat rename failed device_id=%s',
                            did,
                            exc_info=True,
                        )
        for aid, rows in by_aid.items():
            if aid == prim:
                if tnode:
                    motion_rows: List[Dict[str, Any]] = []
                    for r in rows:
                        ch = r.get('characteristic')
                        if not ch or 'value' not in r:
                            continue
                        cs = str(ch)
                        if is_builtin_room_sensor_signal(cs):
                            motion_rows.append(r)
                    if motion_rows:
                        hint = accessory_display_name_from_snapshot_rows(prim_rows) or getattr(
                            tnode, 'name', None
                        )
                        ms = self._ensure_builtin_motion_sensor(did, tnode, accessory_name_hint=hint)
                        if ms:
                            for r in rows:
                                ch = r.get('characteristic')
                                if not ch or 'value' not in r:
                                    continue
                                cs = str(ch)
                                if builtin_motion_sensor_mirror_characteristic(cs):
                                    ms.apply_hub_characteristic(cs, r.get('value'))
                continue
            acc_name = accessory_display_name_from_snapshot_rows(rows)
            self._ensure_remote_sensor(
                did,
                aid,
                thermostat_addr,
                use_c,
                accessory_name=acc_name,
                register_only=False,
            )
            s = self._sensor_by_key.get((did, aid))
            if s and acc_name:
                sn_new = get_valid_node_name(acc_name)
                if sn_new != getattr(s, 'name', None):
                    try:
                        s.rename(sn_new)
                        s.name = sn_new
                    except Exception:
                        LOGGER.debug(
                            'HomeKit sensor rename failed device_id=%s aid=%s',
                            did,
                            aid,
                            exc_info=True,
                        )
            if s:
                for r in rows:
                    ch = r.get('characteristic')
                    if ch and 'value' in r:
                        s.apply_hub_characteristic(str(ch), r.get('value'))
        if tnode:
            self._apply_snapshot_values(tnode, values)
        return values

    def _ensure_remote_sensor(
        self,
        device_id: str,
        aid: int,
        thermostat_primary_addr: str,
        use_c: bool,
        *,
        accessory_name: Optional[str],
        register_only: bool,
    ) -> Optional[HomeKitSensor]:
        did = device_id.strip().lower()
        key = (did, int(aid))
        if key in self._sensor_by_key:
            return self._sensor_by_key[key]
        code_ov = self._hk_sensor_code_override(did, int(aid), accessory_name)
        addr = remote_sensor_address(did, int(aid), accessory_name, code_override=code_ov)
        existing = self.poly.getNode(addr)
        if existing is not None and isinstance(existing, HomeKitSensor):
            self._sensor_by_key[key] = existing
            if not register_only:
                self._retry_existing_sensor_addnode(existing, addr)
            return existing
        if existing is not None:
            LOGGER.warning(
                'HomeKit sensor address %s is already used by a non-sensor node; skipping aid=%s',
                addr,
                aid,
            )
            return None
        if register_only:
            return None
        nd = self._sensor_nodedef_homekit(use_c)
        nm = get_valid_node_name(accessory_name or f'Ecobee - Sensor aid {aid}')
        node = HomeKitSensor(
            self.dispatcher,
            thermostat_primary_addr,
            addr,
            nm,
            nd,
            use_c,
            did,
            int(aid),
            hk=self,
        )
        self.add_node(node)
        self._sensor_by_key[key] = node
        return node

    def _retry_existing_sensor_addnode(self, node: HomeKitSensor, addr: str) -> None:
        """Re-publish cached PG3 nodes so IoX can recover if it missed the first addnode."""
        if addr in self._hk_existing_sensor_addnode_retried:
            return
        self._hk_existing_sensor_addnode_retried.add(addr)
        try:
            self.add_node(node)
            LOGGER.warning('HomeKit sensor %s already existed in PG3; re-sent addnode to IoX', addr)
        except Exception:
            LOGGER.debug('HomeKit sensor %s addnode retry failed', addr, exc_info=True)

    @staticmethod
    def _builtin_motion_sensor_label(
        thermostat: HomeKitThermostat,
        accessory_name_hint: Optional[str] = None,
    ) -> str:
        base = (accessory_name_hint or '').strip() or str(getattr(thermostat, 'name', '') or '').strip()
        if not base:
            base = 'Thermostat'
        if '· motion' in base:
            return base
        return f'{base} · motion'

    def _ensure_builtin_motion_sensor(
        self,
        device_id: str,
        thermostat: HomeKitThermostat,
        *,
        accessory_name_hint: Optional[str],
    ) -> Optional[HomeKitSensor]:
        """Sensor child for motion/occupancy on the same ``aid`` as the thermostat (Ecobee base)."""
        did = device_id.strip().lower()
        existing = self._motion_sensor_by_device.get(did)
        if existing is not None:
            return existing
        prim = self._thermostat_primary_aid.get(did, 1)
        label = self._builtin_motion_sensor_label(thermostat, accessory_name_hint)
        code_ov = self._hk_sensor_code_override(did, int(prim), label)
        addr = remote_sensor_address(did, int(prim), label, code_override=code_ov)
        node_existing = self.poly.getNode(addr)
        if node_existing is not None and isinstance(node_existing, HomeKitSensor):
            self._motion_sensor_by_device[did] = node_existing
            self._retry_existing_sensor_addnode(node_existing, addr)
            return node_existing
        if node_existing is not None:
            LOGGER.warning(
                'HomeKit built-in motion address %s is already used by a non-sensor node; skipping',
                addr,
            )
            return None
        nd = self._sensor_nodedef_homekit(thermostat.use_celsius)
        nm = get_valid_node_name(label)
        node = HomeKitSensor(
            self.dispatcher,
            thermostat.address,
            addr,
            nm,
            nd,
            thermostat.use_celsius,
            did,
            int(prim),
            hk=self,
        )
        self.add_node(node)
        self._motion_sensor_by_device[did] = node
        return node

    def _cancel_all_thermostat_snapshot_timers(self) -> None:
        with self._thermostat_snapshot_timer_lock:
            for tm in self._thermostat_snapshot_timers.values():
                try:
                    tm.cancel()
                except Exception:
                    LOGGER.debug('cancel thermostat snapshot timer failed', exc_info=True)
            self._thermostat_snapshot_timers.clear()

    def _characteristic_warrants_thermostat_snapshot_refresh(self, characteristic: str) -> bool:
        """GV3 often does not stream; after setpoint/mode events, re-read ``VENDOR_ECOBEE_CURRENT_MODE`` via hub ``get``."""
        ch = str(characteristic or '').strip()
        if not ch:
            return False
        u = ch.upper()
        if 'TEMPERATURE_HEATING_THRESHOLD' in u or 'HEAT_TARGET' in u:
            return True
        if 'TEMPERATURE_COOLING_THRESHOLD' in u or 'COOL_TARGET' in u:
            return True
        if 'HEATING_COOLING_TARGET' in u or 'TARGET_HEATING_COOLING' in u:
            return True
        nu = normalize_hap_uuid(ch)
        return bool(nu and nu in _THERM_SNAPSHOT_REFRESH_UUID_NORM)

    def _schedule_thermostat_snapshot_refresh(self, node: HomeKitThermostat, delay: float = 1.2) -> None:
        did = str(getattr(node, 'device_id_hub', None) or '').strip().lower()
        if not did:
            return

        def _fire() -> None:
            with self._thermostat_snapshot_timer_lock:
                self._thermostat_snapshot_timers.pop(did, None)
            try:
                self.refresh_thermostat_gv3(node)
            except Exception:
                LOGGER.debug('debounced thermostat GV3 refresh failed', exc_info=True)

        with self._thermostat_snapshot_timer_lock:
            old = self._thermostat_snapshot_timers.get(did)
            if old is not None:
                try:
                    old.cancel()
                except Exception:
                    pass
            timer = threading.Timer(delay, _fire)
            timer.daemon = True
            self._thermostat_snapshot_timers[did] = timer
            timer.start()

    def _on_hap_event(self, data: Dict[str, Any]) -> None:
        did = str(data.get('device_id') or '').strip().lower()
        char = data.get('characteristic')
        val = data.get('value')
        try:
            aid = int(data.get('aid'))
        except (TypeError, ValueError):
            return
        if not did or not char:
            return
        self._route_hap_value(did, aid, str(char), val)

    def _route_hap_value(self, device_id: str, aid: int, characteristic: str, value: Any) -> None:
        did = device_id.strip().lower()
        prim = self._thermostat_primary_aid.get(did, 1)
        t = self._thermostat_by_device.get(did)
        node: Any = None
        motion_on_primary = is_builtin_room_sensor_signal(characteristic) and aid == prim

        if motion_on_primary and t is not None:
            node = self._motion_sensor_by_device.get(did)
            if node is None:
                node = self._ensure_builtin_motion_sensor(
                    did,
                    t,
                    accessory_name_hint=getattr(t, 'name', None),
                )
        elif t is not None and is_ecobee_current_mode_characteristic(characteristic):
            node = t
        if node is None:
            node = self._sensor_by_key.get((did, aid))
        if node is None and t is not None and aid == prim and not motion_on_primary:
            node = t
        if node is None and t is not None and aid != prim:
            node = self._ensure_remote_sensor(
                did,
                aid,
                t.address,
                t.use_celsius,
                accessory_name=None,
                register_only=False,
            )
        if node is None:
            return
        applied = node.apply_hub_characteristic(characteristic, value)
        if (
            applied
            and t is not None
            and node is t
            and aid == prim
        ):
            ms2 = self._motion_sensor_by_device.get(did)
            if ms2 is not None and builtin_motion_sensor_ambient_mirror(characteristic):
                ms2.apply_hub_characteristic(characteristic, value)
            if self._characteristic_warrants_thermostat_snapshot_refresh(characteristic):
                self._schedule_thermostat_snapshot_refresh(t)
        if applied:
            return
        if classify(characteristic, 0) == CharBucket.UNKNOWN:
            self._bump_unknown_char(characteristic)

    def _bump_unknown_char(self, characteristic: str) -> None:
        key = str(characteristic or '').strip()
        if not key or key in self._unknown_char_logged:
            return
        self._unknown_char_logged.add(key)
        LOGGER.warning('HomeKit unmapped characteristic: %s', key)
        line = f'Unmapped HAP characteristic: <code>{key}</code>'
        self._unknown_char_notice_lines.append(line)
        self._set_notice_html(
            'homekit_unknown_chars',
            'Some hub characteristics are not mapped to IoX drivers yet:<br/>'
            + '<br/>'.join(self._unknown_char_notice_lines),
        )

    def hub_command(self, device_id: str, characteristic: str, value: Any) -> bool:
        did = str(device_id or '').strip().lower()
        value = _normalize_hap_command_value(characteristic, value)
        if self._dry_run():
            LOGGER.info(
                'HomeKit dry_run: would command device_id=%s %s=%r',
                did,
                characteristic,
                value,
            )
            return False
        ws = self._ws
        if ws is None:
            LOGGER.error('HomeKit hub_command: no WebSocket client')
            return False

        def _once() -> bool:
            return ws.command_sync(did, characteristic, value)

        try:
            return _once()
        except TimeoutError:
            self._notice_homekit_hub_rpc_command_error(
                device_id=did,
                characteristic=str(characteristic or ''),
                value=value,
                message=(
                    'Timed out waiting for hub RPC ack — check HomeKit hub logs (MQTT/WebSocket); '
                    'often a bad characteristic token or the hub not replying.'
                ),
            )
            LOGGER.error(
                'HomeKit hub_command: timed out waiting for hub RPC ack; check hub logs (MQTT/WS) for '
                'errors — often a bad characteristic token or hub not replying. device_id=%s %s=%r',
                did,
                characteristic,
                value,
            )
            return False
        except RuntimeError as e:
            if 'connection closed' not in str(e).lower():
                self._notice_homekit_hub_rpc_command_error(
                    device_id=did,
                    characteristic=str(characteristic or ''),
                    value=value,
                    message=str(e),
                )
                return False
            LOGGER.warning(
                'HomeKit hub_command: connection closed, retrying once after reconnect device_id=%s %s=%r',
                did,
                characteristic,
                value,
            )
            time.sleep(0.5)
            try:
                return _once()
            except Exception:
                LOGGER.exception(
                    'HomeKit hub_command failed (after retry) device_id=%s %s=%r',
                    did,
                    characteristic,
                    value,
                )
                return False
        except Exception:
            LOGGER.exception('HomeKit hub_command failed device_id=%s %s=%r', did, characteristic, value)
            return False

    def _apply_snapshot_values(self, node: Any, values: List[Dict[str, Any]]) -> None:
        aid = int(getattr(node, 'aid', 0) or 0)
        did_n = str(getattr(node, 'device_id_hub', '') or '').strip().lower()
        prim = self._thermostat_primary_aid.get(did_n, 1)
        motion_child = self._motion_sensor_by_device.get(did_n) if did_n else None
        for row in values:
            try:
                r_aid = int(row.get('aid'))
            except (TypeError, ValueError):
                continue
            ch = row.get('characteristic')
            chs = str(ch) if ch else ''
            if isinstance(node, HomeKitSensor):
                if r_aid != aid:
                    continue
                if motion_child is node and not builtin_motion_sensor_mirror_characteristic(chs):
                    continue
            if isinstance(node, HomeKitThermostat) and r_aid != prim:
                # ``VENDOR_ECOBEE_CURRENT_MODE`` (GV3) can live on a different ``aid`` than heating/cooling.
                if not is_ecobee_current_mode_characteristic(chs):
                    continue
            if isinstance(node, HomeKitThermostat) and is_builtin_room_sensor_signal(chs):
                continue
            if not ch or 'value' not in row:
                continue
            if not node.apply_hub_characteristic(str(ch), row.get('value')):
                if classify(str(ch), 0) == CharBucket.UNKNOWN:
                    self._bump_unknown_char(str(ch))

    def refresh_thermostat(self, node: HomeKitThermostat) -> None:
        ws = self._ws
        if ws is None:
            return
        did = str(node.device_id_hub or '').strip().lower()
        if not did:
            return
        try:
            values = self._snapshot_values_with_retry(did)
        except Exception:
            LOGGER.warning('refresh_thermostat snapshot failed for %s', did, exc_info=True)
            return
        self._apply_snapshot_values(node, values)

    def refresh_thermostat_gv3(self, node: HomeKitThermostat) -> None:
        """Re-read only Ecobee current comfort index (``GV3``) using hub ``get`` — no full snapshot."""
        if self._ws is None:
            return
        did = str(node.device_id_hub or '').strip().lower()
        if not did:
            return
        try:
            values = self._get_values_with_retry(did, [hap_name_vendor_ecobee_current_mode()])
        except Exception:
            LOGGER.debug('refresh_thermostat_gv3 get failed for %s', did, exc_info=True)
            return
        if not values:
            return
        self._apply_snapshot_values(node, values)

    def refresh_sensor(self, node: HomeKitSensor) -> None:
        ws = self._ws
        if ws is None:
            return
        did = str(node.device_id_hub or '').strip().lower()
        if not did:
            return
        try:
            values = self._snapshot_values_with_retry(did)
        except Exception:
            LOGGER.warning('refresh_sensor snapshot failed for %s', did, exc_info=True)
            return
        self._apply_snapshot_values(node, values)

    def handler_poll(self, polltype):
        if polltype == 'longPoll':
            self.long_poll()
        elif polltype == 'shortPoll':
            self.short_poll()

    def short_poll(self):
        if not self.ready:
            return

    def long_poll(self):
        if not self.ready:
            return
        self.heartbeat()

    def heartbeat(self):
        if self.hb == 0:
            self.dispatcher.reportCmd('DON', 2)
            self.hb = 1
        else:
            self.dispatcher.reportCmd('DOF', 2)
            self.hb = 0

    def handler_stop(self):
        LOGGER.debug('HomeKit backend stop')
        self.close()
        self._thermostat_by_device.clear()
        self._thermostat_primary_aid.clear()
        self._sensor_by_key.clear()
        self._motion_sensor_by_device.clear()
        self.dispatcher.setDriver('GV1', 0)
        try:
            self.dispatcher.setDriver('GV4', _HK_PATH_UNUSED, uom=25, report=True, force=True)
            self.dispatcher.setDriver('GV5', _HK_PATH_UNUSED, uom=25, report=True, force=True)
        except Exception:
            LOGGER.exception('setDriver GV4/GV5 on HomeKit backend stop')
        self.poly.stop()

    def cmd_poll(self, *args, **kwargs):
        self.query()

    def cmd_query(self, *args, **kwargs):
        self.query()

    def query(self):
        self.dispatcher.reportDrivers()
        for node in self.poly.nodes():
            if getattr(node, 'address', None) != self.address:
                node.reportDrivers()

    def discover(self, *args, **kwargs):
        self._list_devices_force_snapshot_resync = True
        devs = self._ws.devices if self._ws else []
        if devs:
            self._on_list_devices(devs)
            return True
        LOGGER.warning('HomeKit DISCOVER: no device list yet (hub not connected?)')
        return True
