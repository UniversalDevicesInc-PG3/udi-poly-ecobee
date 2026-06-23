"""Normalize and validate flat Custom Params (cloud / HomeKit). PG3-free for unit tests."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit

_DEFAULT_MQTT_SLUG_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)


def _is_valid_mqtt_slug(s: str) -> bool:
    t = str(s or "").strip()
    return bool(t) and len(t) <= 128 and all(c in _DEFAULT_MQTT_SLUG_CHARS for c in t)


# Default MQTT ``client_slug`` (hub topic ``…/clients/<slug>/…``): PG3 plugin id for this Node Server.
# Set ``hk_mqtt_client_slug`` explicitly if multiple instances or other plugins need distinct slugs on one broker.
DEFAULT_HK_MQTT_CLIENT_SLUG = "udi-poly-ecobee"

# HomeKit auto-mode minimum heat/cool separation (degrees in the stat's display units).
DEFAULT_HK_HEAT_COOL_MIN_DELTA = '3'


DEFAULT_EFFECTIVE: Dict[str, str] = {
    # Fallback when normalizing empty input; seeding ``backend`` uses :func:`default_backend_for_new_param_seed`.
    'backend': 'homekit',
    # MQTT is the preferred HomeKit hub transport (lower latency, broker survives plugin restarts);
    # WebSocket remains supported when ``mqtt_enable`` is off on the hub.
    'hk_transport': 'mqtt',
    'hk_ws_url': 'ws://127.0.0.1:8163',
    'hk_ws_token': '',
    'hk_mqtt_host': 'localhost',
    'hk_mqtt_port': '1884',
    'hk_mqtt_username': '',
    'hk_mqtt_password': '',
    'hk_mqtt_hub_slug': 'default',
    'hk_mqtt_client_slug': DEFAULT_HK_MQTT_CLIENT_SLUG,
    'use_celsius': 'auto',
    'dry_run': 'false',
    'hk_heat_cool_min_delta': DEFAULT_HK_HEAT_COOL_MIN_DELTA,
}


def default_backend_for_new_param_seed(
    *,
    customdata: Mapping[str, Any],
    api_key_param: str,
    poly_oauth_init: bool,
    has_other_pg3_nodes: bool = False,
) -> str:
    """
    Value to store when PG3 has no ``backend`` Custom Param yet.

    Existing cloud/OAuth/PIN users get ``cloud``; fresh installs get ``homekit``.
    Callers pass a JSON-safe customdata snapshot (no ``poly``), current ``api_key`` text, and
    whether Polyglot ``init`` advertises OAuth for this NS.

    ``has_other_pg3_nodes`` is True when this NS already has IoX nodes besides the controller
    (handles upgrades where Custom Params arrive before customdata is hydrated).
    """
    if poly_oauth_init:
        return 'cloud'
    ak = str(api_key_param or '').strip()
    if ak:
        return 'cloud'
    if not isinstance(customdata, Mapping):
        customdata = {}
    td = customdata.get('tokenData')
    if isinstance(td, Mapping) and td:
        return 'cloud'
    td_old = customdata.get('tokenData_old')
    if isinstance(td_old, Mapping) and td_old:
        return 'cloud'
    if customdata.get('pin_code'):
        return 'cloud'
    if has_other_pg3_nodes:
        return 'cloud'
    return 'homekit'


def _parse_hk_heat_cool_min_delta(raw: Any, fallback: str) -> Tuple[float, bool]:
    """Return (degrees, had_error)."""
    try:
        val = float(str(raw).strip())
    except (TypeError, ValueError):
        return float(fallback), True
    if val < 1.0 or val > 10.0:
        return float(fallback), True
    return val, False


def heat_cool_min_span_degrees(use_celsius: bool, effective: Optional[Mapping[str, str]] = None) -> float:
    """
    Minimum heat/cool separation for HomeKit threshold co-writes.

    ``hk_heat_cool_min_delta`` is in the thermostat's display units (°F or °C), matching the
    Ecobee app **Compressor minimum delta** setting.
    """
    eff = effective or {}
    fallback = eff.get('hk_heat_cool_min_delta', DEFAULT_HK_HEAT_COOL_MIN_DELTA)
    if fallback is None or str(fallback).strip() == '':
        fallback = DEFAULT_HK_HEAT_COOL_MIN_DELTA
    val, _ = _parse_hk_heat_cool_min_delta(
        eff.get('hk_heat_cool_min_delta', fallback),
        str(fallback),
    )
    return val


def normalize_flat_params(
    raw: Mapping[str, Any],
    prev: Optional[Mapping[str, str]] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Validate flat params and return ``(effective, errors)``.

    ``effective`` always contains keys: backend, hk_transport, hk_ws_url, hk_ws_token,
    hk_mqtt_* fields, use_celsius, dry_run, hk_heat_cool_min_delta.
    ``errors`` entries are plain-text lines (caller may wrap in HTML for notices).
    """
    prev_m: Dict[str, str] = dict(DEFAULT_EFFECTIVE)
    if prev:
        prev_m.update(prev)
    errs: List[str] = []

    raw_backend = raw.get('backend', prev_m.get('backend', DEFAULT_EFFECTIVE['backend']))
    backend = str(raw_backend).strip().lower()
    if backend not in ('cloud', 'homekit'):
        errs.append(f"backend: {raw_backend!r} (allowed: cloud, homekit)")
        backend = prev_m.get('backend', DEFAULT_EFFECTIVE['backend'])

    tr_default = DEFAULT_EFFECTIVE['hk_transport']
    tr_raw = str(raw.get('hk_transport', prev_m.get('hk_transport', tr_default))).strip().lower()
    if tr_raw == '':
        # Empty / missing on a fresh install falls through to the preferred default (MQTT).
        transport = tr_default
    elif tr_raw in ('ws', 'websocket'):
        transport = 'websocket'
    elif tr_raw == 'mqtt':
        transport = 'mqtt'
    else:
        errs.append(f"hk_transport: {raw.get('hk_transport')!r} (allowed: websocket, mqtt)")
        transport = str(prev_m.get('hk_transport', tr_default)).strip().lower()
        if transport not in ('websocket', 'mqtt'):
            transport = tr_default

    url = str(raw.get('hk_ws_url', '') or '').strip()
    if not url:
        url = prev_m.get('hk_ws_url', DEFAULT_EFFECTIVE['hk_ws_url'])
    elif transport == 'mqtt':
        # Preserve stored URL for switching back to WebSocket without retyping; do not validate when MQTT.
        pass
    else:
        parts = urlsplit(url)
        if parts.scheme not in ('ws', 'wss') or not parts.netloc:
            errs.append(f"hk_ws_url: {url!r} (must be ws:// or wss:// with a host)")
            url = prev_m.get('hk_ws_url', DEFAULT_EFFECTIVE['hk_ws_url'])

    token = raw.get('hk_ws_token', prev_m.get('hk_ws_token', ''))
    if token is None:
        token = ''
    token = str(token)

    uc = str(raw.get('use_celsius', prev_m.get('use_celsius', 'auto'))).strip().lower()
    if uc not in ('auto', 'true', 'false'):
        errs.append(f"use_celsius: {raw.get('use_celsius')!r} (allowed: auto, true, false)")
        uc = prev_m.get('use_celsius', 'auto')

    dr = str(raw.get('dry_run', prev_m.get('dry_run', DEFAULT_EFFECTIVE['dry_run']))).strip().lower()
    if dr not in ('true', 'false'):
        errs.append(f"dry_run: {raw.get('dry_run')!r} (allowed: true, false)")
        dr = prev_m.get('dry_run', DEFAULT_EFFECTIVE['dry_run'])

    delta_f, delta_err = _parse_hk_heat_cool_min_delta(
        raw.get('hk_heat_cool_min_delta', prev_m.get('hk_heat_cool_min_delta', DEFAULT_HK_HEAT_COOL_MIN_DELTA)),
        prev_m.get('hk_heat_cool_min_delta', DEFAULT_HK_HEAT_COOL_MIN_DELTA),
    )
    if delta_err:
        errs.append(
            f"hk_heat_cool_min_delta: {raw.get('hk_heat_cool_min_delta')!r} "
            f"(allowed: number 1-10, default {DEFAULT_HK_HEAT_COOL_MIN_DELTA})"
        )

    mhost = str(raw.get('hk_mqtt_host', '') or '').strip()
    if not mhost:
        mhost = (
            str(prev_m.get('hk_mqtt_host', DEFAULT_EFFECTIVE['hk_mqtt_host'])).strip()
            or DEFAULT_EFFECTIVE['hk_mqtt_host']
        )

    mport_raw = raw.get('hk_mqtt_port', prev_m.get('hk_mqtt_port', DEFAULT_EFFECTIVE['hk_mqtt_port']))
    try:
        mport_i = int(str(mport_raw).strip())
    except (TypeError, ValueError):
        errs.append(f"hk_mqtt_port: {mport_raw!r} (must be integer 1-65535)")
        mport_i = int(prev_m.get('hk_mqtt_port', DEFAULT_EFFECTIVE['hk_mqtt_port']))
    if mport_i < 1 or mport_i > 65535:
        errs.append(f"hk_mqtt_port: {mport_i} (must be 1-65535)")
        mport_i = int(prev_m.get('hk_mqtt_port', DEFAULT_EFFECTIVE['hk_mqtt_port']))

    muser = raw.get('hk_mqtt_username', prev_m.get('hk_mqtt_username', ''))
    if muser is None:
        muser = ''
    muser = str(muser)
    mpass = raw.get('hk_mqtt_password', prev_m.get('hk_mqtt_password', ''))
    if mpass is None:
        mpass = ''
    mpass = str(mpass)

    hub_slug = str(raw.get('hk_mqtt_hub_slug', '') or '').strip()
    if not hub_slug:
        hub_slug = str(prev_m.get('hk_mqtt_hub_slug', DEFAULT_EFFECTIVE['hk_mqtt_hub_slug'])).strip() or 'default'
    if not _is_valid_mqtt_slug(hub_slug):
        errs.append(f"hk_mqtt_hub_slug: {hub_slug!r} (allowed: [A-Za-z0-9_-] length 1..128)")
        hub_slug = str(prev_m.get('hk_mqtt_hub_slug', DEFAULT_EFFECTIVE['hk_mqtt_hub_slug'])).strip() or 'default'

    client_slug = str(raw.get('hk_mqtt_client_slug', '') or '').strip()
    if not client_slug:
        client_slug = (
            str(prev_m.get('hk_mqtt_client_slug', DEFAULT_EFFECTIVE['hk_mqtt_client_slug'])).strip()
            or DEFAULT_HK_MQTT_CLIENT_SLUG
        )
    if not _is_valid_mqtt_slug(client_slug):
        errs.append(f"hk_mqtt_client_slug: {client_slug!r} (allowed: [A-Za-z0-9_-] length 1..128)")
        client_slug = (
            str(prev_m.get('hk_mqtt_client_slug', DEFAULT_EFFECTIVE['hk_mqtt_client_slug'])).strip()
            or DEFAULT_HK_MQTT_CLIENT_SLUG
        )

    out: Dict[str, str] = {
        'backend': backend,
        'hk_transport': transport,
        'hk_ws_url': url,
        'hk_ws_token': token,
        'hk_mqtt_host': mhost,
        'hk_mqtt_port': str(mport_i),
        'hk_mqtt_username': muser,
        'hk_mqtt_password': mpass,
        'hk_mqtt_hub_slug': hub_slug,
        'hk_mqtt_client_slug': client_slug,
        'use_celsius': uc,
        'dry_run': dr,
        'hk_heat_cool_min_delta': str(int(delta_f) if delta_f == int(delta_f) else delta_f),
    }
    return out, errs


def format_param_notice_html(errors: List[str]) -> str:
    if not errors:
        return ''
    return (
        'Invalid Custom Param value(s) — using prior/default until corrected:<br/>'
        + '<br/>'.join(errors)
    )
