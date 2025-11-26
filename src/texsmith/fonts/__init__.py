"""Utilities for matching Unicode text to available font fallbacks."""

from .fallback import NotoFallback, UnicodeClassSpec
from .locator import FontFiles, FontLocator
from .matcher import (
    FontIndex,
    FontMatchResult,
    check_installed,
    discover_installed_families,
    match_text,
    required_fonts,
    required_fonts_with_ranges,
)


__all__ = [
    "FontFiles",
    "FontIndex",
    "FontLocator",
    "FontMatchResult",
    "NotoFallback",
    "UnicodeClassSpec",
    "check_installed",
    "discover_installed_families",
    "match_text",
    "required_fonts",
    "required_fonts_with_ranges",
]
