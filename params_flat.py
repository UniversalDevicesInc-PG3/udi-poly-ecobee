"""Normalize and validate flat Custom Params (cloud / HomeKit). PG3-free for unit tests."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit

DEFAULT_EFFECTIVE: Dict[str, str] = {
    # Fallback when normalizing empty input; seeding ``backend`` uses :func:`default_backend_for_new_param_seed`.
    'backend': 'homekit',
    'hk_ws_url': 'ws://127.0.0.1:8163',
    'hk_ws_token': '',
    'use_celsius': 'auto',
    'dry_run': 'true',
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


def normalize_flat_params(
    raw: Mapping[str, Any],
    prev: Optional[Mapping[str, str]] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Validate flat params and return ``(effective, errors)``.

    ``effective`` always contains keys: backend, hk_ws_url, hk_ws_token, use_celsius, dry_run.
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

    url = str(raw.get('hk_ws_url', '') or '').strip()
    if not url:
        url = prev_m.get('hk_ws_url', DEFAULT_EFFECTIVE['hk_ws_url'])
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

    dr = str(raw.get('dry_run', prev_m.get('dry_run', 'true'))).strip().lower()
    if dr not in ('true', 'false'):
        errs.append(f"dry_run: {raw.get('dry_run')!r} (allowed: true, false)")
        dr = prev_m.get('dry_run', 'true')

    out: Dict[str, str] = {
        'backend': backend,
        'hk_ws_url': url,
        'hk_ws_token': token,
        'use_celsius': uc,
        'dry_run': dr,
    }
    return out, errs


def format_param_notice_html(errors: List[str]) -> str:
    if not errors:
        return ''
    return (
        'Invalid Custom Param value(s) — using prior/default until corrected:<br/>'
        + '<br/>'.join(errors)
    )
