"""Shared helpers for managing LaTeX partial identifiers."""

from __future__ import annotations

from pathlib import Path

from texsmith.adapters.latex.formatter import LaTeXFormatter


def normalise_partial_key(value: str) -> str:
    """Return a formatter-friendly identifier for a partial entry."""
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    path = Path(candidate)
    base = path.with_suffix("").as_posix()
    return LaTeXFormatter.normalise_key(base)


__all__ = ["normalise_partial_key"]
