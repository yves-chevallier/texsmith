"""Public API surface for font matching utilities."""

from __future__ import annotations

from pathlib import Path

from texsmith.fonts import (
    FontFiles,
    FontLocator,
    FontMatchResult,
    NotoFallback,
    match_text,
)


def match_fonts(
    text: str, *, fonts_yaml: Path | None = None, check_system: bool = True
) -> FontMatchResult:
    """Return the fonts required to cover the provided text payload."""
    return match_text(text, fonts_yaml=fonts_yaml, check_system=check_system)


__all__ = [
    "FontFiles",
    "FontLocator",
    "FontMatchResult",
    "NotoFallback",
    "match_fonts",
]
