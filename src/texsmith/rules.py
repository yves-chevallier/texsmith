"""Compatibility shim for :mod:`texsmith.domain.rules`."""

from __future__ import annotations

from .domain import rules as _rules
from .domain.rules import *  # noqa: F401,F403

__all__ = getattr(_rules, "__all__", [])
