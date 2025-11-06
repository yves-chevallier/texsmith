"""Public entry points for the texsmith-index package."""

from __future__ import annotations

from .markdown import TexsmithIndexExtension
from .registry import (
    IndexEntry,
    IndexRegistry,
    clear_registry,
    get_registry,
)


__all__ = [
    "IndexEntry",
    "IndexRegistry",
    "TexsmithIndexExtension",
    "clear_registry",
    "get_registry",
]
