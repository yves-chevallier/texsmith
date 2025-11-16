"""Public API exposing TeXSmith's hashtag index extension."""

from __future__ import annotations

from .extensions.index import (
    IndexEntry,
    IndexRegistry,
    TexsmithIndexExtension,
    clear_registry,
    get_registry,
)
from .extensions.index.markdown import makeExtension
from .extensions.index.mkdocs_plugin import IndexPlugin
from .extensions.index.renderer import register as register_renderer


__all__ = [
    "IndexEntry",
    "IndexPlugin",
    "IndexRegistry",
    "TexsmithIndexExtension",
    "clear_registry",
    "get_registry",
    "makeExtension",
    "register_renderer",
]
