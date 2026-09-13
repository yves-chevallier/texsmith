"""Public CLI exports for TexSmith."""

from __future__ import annotations

from .app import app, main
from .commands.render import render
from .state import debug_enabled, emit_error, emit_warning, ensure_rich_compat, get_cli_state


__all__ = [
    "app",
    "debug_enabled",
    "emit_error",
    "emit_warning",
    "ensure_rich_compat",
    "get_cli_state",
    "main",
    "render",
]
