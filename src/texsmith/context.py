"""Compatibility shim for :mod:`texsmith.domain.context`."""

from __future__ import annotations

from .domain import context as _context
from .domain.context import *  # noqa: F401,F403

__all__ = getattr(_context, "__all__", [])
