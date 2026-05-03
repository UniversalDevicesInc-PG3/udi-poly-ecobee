"""Generate profile/nodedef/custom.xml, profile/editor/custom.xml, and profile NLS for climate programs."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set

from node_funcs import climateList as DEFAULT_CLIMATE_CATALOG, make_file_dir


def homekit_climate_details_for_device(
    hub_device_id: str,
    typed_program_rows: Optional[Iterable[Mapping[str, object]]],
    climate_catalog: Sequence[str],
    *,
    skip_catalog_indices: Optional[Set[int]] = None,
) -> List[Dict[str, str]]:
    """
    Build the same structure cloud uses for one thermostat: ordered ``{'ref','name'}`` entries.

    Typed rows match ``device_id`` (hub pairing id) and optional integer ``index`` into
    *climate_catalog*; ``name`` overrides the default ucfirst label for that slot.

    *skip_catalog_indices*: optional indices **not** overridden from typed rows (rare; backend-specific).
    """
    hub = str(hub_device_id or '').strip().lower()
    skip = skip_catalog_indices or set()
    overrides: Dict[int, str] = {}
    for row in typed_program_rows or ():
        if str(row.get('device_id', '')).strip().lower() != hub:
            continue
        try:
            idx = int(row.get('index', -1))
        except (TypeError, ValueError):
            continue
        if idx in skip:
            continue
        if idx < 0 or idx >= len(climate_catalog):
            continue
        name = str(row.get('name', '') or '').strip()
        if name:
            overrides[idx] = name
    out: List[Dict[str, str]] = []
    for i, ref in enumerate(climate_catalog):
        default = ref[0].upper() + ref[1:] if ref else str(i)
        out.append({'ref': ref, 'name': overrides.get(i, default)})
    return out


def profile_needs_update(
    data: Optional[MutableMapping[str, object]],
    disk_profile_version: str,
    new_climates: Mapping[str, List[Dict[str, str]]],
) -> bool:
    """
    Mirror cloud ``check_profile`` gating: version.txt change or any per-thermostat climate list change.
    """
    if data is None:
        return True
    if 'profile_info' not in data:
        return True
    try:
        stored_v = (data['profile_info'] or {}).get('version')  # type: ignore[union-attr]
    except Exception:
        return True
    if stored_v != disk_profile_version:
        return True
    if 'climates' not in data:
        return True
    current = data['climates']  # type: ignore[assignment]
    if not isinstance(current, dict):
        return True
    for tid, rows in new_climates.items():
        if tid not in current:
            return True
        old = current[tid]
        if not isinstance(old, list) or len(old) != len(rows):
            return True
        for i, row in enumerate(rows):
            if i >= len(old) or old[i] != row:
                return True
    return False


def write_ecobee_climate_profile(
    base_dir: Path,
    climates: Mapping[str, List[Dict[str, str]]],
    *,
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
    log_prefix: str = 'profile_writer:',
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Write ``profile/nls/en_us.txt`` (from template), per-thermostat nodedef and editor snippets,
    and ``CT_<tstat>-<n>`` NLS lines. *climates* maps thermostat id string (digits) to API-style
    climate rows: ``{'name': str, 'ref': str}`` (ref is ecobee ``climateRef``).
    """
    log = logger or logging.getLogger(__name__)
    base_dir = Path(base_dir)

    en_us_txt = base_dir / 'profile' / 'nls' / 'en_us.txt'
    make_file_dir(str(en_us_txt))
    log.info('%s Writing %s', log_prefix, en_us_txt)
    nls_tmpl_path = base_dir / 'template' / 'en_us.txt'
    with open(nls_tmpl_path, 'r', encoding='utf-8') as nls_tmpl, open(
        en_us_txt, 'w', encoding='utf-8'
    ) as nls:
        for line in nls_tmpl:
            nls.write(line)

    nodedef_f = base_dir / 'profile' / 'nodedef' / 'custom.xml'
    log.info('%s Writing %s', log_prefix, nodedef_f)
    make_file_dir(str(nodedef_f))
    editor_f = base_dir / 'profile' / 'editor' / 'custom.xml'
    make_file_dir(str(editor_f))
    log.info('%s Writing %s', log_prefix, editor_f)

    thermostat_template = base_dir / 'template' / 'thermostat.xml'
    thermostat_homekit_template = base_dir / 'template' / 'thermostat_homekit.xml'
    editors_template = base_dir / 'template' / 'editors.xml'

    with open(nodedef_f, 'w', encoding='utf-8') as nodedef_h, open(
        editor_f, 'w', encoding='utf-8'
    ) as editor_h, open(en_us_txt, 'a', encoding='utf-8') as nls:
        nodedef_h.write('<nodedefs>\n')
        editor_h.write('<editors>\n')
        for tid in climates:
            with open(thermostat_template, 'r', encoding='utf-8') as in_h:
                for line in in_h:
                    nodedef_h.write(re.sub(r'tstatid', f'{tid}', line))
            if thermostat_homekit_template.is_file():
                with open(thermostat_homekit_template, 'r', encoding='utf-8') as in_h:
                    for line in in_h:
                        nodedef_h.write(re.sub(r'tstatid', f'{tid}', line))
            cnt_a = max(0, len(climate_catalog) - 1)
            cnt = max(0, len(climate_catalog) - 5)
            with open(editors_template, 'r', encoding='utf-8') as in_h:
                for line in in_h:
                    line = re.sub(r'tstatid', f'{tid}', line)
                    line = re.sub(r'tstatcnta', f'{cnt_a}', line)
                    line = re.sub(r'tstatcnt', f'{cnt}', line)
                    editor_h.write(line)
            nls.write('\n')
            nls.write(f'ND-EcobeeC_{tid}-NAME = Ecobee Thermostat {tid} (C)\n')
            nls.write(f'ND-EcobeeC_{tid}-ICON = Thermostat\n')
            nls.write(f'ND-EcobeeF_{tid}-NAME = Ecobee Thermostat {tid} (F)\n')
            nls.write(f'ND-EcobeeF_{tid}-ICON = Thermostat\n')
            nls.write(f'ND-EcobeewAQC_{tid}-NAME = Ecobee AQ Thermostat {tid} (C)\n')
            nls.write(f'ND-EcobeewAQC_{tid}-ICON = Thermostat\n')
            nls.write(f'ND-EcobeewAQF_{tid}-NAME = Ecobee AQ Thermostat {tid} (F)\n')
            nls.write(f'ND-EcobeewAQF_{tid}-ICON = Thermostat\n')
            nls.write(f'ND-EcobeeHKC_{tid}-NAME = Ecobee Thermostat {tid} (C, HomeKit)\n')
            nls.write(f'ND-EcobeeHKC_{tid}-ICON = Thermostat\n')
            nls.write(f'ND-EcobeeHKF_{tid}-NAME = Ecobee Thermostat {tid} (F, HomeKit)\n')
            nls.write(f'ND-EcobeeHKF_{tid}-ICON = Thermostat\n')
            custom_list: List[str] = []
            for i in range(len(climate_catalog)):
                ref = climate_catalog[i]
                custom_list.append(ref[0].upper() + ref[1:] if ref else str(i))
            for i in range(len(climate_catalog)):
                name = climate_catalog[i]
                for cli in climates[tid]:
                    if cli.get('ref') == name:
                        custom_list[i] = cli['name']
            log.debug('%s customList[%s]=%s', log_prefix, tid, custom_list)
            for i, label in enumerate(custom_list):
                nls.write(f'CT_{tid}-{i} = {label}\n')
        nodedef_h.write('</nodedefs>\n')
        editor_h.write('</editors>\n')
    log.info('%s done', log_prefix)


def apply_profile_update_if_needed(
    *,
    base_dir: Path,
    data: MutableMapping[str, object],
    poly,
    climates: Mapping[str, List[Dict[str, str]]],
    profile_info: Mapping[str, str],
    climate_catalog: Sequence[str] = DEFAULT_CLIMATE_CATALOG,
    log_prefix: str = '',
    logger: Optional[logging.Logger] = None,
) -> bool:
    """
    If *data* / *climates* warrant a refresh, write custom profile files, ``poly.updateProfile()``,
    and persist ``profile_info`` + ``climates`` into *data*. Returns whether an update ran.
    """
    log = logger or logging.getLogger(__name__)
    ver = str(profile_info.get('version', ''))
    if not profile_needs_update(data, ver, climates):
        return False
    write_ecobee_climate_profile(
        base_dir,
        climates,
        climate_catalog=climate_catalog,
        log_prefix=log_prefix or 'profile:',
        logger=log,
    )
    poly.updateProfile()
    data['profile_info'] = dict(profile_info)
    data['climates'] = {k: list(v) for k, v in climates.items()}
    return True
