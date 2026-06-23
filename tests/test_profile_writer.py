"""homekit_client.profile_writer unit tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from homekit_client.profile_writer import (
    climate_command_subset_hi,
    homekit_climate_details_for_device,
    homekit_gv3_command_subset_hi,
    profile_needs_update,
    write_ecobee_climate_profile,
)
from node_funcs import climateList, climateMap

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mini_plugin(tmp_path: Path) -> Path:
    shutil.copytree(PLUGIN_ROOT / 'template', tmp_path / 'template')
    return tmp_path


def test_homekit_climate_details_override():
    rows = [
        {
            'thermostat_id': '9243',
            'device_id': 'AA:BB',
            'climates': [{'climateRef': 'home', 'name': 'Custom'}],
        }
    ]
    d = homekit_climate_details_for_device('AA:BB', rows, climateList[:5], thermostat_id='9243')
    assert d[climateMap['home']]['name'] == 'Custom'
    assert d[0]['ref'] == climateList[0]


def test_homekit_climate_details_override_by_ref():
    rows = [
        {
            'thermostat_id': '9243',
            'climates': [{'climateRef': 'smart2', 'name': 'Movie Night'}],
        }
    ]
    d = homekit_climate_details_for_device('', rows, climateList[:8], thermostat_id='9243')
    assert d[climateMap['smart2']]['name'] == 'Movie Night'


def test_climate_command_subset_hi_from_api_climates():
    rows = [
        {'ref': 'away', 'name': 'Away'},
        {'ref': 'home', 'name': 'Home'},
        {'ref': 'smart3', 'name': 'Workshop'},
    ]
    assert climate_command_subset_hi(rows, climateList) == climateMap['smart3']


def test_climate_command_subset_hi_empty_falls_back_to_catalog():
    assert climate_command_subset_hi([], climateList) == len(climateList) - 1


def test_homekit_gv3_command_subset_hi_matches_first_four_climate_indices():
    assert homekit_gv3_command_subset_hi() == 3


def test_homekit_climate_details_skips_indices_when_requested():
    rows = [
        {
            'thermostat_id': '9243',
            'device_id': 'aa:bb',
            'climates': [{'climateRef': 'home', 'name': 'HubSlot1'}],
        }
    ]
    d = homekit_climate_details_for_device(
        'AA:BB',
        rows,
        climateList[:5],
        thermostat_id='9243',
        skip_catalog_indices={0, 1, 2, 3},
    )
    assert d[climateMap['home']]['name'] != 'HubSlot1'
    assert d[climateMap['home']]['name'] == (climateList[1][0].upper() + climateList[1][1:] if climateList[1] else '1')


def test_profile_needs_update_version_change():
    data = {'profile_info': {'version': 'old'}, 'climates': {}}
    assert profile_needs_update(data, 'new', {}) is True


def test_profile_needs_update_climate_row_change():
    climates_new = {'9243': [{'ref': 'home', 'name': 'Home'}]}
    data = {
        'profile_info': {'version': '1'},
        'climates': {'9243': [{'ref': 'home', 'name': 'Away'}]},
    }
    assert profile_needs_update(data, '1', climates_new) is True


def test_profile_needs_update_false_when_same():
    climates = {'9243': [{'ref': 'home', 'name': 'Home'}]}
    data = {'profile_info': {'version': '1'}, 'climates': {'9243': [{'ref': 'home', 'name': 'Home'}]}}
    assert profile_needs_update(data, '1', climates) is False


def test_write_ecobee_climate_profile_writes_custom_xml(mini_plugin: Path):
    climates = {
        '9243': [
            {'ref': 'away', 'name': 'Away'},
            {'ref': 'home', 'name': 'Home'},
            {'ref': 'sleep', 'name': 'Sleep'},
            {'ref': 'smart1', 'name': 'Workshop'},
            {'ref': 'smart2', 'name': 'Movie Night'},
        ],
    }
    write_ecobee_climate_profile(mini_plugin, climates, log_prefix='test:', climate_catalog=climateList[:6])
    nodedef = mini_plugin / 'profile' / 'nodedef' / 'custom.xml'
    assert nodedef.is_file()
    text = nodedef.read_text(encoding='utf-8')
    assert 'EcobeeC_9243' in text
    assert 'EcobeeHKC_9243' in text
    assert 'EcobeeHKF_9243' in text
    hk_c_block = text.split('EcobeeHKC_9243')[1].split('EcobeeHKF_9243')[0]
    assert 'CTA_9243' in hk_c_block
    assert 'CT_HK_9243' not in hk_c_block.split('<sts>')[1].split('</sts>')[0]
    assert 'HoldType' not in hk_c_block
    assert '9243' in text
    editor = mini_plugin / 'profile' / 'editor' / 'custom.xml'
    ed = editor.read_text(encoding='utf-8')
    assert 'CTA_9243' in ed
    assert 'CT_HK_9243' in ed
    assert 'subset="0-3"' in ed
    assert 'subset="0-4"' in ed  # cloud command: through smart2
    assert '_hk_hi' not in ed  # ``tstatcnt`` must not replace inside ``tstatcnt_hk_hi``
    assert 'I_HK_TSTAT_FAN_MODE' not in ed
    assert 'I_TSTAT_FAN_MODE' in text
    nls = (mini_plugin / 'profile' / 'nls' / 'en_us.txt').read_text(encoding='utf-8')
    assert 'CT_9243-0 = Away' in nls
    assert 'CT_9243-4 = Movie Night' in nls
    assert 'HK_TSTAT_FAN' not in nls
