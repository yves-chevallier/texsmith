"""Convenience alias for the small caps Markdown extension."""

from __future__ import annotations

from .adapters.markdown_extensions.smallcaps import SmallCapsExtension, makeExtension

__all__ = ["SmallCapsExtension", "makeExtension"]
