"""Extensions for :mod:`climate_typed` (learned setpoints, typed schema)."""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from climate_typed import (
    TYPED_CLIMATE_PROGRAMS,
    _DEFAULT_SEED_REFS,
    _api_climate_map,
    _climate_name_is_default,
    _climate_ref_from_row,
    _thermostat_row_key,
    _typed_climate_program_rows,
    climateMap,
    climate_typed_params_section,
    default_climate_label,
    find_thermostat_typed_row,
    seed_climate_rows,
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


def _merge_climate_list_preserve_setpoints(
    existing: Optional[List[Dict[str, str]]],
    *,
    api_climates: Optional[Iterable[Mapping[str, object]]] = None,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> Tuple[List[Dict[str, str]], bool]:
    """Like :func:`climate_typed._merge_climate_list`, but keeps ``heat`` / ``cool`` fields."""
    api = _api_climate_map(api_climates)
    by_ref: Dict[str, Dict[str, str]] = {}
    changed = False
    for row in existing or ():
        ref = _climate_ref_from_row(row)
        if not ref:
            continue
        entry: Dict[str, str] = {
            'climateRef': ref,
            'name': str(row.get('name', '') or '').strip() or default_climate_label(ref),
        }
        for band in ('heat', 'cool'):
            raw = row.get(band)
            if raw is not None and str(raw).strip() != '':
                entry[band] = str(raw).strip()
        by_ref[ref] = entry

    seed_refs = list(api.keys()) if api else [r for r in _DEFAULT_SEED_REFS if r in climateMap]
    for ref in seed_refs:
        api_name = api.get(ref, '')
        if ref not in by_ref:
            by_ref[ref] = {'climateRef': ref, 'name': api_name or default_climate_label(ref)}
            changed = True
            continue
        cur = by_ref[ref]['name']
        if api_name and _climate_name_is_default(ref, cur) and cur != api_name:
            by_ref[ref]['name'] = api_name
            changed = True

    ordered: List[Dict[str, str]] = []
    seen: set[str] = set()
    for ref in climate_catalog:
        if ref in by_ref:
            ordered.append(by_ref[ref])
            seen.add(ref)
    for ref, row in by_ref.items():
        if ref not in seen:
            ordered.append(row)
    return ordered, changed


def ensure_climate_typed_data_preserve_setpoints(
    existing_rows: Optional[Iterable[Mapping[str, object]]],
    thermostats: Iterable[Mapping[str, object]],
    *,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Like :func:`climate_typed.ensure_climate_typed_data`, but keeps hub-learned setpoints."""
    rows = _typed_climate_program_rows(existing_rows)
    by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        key = _thermostat_row_key(row)
        if not key:
            continue
        by_key[key] = dict(row)
        if key not in order:
            order.append(key)

    changed = False

    for spec in thermostats:
        tid = str(spec.get('thermostat_id', '') or '').strip()
        if not tid:
            continue
        display = str(spec.get('name', '') or '').strip()
        did = str(spec.get('device_id', '') or '').strip().lower()
        api_climates = spec.get('api_climates')

        row = find_thermostat_typed_row(list(by_key.values()), thermostat_id=tid, device_id=did or None)
        key = f'id:{tid}'
        if row is None:
            row = {
                'thermostat_id': tid,
                'name': display,
                'device_id': did,
                'climates': seed_climate_rows(api_climates=api_climates, climate_catalog=climate_catalog),
            }
            by_key[key] = row
            if key not in order:
                order.append(key)
            changed = True
        else:
            key = _thermostat_row_key(row) or key
            row = dict(by_key[key])
            if display and not str(row.get('name', '') or '').strip():
                row['name'] = display
                changed = True
            if did and not str(row.get('device_id', '') or '').strip():
                row['device_id'] = did
                changed = True
            if not str(row.get('thermostat_id', '') or '').strip():
                row['thermostat_id'] = tid
                changed = True

        climates, c_changed = _merge_climate_list_preserve_setpoints(
            row.get('climates') if isinstance(row.get('climates'), list) else [],
            api_climates=api_climates,
            climate_catalog=climate_catalog,
        )
        if c_changed:
            row['climates'] = climates
            changed = True
        elif row.get('climates') != climates:
            row['climates'] = climates
        by_key[key] = row
        if key not in order:
            order.append(key)

    out = [by_key[k] for k in order if k in by_key]
    return out, changed


def sync_climate_typed_store(
    typed_data: Any,
    thermostats: Iterable[Mapping[str, object]],
    *,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> List[Dict[str, Any]]:
    """
    Ensure nested climate typed rows exist and persist when changed.

    Preserves hub-learned ``heat`` / ``cool`` during merge so repeated hub syncs do not
    spuriously rewrite typed data (which would echo back through ``handler_typed_data``).
    """
    td = typed_data_dict(typed_data)
    existing = td.get(TYPED_CLIMATE_PROGRAMS)
    rows, changed = ensure_climate_typed_data_preserve_setpoints(
        existing if isinstance(existing, list) else None,
        thermostats,
        climate_catalog=climate_catalog,
    )
    if changed:
        td[TYPED_CLIMATE_PROGRAMS] = rows
        typed_data.load(td, save=True)
    return rows
