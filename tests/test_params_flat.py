"""Unit tests for flat Custom Param normalization (no Polyglot)."""

from __future__ import annotations

import pytest

from params_flat import (
    DEFAULT_EFFECTIVE,
    DEFAULT_HK_HEAT_COOL_MIN_DELTA,
    DEFAULT_HK_MQTT_CLIENT_SLUG,
    default_backend_for_new_param_seed,
    format_param_notice_html,
    heat_cool_min_span_degrees,
    normalize_flat_params,
)


def test_defaults_when_empty_raw():
    out, errs = normalize_flat_params({})
    assert errs == []
    assert out['backend'] == 'homekit'
    # MQTT is the preferred HomeKit hub transport on new installs (4.1.0+).
    assert out['hk_transport'] == 'mqtt'
    assert DEFAULT_EFFECTIVE['hk_transport'] == 'mqtt'
    assert out['hk_ws_url'] == DEFAULT_EFFECTIVE['hk_ws_url']
    assert out['hk_mqtt_client_slug'] == DEFAULT_HK_MQTT_CLIENT_SLUG == DEFAULT_EFFECTIVE['hk_mqtt_client_slug']
    assert out['dry_run'] == 'false'
    assert out['hk_heat_cool_min_delta'] == DEFAULT_HK_HEAT_COOL_MIN_DELTA


def test_hk_heat_cool_min_delta_default_span():
    assert heat_cool_min_span_degrees(False, {}) == 3.0
    assert heat_cool_min_span_degrees(True, {}) == 3.0


def test_hk_heat_cool_min_delta_custom():
    eff = {'hk_heat_cool_min_delta': '2'}
    assert heat_cool_min_span_degrees(False, eff) == 2.0
    assert heat_cool_min_span_degrees(True, eff) == 2.0


def test_hk_heat_cool_min_delta_invalid_falls_back():
    prev = {**DEFAULT_EFFECTIVE, 'hk_heat_cool_min_delta': '3'}
    out, errs = normalize_flat_params({'hk_heat_cool_min_delta': '0'}, prev)
    assert errs
    assert out['hk_heat_cool_min_delta'] == '3'


def test_empty_hk_transport_falls_back_to_default():
    """Blank ``hk_transport`` (e.g. seeded but never edited) uses :data:`DEFAULT_EFFECTIVE`."""
    out, errs = normalize_flat_params({'hk_transport': ''})
    assert errs == []
    assert out['hk_transport'] == DEFAULT_EFFECTIVE['hk_transport']


def test_mqtt_transport_preserved_slugs():
    out, errs = normalize_flat_params(
        {
            'hk_transport': 'mqtt',
            'hk_mqtt_hub_slug': 'hub1',
            'hk_mqtt_client_slug': 'my-client',
        }
    )
    assert errs == []
    assert out['hk_transport'] == 'mqtt'
    assert out['hk_mqtt_hub_slug'] == 'hub1'
    assert out['hk_mqtt_client_slug'] == 'my-client'


def test_mqtt_invalid_client_slug_falls_back():
    prev = {**DEFAULT_EFFECTIVE, 'hk_mqtt_client_slug': 'my-plugin-ns'}
    out, errs = normalize_flat_params({'hk_mqtt_client_slug': 'bad slug!'}, prev)
    assert errs
    assert out['hk_mqtt_client_slug'] == 'my-plugin-ns'


def test_ws_url_not_validated_when_mqtt_transport():
    out, errs = normalize_flat_params({'hk_transport': 'mqtt', 'hk_ws_url': 'http://nope'})
    assert errs == []
    assert out['hk_ws_url'] == 'http://nope'


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
    # Validation only runs when ``hk_transport`` is ``websocket`` (MQTT preserves the URL verbatim).
    prev = {**DEFAULT_EFFECTIVE, 'hk_transport': 'websocket', 'hk_ws_url': 'ws://127.0.0.1:8163'}
    out, errs = normalize_flat_params(
        {'hk_transport': 'websocket', 'hk_ws_url': 'http://nope'}, prev
    )
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
