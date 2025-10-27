"""Compatibility shim for :mod:`texsmith.domain.exceptions`."""

from __future__ import annotations

from .domain import exceptions as _exceptions
from .domain.exceptions import *  # noqa: F401,F403

__all__ = getattr(_exceptions, "__all__", [])
