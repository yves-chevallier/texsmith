"""Convenience alias exposing the raw LaTeX Markdown extension."""

from __future__ import annotations

from .extensions.latex_raw import LatexRawExtension as RawLatexExtension, makeExtension


__all__ = ["RawLatexExtension", "makeExtension"]
