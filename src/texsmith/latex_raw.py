"""Convenience alias for the raw LaTeX Markdown extension."""

from __future__ import annotations

from .extensions.latex_raw import LatexRawExtension, makeExtension


__all__ = ["LatexRawExtension", "makeExtension"]
