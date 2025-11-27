"""CLI command implementations exposed via `texsmith.ui.cli`.

This module exists primarily to make the `texsmith.ui.cli.commands` package
importable for documentation tools such as mkdocstrings. It re-exports the
Typer command factories defined in the sibling modules so downstream code can
import them using dotted paths (e.g. ``texsmith.ui.cli.commands.render``).
"""

from __future__ import annotations

from .render import render


__all__ = ["render"]
