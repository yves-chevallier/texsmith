"""Public CLI exports for TexSmith."""

from __future__ import annotations

from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS

from .app import app, bibliography_app, latex_app, main, template_app
from .commands import build, convert
from .state import debug_enabled, emit_error, emit_warning, ensure_rich_compat, get_cli_state


__all__ = [
    "DEFAULT_MARKDOWN_EXTENSIONS",
    "app",
    "bibliography_app",
    "build",
    "convert",
    "debug_enabled",
    "emit_error",
    "emit_warning",
    "ensure_rich_compat",
    "get_cli_state",
    "latex_app",
    "main",
    "template_app",
]
