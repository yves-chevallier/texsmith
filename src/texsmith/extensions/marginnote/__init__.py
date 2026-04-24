"""Public entry points for the margin-note inline extension."""

from __future__ import annotations

from .markdown import MarginNoteExtension, makeExtension
from .renderer import register as register_renderer, render_marginnote


__all__ = [
    "MarginNoteExtension",
    "makeExtension",
    "register_renderer",
    "render_marginnote",
]
