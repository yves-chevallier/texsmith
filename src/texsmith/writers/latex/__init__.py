"""LaTeX writer package: emit LaTeX from the TeXSmith IR."""

from __future__ import annotations

from .escaper import escape_latex_chars
from .registry import WriterRegistry, writes
from .state import WriterState
from .writer import LaTeXWriteError, LaTeXWriter


__all__ = [
    "LaTeXWriteError",
    "LaTeXWriter",
    "WriterRegistry",
    "WriterState",
    "escape_latex_chars",
    "writes",
]
