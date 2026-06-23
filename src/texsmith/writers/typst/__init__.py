"""Typst writer package: emit Typst markup from the TeXSmith IR.

The project's second backend (see ``refactoring/PLAN.md`` Phase 4). It consumes
the same IR as the LaTeX backend without touching ``readers/`` or ``ir/``.
"""

from __future__ import annotations

from texsmith.writers.registry import WriterRegistry, writes

from .document import render_document
from .escaper import escape_typst_chars
from .state import TypstWriterState
from .writer import TypstWriteError, TypstWriter


__all__ = [
    "TypstWriteError",
    "TypstWriter",
    "TypstWriterState",
    "WriterRegistry",
    "escape_typst_chars",
    "render_document",
    "writes",
]
