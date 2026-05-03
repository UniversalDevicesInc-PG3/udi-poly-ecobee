"""customdata_user_snapshot / customdata_load_payload (udi_interface.Custom quirks)."""

from __future__ import annotations

from types import SimpleNamespace

from node_funcs import customdata_load_payload, customdata_user_snapshot


class _FakeCustom:
    """Minimal stand-in for udi_interface.Custom user-key iteration."""

    def __init__(self, raw):
        self._rawdata = raw

    def __iter__(self):
        return iter(self._rawdata)

    def __getitem__(self, key):
        return self._rawdata[key]


def test_user_snapshot_iterates_raw_only():
    store = _FakeCustom({'profile_info': {'version': '1'}, 'climates': {}})
    snap = customdata_user_snapshot(store)
    assert snap == {'profile_info': {'version': '1'}, 'climates': {}}
    assert 'poly' not in snap


def test_user_snapshot_strips_internal_if_present():
    store = _FakeCustom({'poly': 'oops', 'profile_info': {'version': '1'}})
    snap = customdata_user_snapshot(store)
    assert 'poly' not in snap
    assert snap['profile_info']['version'] == '1'


def test_load_payload_strips_internal_keys():
    assert customdata_load_payload({'profile_info': {'version': '2'}, '_extradata': {}}) == {
        'profile_info': {'version': '2'}
    }


def test_load_payload_recover_from_custom_dump_shape():
    mistaken = {
        'poly': SimpleNamespace(),
        'custom': 'customdata',
        '_rawdata': {'profile_info': {'version': '3'}, 'climates': {'9': []}},
        '_extradata': {},
    }
    out = customdata_load_payload(mistaken)
    assert out == {'profile_info': {'version': '3'}, 'climates': {'9': []}}
    assert 'poly' not in out


def test_load_payload_none():
    assert customdata_load_payload(None) is None
