"""Compatibility wrapper re-exporting the LaTeX formatter."""

from __future__ import annotations

from .latex.formatter import LaTeXFormatter, optimize_list

__all__ = ["LaTeXFormatter", "optimize_list"]

