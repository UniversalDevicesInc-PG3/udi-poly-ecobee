"""Extensions for :mod:`climate_typed` (learned setpoints, typed schema)."""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from climate_typed import (
    TYPED_CLIMATE_PROGRAMS,
    _climate_ref_from_row,
    _thermostat_row_key,
    climate_typed_params_section,
    find_thermostat_typed_row,
    sync_climate_typed_store as _sync_climate_typed_store,
    typed_data_dict,
)
from node_funcs import climateList as DEFAULT_CLIMATE_CATALOG


def climate_typed_params_section_with_learned_setpoints() -> Dict[str, Any]:
    """Typed schema with read-only-style ``heat`` / ``cool`` filled by HomeKit learn."""
    section = copy.deepcopy(climate_typed_params_section())
    for p in section.get('params', []):
        if p.get('name') != 'climates':
            continue
        p['params'].extend(
            [
                {
                    'name': 'heat',
                    'title': 'Heat setpoint (auto, HomeKit learn)',
                    'isRequired': False,
                },
                {
                    'name': 'cool',
                    'title': 'Cool setpoint (auto, HomeKit learn)',
                    'isRequired': False,
                },
            ]
        )
    section['desc'] = (
        'Friendly comfort names per thermostat. Cloud fills names from the Ecobee API on '
        'DISCOVER. On HomeKit, edit **Display name** to match your Ecobee app (e.g. rename '
        '``smart1`` to **Workshop**). **Heat** / **Cool** are updated automatically when the '
        'plugin learns setpoints from a hub snapshot.'
    )
    return section


def sync_learned_setpoint_in_typed_store(
    typed_data: Any,
    thermostat_id: str,
    climate_ref: str,
    heat: float,
    cool: float,
    *,
    device_id: Optional[str] = None,
) -> bool:
    """
    Write hub-learned heat/cool onto the matching nested comfort row in typed data.

    Returns True when typed data was changed and saved.
    """
    ref = str(climate_ref or '').strip()
    if not ref or typed_data is None:
        return False
    td = typed_data_dict(typed_data)
    rows = list(td.get(TYPED_CLIMATE_PROGRAMS) or [])
    row = find_thermostat_typed_row(
        rows,
        thermostat_id=str(thermostat_id),
        device_id=device_id,
    )
    if not row or not isinstance(row.get('climates'), list):
        return False
    heat_s = str(float(heat))
    cool_s = str(float(cool))
    changed = False
    climates: List[Dict[str, Any]] = []
    for c in row['climates']:
        if not isinstance(c, dict):
            climates.append(c)
            continue
        entry = dict(c)
        cref = str(entry.get('climateRef', '') or entry.get('ref', '') or '').strip()
        if cref == ref:
            if str(entry.get('heat', '')) != heat_s or str(entry.get('cool', '')) != cool_s:
                entry['heat'] = heat_s
                entry['cool'] = cool_s
                changed = True
        climates.append(entry)
    if not changed:
        return False
    row['climates'] = climates
    key = None
    tid = str(thermostat_id or '').strip()
    did = str(device_id or '').strip().lower()
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        if tid and str(r.get('thermostat_id', '') or '').strip() == tid:
            key = i
            break
        if did and str(r.get('device_id', '') or '').strip().lower() == did:
            key = i
            break
    if key is None:
        return False
    rows[key] = row
    td[TYPED_CLIMATE_PROGRAMS] = rows
    typed_data.load(td, save=True)
    return True


def _setpoints_by_thermostat_key(
    rows: Optional[Iterable[Mapping[str, object]]],
) -> Dict[str, Dict[str, Dict[str, str]]]:
    """Snapshot ``heat`` / ``cool`` nested fields before typed merge overwrites them."""
    out: Dict[str, Dict[str, Dict[str, str]]] = {}
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        key = _thermostat_row_key(row)
        if not key or not isinstance(row.get('climates'), list):
            continue
        by_ref: Dict[str, Dict[str, str]] = {}
        for c in row['climates']:
            if not isinstance(c, dict):
                continue
            ref = _climate_ref_from_row(c)
            if not ref:
                continue
            fields: Dict[str, str] = {}
            for band in ('heat', 'cool'):
                raw = c.get(band)
                if raw is not None and str(raw).strip() != '':
                    fields[band] = str(raw).strip()
            if fields:
                by_ref[ref] = fields
        if by_ref:
            out[key] = by_ref
    return out


def _restore_preserved_comfort_setpoints(
    rows: List[Dict[str, Any]],
    preserved: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> tuple[List[Dict[str, Any]], bool]:
    if not preserved:
        return rows, False
    changed = False
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(row)
            continue
        entry = dict(row)
        key = _thermostat_row_key(entry)
        keep = preserved.get(key) if key else None
        if not keep or not isinstance(entry.get('climates'), list):
            out.append(entry)
            continue
        climates: List[Dict[str, Any]] = []
        for c in entry['climates']:
            if not isinstance(c, dict):
                climates.append(c)
                continue
            cref = _climate_ref_from_row(c)
            merged = dict(c)
            sp = keep.get(cref) if cref else None
            if sp:
                for band in ('heat', 'cool'):
                    if band in sp and str(merged.get(band, '')) != sp[band]:
                        merged[band] = sp[band]
                        changed = True
            climates.append(merged)
        entry['climates'] = climates
        out.append(entry)
    return out, changed


def sync_climate_typed_store(
    typed_data: Any,
    thermostats: Iterable[Mapping[str, object]],
    *,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> List[Dict[str, Any]]:
    """
    Like :func:`climate_typed.sync_climate_typed_store`, but keeps hub-learned ``heat`` / ``cool``.
    """
    td = typed_data_dict(typed_data)
    existing = td.get(TYPED_CLIMATE_PROGRAMS)
    preserved = _setpoints_by_thermostat_key(existing if isinstance(existing, list) else None)
    rows = _sync_climate_typed_store(
        typed_data,
        thermostats,
        climate_catalog=climate_catalog,
    )
    rows, restored = _restore_preserved_comfort_setpoints(rows, preserved)
    if restored:
        td[TYPED_CLIMATE_PROGRAMS] = rows
        typed_data.load(td, save=True)
    return rows
