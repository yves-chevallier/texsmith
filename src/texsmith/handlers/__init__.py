"""Compatibility package for :mod:`texsmith.adapters.handlers`."""

from __future__ import annotations

import sys

from ..adapters import handlers as _handlers

sys.modules[__name__] = _handlers
