"""Unit tests for flat Custom Param normalization (no Polyglot)."""

from __future__ import annotations

import pytest

from params_flat import (
    DEFAULT_EFFECTIVE,
    default_backend_for_new_param_seed,
    format_param_notice_html,
    normalize_flat_params,
)


def test_defaults_when_empty_raw():
    out, errs = normalize_flat_params({})
    assert errs == []
    assert out['backend'] == 'homekit'
    assert out['hk_ws_url'] == DEFAULT_EFFECTIVE['hk_ws_url']
    assert out['dry_run'] == 'true'


def test_backend_seed_fresh_install_homekit():
    assert (
        default_backend_for_new_param_seed(
            customdata={},
            api_key_param='',
            poly_oauth_init=False,
            has_other_pg3_nodes=False,
        )
        == 'homekit'
    )


def test_backend_seed_cloud_oauth_init():
    assert (
        default_backend_for_new_param_seed(
            customdata={},
            api_key_param='',
            poly_oauth_init=True,
            has_other_pg3_nodes=False,
        )
        == 'cloud'
    )


def test_backend_seed_cloud_api_key():
    assert (
        default_backend_for_new_param_seed(
            customdata={},
            api_key_param='  sekret  ',
            poly_oauth_init=False,
            has_other_pg3_nodes=False,
        )
        == 'cloud'
    )


def test_backend_seed_cloud_token_data():
    assert (
        default_backend_for_new_param_seed(
            customdata={'tokenData': {'access_token': 'x'}},
            api_key_param='',
            poly_oauth_init=False,
            has_other_pg3_nodes=False,
        )
        == 'cloud'
    )


def test_backend_seed_cloud_other_nodes():
    assert (
        default_backend_for_new_param_seed(
            customdata={},
            api_key_param='',
            poly_oauth_init=False,
            has_other_pg3_nodes=True,
        )
        == 'cloud'
    )


def test_backend_homekit_trim_case():
    out, errs = normalize_flat_params({'backend': '  HomeKit  '})
    assert errs == []
    assert out['backend'] == 'homekit'


def test_invalid_backend_falls_back_to_prev():
    prev = {**DEFAULT_EFFECTIVE, 'backend': 'homekit'}
    out, errs = normalize_flat_params({'backend': 'lambda'}, prev)
    assert errs
    assert 'backend' in errs[0]
    assert out['backend'] == 'homekit'


def test_ws_url_valid():
    out, errs = normalize_flat_params({'hk_ws_url': 'wss://hub.example:8163/ws'})
    assert errs == []
    assert out['hk_ws_url'] == 'wss://hub.example:8163/ws'


def test_ws_url_invalid_falls_back():
    prev = {**DEFAULT_EFFECTIVE, 'hk_ws_url': 'ws://127.0.0.1:8163'}
    out, errs = normalize_flat_params({'hk_ws_url': 'http://nope'}, prev)
    assert errs
    assert out['hk_ws_url'] == 'ws://127.0.0.1:8163'


@pytest.mark.parametrize(
    'raw_uc,expected',
    [
        ('auto', 'auto'),
        ('TRUE', 'true'),
        ('False', 'false'),
    ],
)
def test_use_celsius(raw_uc, expected):
    out, errs = normalize_flat_params({'use_celsius': raw_uc})
    assert errs == []
    assert out['use_celsius'] == expected


def test_notice_html_wraps_errors():
    html = format_param_notice_html(['bad: x'])
    assert 'bad: x' in html
    assert '<br/>' in html
