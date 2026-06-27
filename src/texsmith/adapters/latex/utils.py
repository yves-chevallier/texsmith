"""LaTeX escaping — single source of truth lives in the LaTeX writer.

Escaping is a backend responsibility, so the canonical implementation moved to
:mod:`texsmith.writers.latex.escaper`. This module re-exports it so existing
importers (templates, fonts, extensions, legacy handler helpers) keep a stable
import path without duplicating the logic.
"""

from __future__ import annotations

from texsmith.writers.latex.escaper import escape_latex_chars


__all__ = ["escape_latex_chars"]
