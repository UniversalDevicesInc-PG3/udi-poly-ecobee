"""Ecobee program comfort setpoints (cloud API → IoX driver temps for HomeKit commands)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

from node_funcs import climateMap, toC


def ecobee_api_temp_to_driver(temp: Any, *, use_celsius: bool) -> Optional[float]:
    """Convert Ecobee API tenths (F at wire) to driver heat/cool units."""
    try:
        t = float(temp)
    except (TypeError, ValueError):
        return None
    if t == 0:
        return 0.0
    t = t / 10.0
    if use_celsius:
        return float(toC(t))
    return float(int(t))


def climate_setpoints_from_program_climates(
    climates: Iterable[Mapping[str, Any]],
    *,
    use_celsius: bool,
) -> Dict[str, Tuple[float, float]]:
    """Map ``climateRef`` → (heat, cool) driver setpoints from Ecobee ``program.climates`` rows."""
    out: Dict[str, Tuple[float, float]] = {}
    for climate in climates or ():
        ref = str(climate.get('climateRef', '') or climate.get('ref', '') or '').strip()
        if not ref:
            continue
        heat = ecobee_api_temp_to_driver(climate.get('heatTemp'), use_celsius=use_celsius)
        cool = ecobee_api_temp_to_driver(climate.get('coolTemp'), use_celsius=use_celsius)
        if heat is None or cool is None:
            continue
        out[ref] = (float(heat), float(cool))
    return out


def climate_setpoints_for_storage(
    by_ref: Mapping[str, Tuple[float, float]],
) -> Dict[str, Dict[str, float]]:
    """Serialize ref → (heat, cool) for ``customData.climate_setpoints``."""
    return {ref: {'heat': heat, 'cool': cool} for ref, (heat, cool) in by_ref.items()}


def climate_setpoints_from_stored(
    data: Optional[Mapping[str, Any]],
    thermostat_id: str,
) -> Dict[str, Tuple[float, float]]:
    """Load stored program setpoints for one thermostat from customData."""
    if not data:
        return {}
    block = (data.get('climate_setpoints') or {}).get(str(thermostat_id))
    if not isinstance(block, dict):
        return {}
    out: Dict[str, Tuple[float, float]] = {}
    for ref, sp in block.items():
        if not isinstance(sp, dict):
            continue
        try:
            heat = float(sp['heat'])
            cool = float(sp['cool'])
        except (KeyError, TypeError, ValueError):
            continue
        out[str(ref)] = (heat, cool)
    return out


def _float_setpoint_field(row: Mapping[str, object], key: str) -> Optional[float]:
    raw = row.get(key)
    if raw is None or str(raw).strip() == '':
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def comfort_setpoints_from_typed_rows(
    typed_rows: Optional[Iterable[Mapping[str, object]]],
    thermostat_id: str,
    *,
    device_id: Optional[str] = None,
) -> Dict[str, Tuple[float, float]]:
    """
    Optional hub-learned ``heat`` / ``cool`` per comfort from **Climate program labels** typed data.

    HomeKit fills these fields automatically when the stat is on that comfort during QUERY or
    at Node Server start; they are not meant for manual entry.
    """
    from climate_typed import find_thermostat_typed_row

    row = find_thermostat_typed_row(
        list(typed_rows or ()),
        thermostat_id=str(thermostat_id),
        device_id=device_id,
    )
    if not row or not isinstance(row.get('climates'), list):
        return {}
    out: Dict[str, Tuple[float, float]] = {}
    for c in row['climates']:
        if not isinstance(c, dict):
            continue
        ref = str(c.get('climateRef', '') or c.get('ref', '') or '').strip()
        if not ref:
            continue
        heat = _float_setpoint_field(c, 'heat')
        cool = _float_setpoint_field(c, 'cool')
        if heat is None or cool is None:
            continue
        out[ref] = (float(heat), float(cool))
    return out


def merge_comfort_setpoint_maps(
    *maps: Mapping[str, Tuple[float, float]],
) -> Dict[str, Tuple[float, float]]:
    """Later maps override earlier entries for the same ``climateRef``."""
    out: Dict[str, Tuple[float, float]] = {}
    for m in maps:
        for ref, sp in (m or {}).items():
            r = str(ref or '').strip()
            if r:
                out[r] = (float(sp[0]), float(sp[1]))
    return out


def seed_gv3_to_sp_from_comfort_maps(
    gv3_to_sp: MutableMapping[int, Tuple[float, float]],
    *,
    program_sp: Mapping[str, Tuple[float, float]],
    vendor_sp: Mapping[str, Tuple[float, float]],
    climate_map: Mapping[str, int] = climateMap,
) -> None:
    """Fill missing IoX ``GV3`` index entries from program and vendor comfort ref maps."""
    for ref, sp in program_sp.items():
        if ref not in climate_map:
            continue
        gv = int(climate_map[ref])
        gv3_to_sp.setdefault(gv, sp)
    for ref, sp in vendor_sp.items():
        if ref not in climate_map:
            continue
        gv = int(climate_map[ref])
        gv3_to_sp.setdefault(gv, sp)
