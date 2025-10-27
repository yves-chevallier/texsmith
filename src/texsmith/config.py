"""Compatibility shim for :mod:`texsmith.domain.config`."""

from __future__ import annotations

from .domain import config as _config
from .domain.config import *  # noqa: F401,F403

__all__ = getattr(_config, "__all__", [])
