"""Cloud backend construction (regression: serverdata must bind to dispatcher.poly)."""

from __future__ import annotations

from unittest.mock import MagicMock

from nodes.backends.cloud.Controller import CloudBackend


def test_cloud_backend_init_binds_serverdata():
    poly = MagicMock()
    poly.serverdata = {'version': 'test-ns', 'api_key': 'k'}

    d = MagicMock()
    d.poly = poly
    d.address = 'controller'
    d.Notices = MagicMock()
    d.Data = MagicMock()
    d.Params = MagicMock()

    b = CloudBackend(d)
    assert b.serverdata is poly.serverdata
    assert b.poly is poly
