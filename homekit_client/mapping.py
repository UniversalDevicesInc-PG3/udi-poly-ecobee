"""Resolve IoX addresses from HomeKit device metadata."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

_ECOBEE_NAME_PREFIX = 'Ecobee - '

# IoX / PG3 node addresses are typically limited to **14 characters** (ISY convention).
_RS_PREFIX = 'rs_'
_MAX_NODE_ADDRESS_LEN = 14
_MAX_RS_BODY_LEN = _MAX_NODE_ADDRESS_LEN - len(_RS_PREFIX)  # 11 → ``rs_`` + body ≤ 14 total


def _digits(s: str) -> str:
    return re.sub(r'\D', '', s or '')


def sanitize_address_part(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def _strip_ecobee_prefix(accessory_name: str) -> str:
    t = (accessory_name or '').strip()
    if t.lower().startswith(_ECOBEE_NAME_PREFIX.lower()):
        return t[len(_ECOBEE_NAME_PREFIX) :].strip()
    return t


def _existing_thermostat_addresses(existing_addresses: List[str]) -> List[str]:
    return [a for a in existing_addresses if a.startswith('t')]


def _digit_suffix_matches(plain: str, existing_t: List[str]) -> List[str]:
    out: List[str] = []
    for a in existing_t:
        suf = _digits(a[1:])
        if suf and plain.endswith(suf):
            out.append(a)
    return out


def _pick_by_name_runs(accessory_name: Optional[str], addresses: List[str]) -> Optional[str]:
    """
    If *accessory_name* contains a digit run that exactly equals the numeric suffix
    of exactly one address in *addresses*, return that address.
    """
    if not accessory_name or not addresses:
        return None
    target = _strip_ecobee_prefix(accessory_name)
    runs = set(re.findall(r'\d+', target))
    if not runs:
        return None
    hits = []
    for a in addresses:
        suf = _digits(a[1:])
        if suf and suf in runs:
            hits.append(a)
    if len(hits) == 1:
        return hits[0]
    return None


def resolve_thermostat_address(
    device_id: str,
    serial_number: Optional[str],
    accessory_name: Optional[str],
    existing_addresses: List[str],
    id_override: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Return (address, reason) where address is like ``t<digits>`` or sanitized serial.
    """
    if id_override:
        tid = _digits(id_override) or sanitize_address_part(id_override)
        return f't{tid}', 'hk_id_overrides'

    existing_t = _existing_thermostat_addresses(existing_addresses)
    sn = (serial_number or '').strip()
    if sn:
        plain = _digits(sn) or sanitize_address_part(sn)
        cand = f't{plain}'
        if cand in existing_addresses:
            return cand, 'exact_serial'
        digit_matches = _digit_suffix_matches(plain, existing_t)
        if len(digit_matches) == 1:
            return digit_matches[0], 'digit_suffix'
        if len(digit_matches) > 1 and accessory_name:
            picked = _pick_by_name_runs(accessory_name, digit_matches)
            if picked:
                return picked, 'name_digits'
        if accessory_name and existing_t:
            picked = _pick_by_name_runs(accessory_name, existing_t)
            if picked:
                return picked, 'name_digits'
        if cand not in existing_addresses and not digit_matches:
            return cand, 'mint_serial'
        if cand not in existing_addresses:
            return cand, 'mint_serial'

    fallback = sanitize_address_part(device_id.replace(':', '')) or 'unknown'
    return f't{fallback}', 'device_id_fallback'


def remote_sensor_address(
    device_id: str,
    aid: int,
    accessory_name: Optional[str],
    code_override: Optional[str] = None,
) -> str:
    """
    Return a remote-sensor IoX address like ``rs_<body>``.

    The ``rs_`` prefix uses 3 characters; the body is truncated so the **full** address
    never exceeds :data:`_MAX_NODE_ADDRESS_LEN` (PG3/ISY rejects longer addresses — e.g.
    ``rs_mastermotion`` is 15 chars and fails ``addnode``).
    """
    del device_id  # reserved for future per-hub disambiguation
    if code_override:
        c = sanitize_address_part(code_override)[:_MAX_RS_BODY_LEN] or 'unk'
        return f'{_RS_PREFIX}{c}'
    base = sanitize_address_part(accessory_name or f'a{aid}')[:_MAX_RS_BODY_LEN] or 's'
    return f'{_RS_PREFIX}{base}'
