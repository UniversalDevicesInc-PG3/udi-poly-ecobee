#!/usr/bin/env python3
"""PG3 controller node (ECO_CTR): dispatches lifecycle to cloud or HomeKit backend."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional, Union

import markdown2
from udi_interface import LOG_HANDLER, LOGGER, Custom, Node

from const import driversMap
from node_funcs import customdata_load_payload, customdata_user_snapshot
from nodes.backends.cloud.Controller import CloudBackend
from params_flat import (
    DEFAULT_EFFECTIVE,
    default_backend_for_new_param_seed,
    format_param_notice_html,
    normalize_flat_params,
)

# PG3 only lists Custom Params that exist in saved config; seed missing keys on load (Kasa/HomeKit pattern).
_DEFAULT_CUSTOM_PARAMS = {**DEFAULT_EFFECTIVE, 'api_key': ''}

TYPED_HK_ID_OVERRIDES = 'hk_id_overrides'
TYPED_HK_SENSOR_OVERRIDES = 'hk_sensor_overrides'
TYPED_CLIMATE_PROGRAMS = 'climate_programs'


class Controller(Node):
    id = 'ECO_CTR'
    drivers = deepcopy(driversMap['ECO_CTR'])
    commands = {
        'QUERY': 'cmd_query',
        'POLL': 'cmd_poll',
    }

    def updateDrivers(self, drivers):
        """Merge PG3 ``drivers`` into the full ``ECO_CTR`` template from :mod:`const`.

        On CONFIG, ``udi_interface`` replaces ``self.drivers`` with the list from
        Polyglot's database. After a profile upgrade (new GV4/GV5 on the controller),
        that list can still omit drivers IoX has not persisted yet, which makes
        ``setDriver('GV4'|'GV5')`` fail with *Invalid driver* and leaves transport
        status stuck at *Not in use*. Merging keeps template drivers and overlays
        stored values/uoms for keys PG3 does know about.
        """
        if not isinstance(drivers, list):
            super().updateDrivers(drivers)
            return
        merged = deepcopy(driversMap['ECO_CTR'])
        by_id = {d['driver']: d for d in merged}
        for row in drivers:
            key = row.get('driver')
            if not key or key not in by_id:
                continue
            tgt = by_id[key]
            if 'value' in row:
                tgt['value'] = row['value']
            if row.get('uom') is not None:
                tgt['uom'] = str(row['uom'])
        self.drivers = merged
        if len(drivers) < len(merged):
            LOGGER.debug(
                'Controller: merged %s PG3 driver row(s) into ECO_CTR template (%s); '
                'IoX profile sync will add missing keys to the database over time.',
                len(drivers),
                len(merged),
            )

    def __init__(self, poly, primary, address, name):
        self.Notices = Custom(poly, 'notices')
        self.Data = Custom(poly, 'customdata')
        self.Params = Custom(poly, 'customparams')
        self.TypedParams = Custom(poly, 'customtypedparams')
        self.TypedData = Custom(poly, 'customtypeddata')
        self.effective_params = dict(DEFAULT_EFFECTIVE)
        self._backend: Any = None
        self._active_backend_kind: Optional[str] = None
        # PG3 fires CONFIG / TYPED / NS before CUSTOMPARAMS; avoid picking cloud vs homekit until flat params load.
        self._custom_params_loaded = False
        self._poly_start_seen = False
        self._backend_poly_start_applied = False
        self._pending_cfg_data: Any = None
        self._pending_config_done = False
        super().__init__(poly, primary, address, name)
        self.name = name
        self._init_hk_typed_params()
        poly.subscribe(poly.START, self.handler_start, address)
        poly.subscribe(poly.STOP, self.handler_stop)
        poly.subscribe(poly.CONFIG, self.handler_config)
        poly.subscribe(poly.CONFIGDONE, self.handler_config_done)
        poly.subscribe(poly.POLL, self.handler_poll)
        poly.subscribe(poly.DISCOVER, self.handler_discover)
        poly.subscribe(poly.CUSTOMPARAMS, self.handler_params)
        poly.subscribe(poly.CUSTOMDATA, self.handler_data)
        poly.subscribe(poly.CUSTOMNS, self.handler_custom_ns)
        poly.subscribe(poly.OAUTH, self.handler_oauth)
        poly.subscribe(poly.LOGLEVEL, self.handler_log_level)
        poly.subscribe(poly.ADDNODEDONE, self.handler_add_node_done)
        poly.subscribe(poly.CUSTOMTYPEDPARAMS, self.handler_typed_params)
        poly.subscribe(poly.CUSTOMTYPEDDATA, self.handler_typed_data)
        poly.subscribe(poly.DELETE, self.handler_delete)
        poly.ready()
        poly.addNode(self, conn_status='ST')

    def _init_hk_typed_params(self) -> None:
        LOGGER.debug('init HomeKit typed params schema')
        self.TypedParams.load(
            [
                {
                    'name': TYPED_HK_ID_OVERRIDES,
                    'title': 'HomeKit thermostat address overrides',
                    'desc': 'Map hub device_id to an Ecobee thermostat id for IoX address t<id>.',
                    'isList': True,
                    'params': [
                        {'name': 'device_id', 'title': 'device_id (pairing id)', 'isRequired': False},
                        {'name': 'thermostat_id', 'title': 'thermostat_id (numeric/string)', 'isRequired': False},
                        {'name': 'notes', 'title': 'notes', 'isRequired': False},
                    ],
                },
                {
                    'name': TYPED_HK_SENSOR_OVERRIDES,
                    'title': 'HomeKit remote sensor address overrides',
                    'desc': 'Optional overrides for rs_* sensor node addresses.',
                    'isList': True,
                    'params': [
                        {'name': 'device_id', 'title': 'device_id', 'isRequired': False},
                        {'name': 'aid', 'title': 'aid', 'isRequired': False},
                        {'name': 'accessory_name', 'title': 'accessory_name', 'isRequired': False},
                        {'name': 'code', 'title': 'code (rs_ suffix)', 'isRequired': False},
                        {'name': 'notes', 'title': 'notes', 'isRequired': False},
                    ],
                },
                {
                    'name': TYPED_CLIMATE_PROGRAMS,
                    'title': 'Climate program labels',
                    'desc': 'Friendly names for VENDOR_ECOBEE_CURRENT_MODE indices (per device_id).',
                    'isList': True,
                    'params': [
                        {'name': 'device_id', 'title': 'device_id', 'isRequired': False},
                        {'name': 'index', 'title': 'mode index', 'isRequired': False},
                        {'name': 'name', 'title': 'display name', 'isRequired': False},
                        {'name': 'notes', 'title': 'notes', 'isRequired': False},
                    ],
                },
            ],
            True,
        )

    def _validate_params(self) -> Optional[str]:
        raw = {k: self.Params[k] for k in self.Params.keys()}
        merged, errs = normalize_flat_params(raw, self.effective_params)
        self.effective_params.clear()
        self.effective_params.update(merged)
        if errs:
            for line in errs:
                LOGGER.warning('Param validation: %s', line)
            return format_param_notice_html(errs)
        return None

    def _has_non_controller_poly_nodes(self) -> bool:
        """True if Polyglot already has nodes besides this NS controller (legacy cloud installs)."""
        try:
            for n in self.poly.nodes():
                addr = str(getattr(n, 'address', '') or '').strip().lower()
                if not addr or addr == 'controller':
                    continue
                return True
        except Exception:
            LOGGER.debug('non-controller node scan failed', exc_info=True)
        return False

    def _ensure_default_custom_params(self) -> None:
        """Seed keys missing from PG3 store so the config editor shows new/flat params after upgrades."""
        init = getattr(self.poly, 'init', None) or {}
        oauth_init = bool(isinstance(init, dict) and init.get('oauth'))
        try:
            api_key_raw = self.Params['api_key'] if 'api_key' in self.Params else ''
        except Exception:
            api_key_raw = ''
        data_snap = customdata_user_snapshot(self.Data)
        has_other_nodes = self._has_non_controller_poly_nodes()
        for key, default in _DEFAULT_CUSTOM_PARAMS.items():
            if key in self.Params:
                continue
            if key == 'backend':
                default = default_backend_for_new_param_seed(
                    customdata=data_snap,
                    api_key_param=str(api_key_raw or ''),
                    poly_oauth_init=oauth_init,
                    has_other_pg3_nodes=has_other_nodes,
                )
            try:
                self.Params[key] = default
                LOGGER.info(
                    'Seeded default Custom Param %s=%r (first time / missing in PG3 store)',
                    key,
                    default,
                )
            except Exception:
                LOGGER.exception('Failed to seed default Custom Param %s', key)

    def _ensure_backend(self) -> None:
        if not self._custom_params_loaded:
            return
        kind = self.effective_params.get('backend', DEFAULT_EFFECTIVE['backend'])
        if self._backend is not None and self._active_backend_kind == kind:
            return
        if self._backend is not None:
            try:
                self._backend.close()
            except Exception:
                LOGGER.debug('backend close failed', exc_info=True)
        if kind == 'homekit':
            from nodes.backends.homekit.Controller import HomeKitBackend

            self._backend = HomeKitBackend(self)
        else:
            self._backend = CloudBackend(self)
        self._active_backend_kind = kind
        self._backend_poly_start_applied = False
        LOGGER.info('Ecobee backend active: %s', kind)

    def _replay_customdata_to_backend(self) -> None:
        """
        If PG3 delivered CUSTOMDATA before CUSTOMPARAMS, :meth:`handler_data` only loaded
        ``Custom(poly, 'customdata')`` early and returned without notifying the backend.
        Replay the current store once params are loaded so backends (e.g. HomeKit) can set
        ``handler_data_st`` before :meth:`handler_start`.
        """
        if self._backend is None or not hasattr(self._backend, 'handler_data'):
            return
        try:
            d = customdata_user_snapshot(self.Data)
        except Exception:
            LOGGER.debug('customdata replay: user snapshot failed', exc_info=True)
            return
        if d is None:
            d = {}
        try:
            self._backend.handler_data(d)
        except Exception:
            LOGGER.exception('customdata replay to backend failed')

    def _flush_pending_config_to_backend(self) -> None:
        """Replay CONFIG / CONFIGDONE received before flat custom params were ready."""
        if not self._custom_params_loaded or self._backend is None:
            return
        if self._pending_cfg_data is not None:
            self._backend.handler_config(self._pending_cfg_data)
            self._pending_cfg_data = None
        if self._pending_config_done:
            self._backend.handler_config_done()
            self._pending_config_done = False

    def _apply_backend_poly_start(self) -> None:
        """Run backend.handler_start() once Poly START and flat params have both been seen."""
        if not (self._custom_params_loaded and self._poly_start_seen):
            return
        self._ensure_backend()
        if self._backend is None:
            return
        if self._backend_poly_start_applied:
            return
        self._backend.handler_start()
        self._backend_poly_start_applied = True

    # --- Polyglot handlers ---

    def handler_start(self):
        cfg_md = Path(__file__).resolve().parent.parent / "CONFIG.md"
        if cfg_md.is_file():
            try:
                self.poly.setCustomParamsDoc(
                    markdown2.markdown_path(
                        str(cfg_md),
                        extras=["tables", "fenced-code-blocks"],
                    )
                )
            except Exception:
                LOGGER.exception("Failed to convert/set CONFIG.md as custom params doc")
        self._poly_start_seen = True
        self._flush_pending_config_to_backend()
        self._apply_backend_poly_start()

    def handler_stop(self):
        if self._backend:
            self._backend.handler_stop()

    def handler_config(self, cfg_data):
        if not self._custom_params_loaded:
            self._pending_cfg_data = cfg_data
            return
        self._ensure_backend()
        if self._backend:
            self._backend.handler_config(cfg_data)

    def handler_config_done(self):
        if not self._custom_params_loaded:
            self._pending_config_done = True
            return
        self._ensure_backend()
        if self._backend:
            self._backend.handler_config_done()

    def handler_poll(self, polltype):
        if not self._custom_params_loaded:
            return
        self._ensure_backend()
        if self._backend:
            self._backend.handler_poll(polltype)

    def handler_discover(self):
        if not self._custom_params_loaded:
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'discover'):
            self._backend.discover()

    def handler_params(self, params):
        self.Params.load(params)
        self._ensure_default_custom_params()
        bad = self._validate_params()
        if bad:
            self.Notices['homekit_bad_param'] = bad
        else:
            self.Notices.delete('homekit_bad_param')
        self._custom_params_loaded = True
        prev_kind = self._active_backend_kind
        self._ensure_backend()
        self._flush_pending_config_to_backend()
        if prev_kind is not None and prev_kind != self._active_backend_kind:
            self.Notices['homekit_backend_changed'] = (
                f'Backend changed from {prev_kind} to {self._active_backend_kind}. '
                'Node behavior follows the new backend after this reload cycle.'
            )
        if self._backend:
            self._backend.handler_params(params)
        self._replay_customdata_to_backend()
        if self._backend and hasattr(self._backend, 'sync_param_notices'):
            self._backend.sync_param_notices()
        self._apply_backend_poly_start()

    def handler_data(self, data):
        if not self._custom_params_loaded:
            if data is not None:
                try:
                    payload = customdata_load_payload(data)
                    if payload is not None:
                        self.Data.load(payload)
                except Exception:
                    LOGGER.exception('Early custom data load failed')
            return
        self._ensure_backend()
        if self._backend:
            self._backend.handler_data(data)

    def handler_custom_ns(self, key, data):
        if not self._custom_params_loaded:
            return
        if self.effective_params.get('backend', DEFAULT_EFFECTIVE['backend']) != 'cloud':
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'handler_nsdata'):
            self._backend.handler_nsdata(key, data)

    def handler_oauth(self, oauth):
        if not self._custom_params_loaded:
            return
        if self.effective_params.get('backend', DEFAULT_EFFECTIVE['backend']) != 'cloud':
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'oauth'):
            self._backend.oauth(oauth)

    def handler_log_level(self, level):
        if self._custom_params_loaded:
            self._ensure_backend()
            if self._backend and hasattr(self._backend, 'handler_log_level'):
                self._backend.handler_log_level(level)
                return
        import logging

        lvl = level.get('level', 10) if isinstance(level, dict) else 10
        if lvl < 10:
            LOG_HANDLER.set_basic_config(True, logging.DEBUG)
        else:
            LOG_HANDLER.set_basic_config(True, logging.WARNING)

    def handler_add_node_done(self, node: Union[dict, Any]):
        if not self._custom_params_loaded:
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'node_queue'):
            if isinstance(node, dict):
                addr = node.get('address')
            else:
                addr = getattr(node, 'address', None)
            if addr is not None:
                self._backend.node_queue({'address': addr})

    def handler_typed_params(self, data):
        if not self._custom_params_loaded:
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'handler_typed_params'):
            self._backend.handler_typed_params(data)

    def handler_typed_data(self, data):
        if not self._custom_params_loaded:
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'handler_typed_data'):
            self._backend.handler_typed_data(data)

    def handler_delete(self):
        if not self._custom_params_loaded:
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'delete'):
            self._backend.delete()

    def cmd_query(self, cmd=None):
        if not self._custom_params_loaded:
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'cmd_query'):
            self._backend.cmd_query(cmd)

    def cmd_poll(self, cmd=None):
        if not self._custom_params_loaded:
            return
        self._ensure_backend()
        if self._backend and hasattr(self._backend, 'cmd_poll'):
            self._backend.cmd_poll(cmd)
