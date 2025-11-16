"""Convenience alias for the LaTeX text styling Markdown extension."""

from __future__ import annotations

from .extensions.latex_text import LatexTextExtension, makeExtension


__all__ = ["LatexTextExtension", "makeExtension"]
