"""CLI command implementations exposed via `texsmith.cli`.

This module exists primarily to make the `texsmith.cli.commands` package
importable for documentation tools such as mkdocstrings. It re-exports the
Typer command factories defined in the sibling modules so downstream code can
import them using dotted paths (e.g. ``texsmith.cli.commands.build``).
"""

from __future__ import annotations

from .build import build, build_latexmk_command  # noqa: F401
from .convert import convert  # noqa: F401

__all__ = ["build", "build_latexmk_command", "convert"]
