"""Compatibility module for :mod:`texsmith.ui.cli.commands.convert`."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("texsmith.ui.cli.commands.convert")
globals().update(vars(_module))
sys.modules[__name__] = _module
