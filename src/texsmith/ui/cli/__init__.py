"""Public CLI exports for TexSmith."""

from __future__ import annotations

from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS

from .app import app, main
from .commands import render
from .state import debug_enabled, emit_error, emit_warning, ensure_rich_compat, get_cli_state


__all__ = [
    "DEFAULT_MARKDOWN_EXTENSIONS",
    "app",
    "debug_enabled",
    "emit_error",
    "emit_warning",
    "ensure_rich_compat",
    "get_cli_state",
    "main",
    "render",
]
