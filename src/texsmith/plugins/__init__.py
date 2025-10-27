"""Compatibility package for :mod:`texsmith.adapters.plugins`."""

from __future__ import annotations

import sys

from ..adapters import plugins as _plugins

sys.modules[__name__] = _plugins
