"""Compatibility package for :mod:`texsmith.ui.cli`."""

from __future__ import annotations

import sys

from ..ui import cli as _cli

sys.modules[__name__] = _cli
