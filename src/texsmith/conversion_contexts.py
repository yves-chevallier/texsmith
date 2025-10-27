"""Compatibility shim for :mod:`texsmith.domain.conversion_contexts`."""

from __future__ import annotations

from .domain import conversion_contexts as _conversion_contexts
from .domain.conversion_contexts import *  # noqa: F401,F403

__all__ = getattr(_conversion_contexts, "__all__", [])
