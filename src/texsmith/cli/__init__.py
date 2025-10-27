"""Compatibility package for :mod:`texsmith.ui.cli`."""

from __future__ import annotations

import importlib
import sys

from ..ui import cli as _cli


sys.modules[__name__] = _cli
sys.modules[f"{__name__}.commands"] = importlib.import_module("texsmith.ui.cli.commands")
sys.modules[f"{__name__}.commands.build"] = importlib.import_module("texsmith.ui.cli.commands.build")
sys.modules[f"{__name__}.commands.convert"] = importlib.import_module("texsmith.ui.cli.commands.convert")
sys.modules[f"{__name__}.commands.templates"] = importlib.import_module(
    "texsmith.ui.cli.commands.templates"
)
