"""Public entry points for the margin-note inline extension."""

from __future__ import annotations

from .markdown import MarginNoteExtension, makeExtension


__all__ = [
    "MarginNoteExtension",
    "makeExtension",
]
