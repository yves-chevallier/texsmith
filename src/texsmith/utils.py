"""Compatibility shim for :mod:`texsmith.domain.utils`."""

from __future__ import annotations

from .domain import utils as _utils
from .domain.utils import *  # noqa: F401,F403

__all__ = getattr(_utils, "__all__", [])
