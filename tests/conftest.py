"""Pytest configuration: ensure plugin root is on sys.path."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Dev / CI shells may lack optional runtime deps (e.g. aiomqtt on the eISY image only).
sys.modules.setdefault('aiomqtt', MagicMock())
if 'websockets' not in sys.modules:
    _websockets = types.ModuleType('websockets')
    _websockets_client = types.ModuleType('websockets.client')
    _websockets_client.WebSocketClientProtocol = MagicMock()
    sys.modules['websockets'] = _websockets
    sys.modules['websockets.client'] = _websockets_client
