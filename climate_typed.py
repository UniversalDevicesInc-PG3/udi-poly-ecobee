"""Custom Typed climate program labels: per-thermostat nested rows and profile helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from node_funcs import climateList as DEFAULT_CLIMATE_CATALOG, climateMap

TYPED_CLIMATE_PROGRAMS = 'climate_programs'

# Comfort refs usually present on Ecobee stats (used when API rows are unavailable).
_DEFAULT_SEED_REFS = (
    'away',
    'home',
    'sleep',
    'smart1',
    'smart2',
    'smart3',
    'smart4',
    'smart5',
    'smart6',
    'smart7',
)


def climate_typed_params_section() -> Dict[str, Any]:
    """Schema fragment for :meth:`Controller.TypedParams.load`."""
    return {
        'name': TYPED_CLIMATE_PROGRAMS,
        'title': 'Climate program labels',
        'desc': (
            'Friendly comfort names per thermostat. Each thermostat has a list of climateRef rows. '
            'Cloud fills names from the Ecobee API on DISCOVER; edit display names here.'
        ),
        'isList': True,
        'params': [
            {'name': 'thermostat_id', 'title': 'Thermostat id (IoX t<id> suffix)', 'isRequired': False},
            {'name': 'name', 'title': 'Thermostat display name', 'isRequired': False},
            {'name': 'device_id', 'title': 'HomeKit device_id (optional)', 'isRequired': False},
            {
                'name': 'climates',
                'title': 'Comfort programs',
                'isRequired': False,
                'isList': True,
                'params': [
                    {'name': 'climateRef', 'title': 'climateRef (e.g. home, smart2)', 'isRequired': False},
                    {'name': 'name', 'title': 'Display name', 'isRequired': False},
                ],
            },
        ],
    }


def default_climate_label(ref: str) -> str:
    r = str(ref or '').strip()
    if not r:
        return ''
    return r[0].upper() + r[1:] if len(r) > 1 else r.upper()


def _climate_ref_from_row(row: Mapping[str, object]) -> str:
    return str(row.get('climateRef', '') or row.get('ref', '') or '').strip()


def _api_climate_map(api_climates: Optional[Iterable[Mapping[str, object]]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in api_climates or ():
        ref = _climate_ref_from_row(row)
        if not ref:
            continue
        name = str(row.get('name', '') or '').strip()
        if name:
            out[ref] = name
    return out


def seed_climate_rows(
    *,
    api_climates: Optional[Iterable[Mapping[str, object]]] = None,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> List[Dict[str, str]]:
    """Default nested ``climates`` list for a new thermostat row."""
    api = _api_climate_map(api_climates)
    if api:
        refs = list(api.keys())
    else:
        refs = [r for r in _DEFAULT_SEED_REFS if r in climateMap]
    out: List[Dict[str, str]] = []
    for ref in refs:
        out.append({'climateRef': ref, 'name': api.get(ref, default_climate_label(ref))})
    return out


def _typed_climate_program_rows(
    rows: Optional[Iterable[Mapping[str, object]]],
) -> List[Dict[str, Any]]:
    """Return a list of thermostat dict rows from persisted typed data."""
    if not rows:
        return []
    return [dict(r) for r in rows if isinstance(r, dict)]


def _thermostat_row_key(row: Mapping[str, object]) -> str:
    tid = str(row.get('thermostat_id', '') or '').strip()
    if tid:
        return f'id:{tid}'
    did = str(row.get('device_id', '') or '').strip().lower()
    if did:
        return f'device:{did}'
    return ''


def find_thermostat_typed_row(
    rows: Sequence[Mapping[str, object]],
    *,
    thermostat_id: str,
    device_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    tid = str(thermostat_id or '').strip()
    did = str(device_id or '').strip().lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        rt = str(row.get('thermostat_id', '') or '').strip()
        rd = str(row.get('device_id', '') or '').strip().lower()
        if tid and rt == tid:
            return dict(row)
        if did and rd == did:
            return dict(row)
    return None


def _climate_name_is_default(ref: str, name: str) -> bool:
    n = str(name or '').strip()
    if not n:
        return True
    return n == default_climate_label(ref)


def _merge_climate_list(
    existing: Optional[List[Dict[str, str]]],
    *,
    api_climates: Optional[Iterable[Mapping[str, object]]] = None,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> Tuple[List[Dict[str, str]], bool]:
    api = _api_climate_map(api_climates)
    by_ref: Dict[str, Dict[str, str]] = {}
    changed = False
    for row in existing or ():
        ref = _climate_ref_from_row(row)
        if not ref:
            continue
        by_ref[ref] = {
            'climateRef': ref,
            'name': str(row.get('name', '') or '').strip() or default_climate_label(ref),
        }

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

    # Stable order: catalog order first, then any extra API refs.
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


def ensure_climate_typed_data(
    existing_rows: Optional[Iterable[Mapping[str, object]]],
    thermostats: Iterable[Mapping[str, object]],
    *,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Ensure one typed row per thermostat with nested ``climates`` entries.

    *thermostats* items: ``thermostat_id``, ``name`` (display), optional ``device_id``,
    optional ``api_climates`` (``[{'ref','name'}, ...]``).
    """
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

        climates, c_changed = _merge_climate_list(
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


def profile_climates_for_thermostat(
    typed_rows: Optional[Iterable[Mapping[str, object]]],
    thermostat_id: str,
    *,
    device_id: Optional[str] = None,
    api_climates: Optional[Iterable[Mapping[str, object]]] = None,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> List[Dict[str, str]]:
    """
  Build profile writer input for one thermostat: full ``climate_catalog`` with per-ref names.

    Priority: typed nested name → API name → default label.
    """
    rows = _typed_climate_program_rows(typed_rows)
    row = find_thermostat_typed_row(rows, thermostat_id=thermostat_id, device_id=device_id)
    typed_by_ref: Dict[str, str] = {}
    if row and isinstance(row.get('climates'), list):
        for c in row['climates']:
            if not isinstance(c, dict):
                continue
            ref = _climate_ref_from_row(c)
            if not ref:
                continue
            name = str(c.get('name', '') or '').strip()
            if name:
                typed_by_ref[ref] = name
    api_by_ref = _api_climate_map(api_climates)

    out: List[Dict[str, str]] = []
    for ref in climate_catalog:
        name = typed_by_ref.get(ref) or api_by_ref.get(ref) or default_climate_label(ref)
        out.append({'ref': ref, 'name': name})
    return out


def command_climates_for_thermostat(
    typed_rows: Optional[Iterable[Mapping[str, object]]],
    thermostat_id: str,
    *,
    device_id: Optional[str] = None,
    api_climates: Optional[Iterable[Mapping[str, object]]] = None,
) -> List[Dict[str, str]]:
    """Subset of configured comforts for GV3 command editors (not the full catalog)."""
    rows = _typed_climate_program_rows(typed_rows)
    row = find_thermostat_typed_row(rows, thermostat_id=thermostat_id, device_id=device_id)
    if row and isinstance(row.get('climates'), list) and row['climates']:
        out: List[Dict[str, str]] = []
        for c in row['climates']:
            if not isinstance(c, dict):
                continue
            ref = _climate_ref_from_row(c)
            if not ref:
                continue
            name = str(c.get('name', '') or '').strip() or default_climate_label(ref)
            out.append({'ref': ref, 'name': name})
        if out:
            return out
    api = _api_climate_map(api_climates)
    if api:
        return [{'ref': ref, 'name': api[ref]} for ref in api]
    return [{'ref': ref, 'name': default_climate_label(ref)} for ref in _DEFAULT_SEED_REFS if ref in climateMap]


def typed_data_dict(typed_data: Any) -> Dict[str, Any]:
    """Snapshot :class:`udi_interface.Custom` typed data as a plain dict."""
    out: Dict[str, Any] = {}
    if typed_data is None:
        return out
    try:
        for k in typed_data.keys():
            out[k] = typed_data[k]
    except Exception:
        pass
    return out


def sync_climate_typed_store(
    typed_data: Any,
    thermostats: Iterable[Mapping[str, object]],
    *,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
) -> List[Dict[str, Any]]:
    """
    Ensure nested climate typed rows exist and persist when changed.

    Returns the normalized ``climate_programs`` list (also written to typed data when updated).
    """
    td = typed_data_dict(typed_data)
    existing = td.get(TYPED_CLIMATE_PROGRAMS)
    rows, changed = ensure_climate_typed_data(
        existing if isinstance(existing, list) else None,
        thermostats,
        climate_catalog=climate_catalog,
    )
    if changed:
        td[TYPED_CLIMATE_PROGRAMS] = rows
        typed_data.load(td, save=True)
    return rows
