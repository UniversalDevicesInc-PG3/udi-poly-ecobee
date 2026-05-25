"""Ecobee Node Server: dispatcher Controller + per-backend node implementations."""
# Bump only when cutting a beta or production store release; keep stable during development.
VERSION = "4.1.2"
from .Controller import Controller

__all__ = ["Controller", "VERSION"]
