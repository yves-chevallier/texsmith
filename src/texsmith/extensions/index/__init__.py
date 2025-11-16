"""Public entry points for TeXSmith's hashtag index extension."""

from __future__ import annotations

from .markdown import TexsmithIndexExtension, makeExtension
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
    "makeExtension",
]
