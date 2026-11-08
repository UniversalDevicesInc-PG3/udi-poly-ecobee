"""Cloud backend construction (regression: serverdata must bind to dispatcher.poly)."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from nodes.backends.cloud.Controller import CloudBackend


def _backend():
    poly = MagicMock()
    poly.serverdata = {'version': 'test-ns', 'api_key': 'k'}

    d = MagicMock()
    d.poly = poly
    d.address = 'controller'
    d.Notices = MagicMock()
    d.Data = MagicMock()
    d.Params = MagicMock()
    return CloudBackend(d)


def _expires_in(seconds: float) -> str:
    return (datetime.now() + timedelta(seconds=seconds)).strftime('%Y-%m-%dT%H:%M:%S')


def test_cloud_backend_init_binds_serverdata():
    b = _backend()
    assert b.serverdata is b.poly.serverdata
    assert b.poly is b.dispatcher.poly


def test_refresh_lead_is_one_long_poll_capped_at_five_minutes():
    b = _backend()
    b.cfg_longPoll = 180
    assert b._refresh_lead_seconds() == 180
    b.cfg_longPoll = 600
    assert b._refresh_lead_seconds() == 300
    b.cfg_longPoll = 0
    assert b._refresh_lead_seconds() == 300


def test_check_tokens_skips_refresh_until_long_poll():
    b = _backend()
    b.cfg_longPoll = 180
    b.tokenData = {
        'access_token': 'a',
        'refresh_token': 'r',
        'expires': _expires_in(120),
    }
    b._skip_refresh_until_long_poll = True
    b._getRefresh = MagicMock(return_value=True)
    assert b._checkTokens() is True
    b._getRefresh.assert_not_called()


def test_check_tokens_refreshes_inside_lead_window():
    b = _backend()
    b.cfg_longPoll = 180
    b.tokenData = {
        'access_token': 'a',
        'refresh_token': 'r',
        'expires': _expires_in(30),
    }
    b._skip_refresh_until_long_poll = False
    b._getRefresh = MagicMock(return_value=True)
    assert b._checkTokens() is True
    b._getRefresh.assert_called_once()


def test_end_refresh_installs_token_used_by_api_calls():
    b = _backend()
    b.tokenData = {
        'access_token': 'old',
        'token_type': 'Bearer',
        'refresh_token': 'r',
        'expires': '2026-11-06T18:07:05',
    }
    new = {
        'access_token': 'new',
        'token_type': 'Bearer',
        'refresh_token': 'r',
        'expires_in': 3600,
    }
    b._endRefresh(new)
    assert b.tokenData['access_token'] == 'new'
    assert b.tokenData['expires']
    assert b.token['access_token'] == 'new'
    assert b.token is not b.tokenData
    b.Data.__setitem__.assert_called_with('tokenData', new)


def test_get_refresh_success_replaces_access_token():
    b = _backend()
    b.api_key = 'k'
    b._skip_refresh_until_long_poll = True
    b.tokenData = {
        'refresh_token': 'r',
        'access_token': 'old',
        'token_type': 'Bearer',
        'expires': _expires_in(-60),
    }
    b.session = MagicMock()
    b.session.post.return_value = {
        'code': 200,
        'data': {
            'access_token': 'new',
            'token_type': 'Bearer',
            'refresh_token': 'r2',
            'expires_in': 3600,
        },
    }
    assert b._getRefresh() is True
    assert b.tokenData['access_token'] == 'new'
    assert b.tokenData['token_type'] == 'Bearer'
    assert b._skip_refresh_until_long_poll is False


def test_get_refresh_defers_further_attempts_on_429():
    b = _backend()
    b.api_key = 'k'
    b.tokenData = {'refresh_token': 'r', 'access_token': 'a', 'expires': _expires_in(30)}
    b.session = MagicMock()
    b.session.post.return_value = {'code': 429, 'data': False}
    assert b._getRefresh() is False
    assert b._skip_refresh_until_long_poll is True
    b.session.post.assert_called_once()


def test_startup_timeout_continues_when_only_nsdata_is_missing():
    b = _backend()
    b.handler_config_st = True
    b.handler_config_done_st = True
    b.handler_params_st = True
    b.handler_data_st = True
    b.handler_nsdata_st = None
    b.Params.get.return_value = 'user-key'
    assert b._give_up_on_startup_wait() is False
    assert b.handler_nsdata_st is False


def test_startup_timeout_stops_without_api_key():
    b = _backend()
    b.handler_config_st = True
    b.handler_config_done_st = True
    b.handler_params_st = True
    b.handler_data_st = True
    b.handler_nsdata_st = None
    b.Params.get.return_value = ''
    assert b._give_up_on_startup_wait() is True


def test_nsdata_before_params_is_replayed_to_cloud():
    from nodes.Controller import Controller as Dispatcher

    c = Dispatcher.__new__(Dispatcher)
    c._custom_params_loaded = False
    c._pending_nsdata = None
    c.effective_params = {'backend': 'cloud'}
    c.handler_custom_ns('nsdata', {'api_key_pin': 'pin'})
    assert c._pending_nsdata == ('nsdata', {'api_key_pin': 'pin'})

    backend = MagicMock()
    c._backend = backend
    c._ensure_backend = lambda: None
    c._replay_nsdata_to_backend()
    backend.handler_nsdata.assert_called_once_with('nsdata', {'api_key_pin': 'pin'})
    assert c._pending_nsdata is None


def test_typed_data_before_params_is_kept_and_replayed():
    from nodes.Controller import Controller as Dispatcher

    c = Dispatcher.__new__(Dispatcher)
    c._custom_params_loaded = False
    c._pending_typed_data = None
    c._typed_data_loaded = False
    c.TypedData = MagicMock()
    payload = {
        'climate_programs': [
            {
                'thermostat_id': '411956665463',
                'climates': [{'climateRef': 'away', 'name': 'Away', 'heat': '68.0', 'cool': '76.0'}],
            }
        ]
    }
    c.handler_typed_data(payload)
    assert c._pending_typed_data == payload
    assert c._typed_data_loaded is True
    c.TypedData.load.assert_called_once_with(payload)

    backend = MagicMock()
    c._backend = backend
    c._replay_typed_data_to_backend()
    backend.handler_typed_data.assert_called_once_with(payload)
    assert c._pending_typed_data is None
