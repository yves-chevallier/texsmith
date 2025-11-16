"""Convenience alias for the missing footnotes Markdown extension."""

from __future__ import annotations

from .extensions.missing_footnotes import MissingFootnotesExtension, makeExtension


__all__ = ["MissingFootnotesExtension", "makeExtension"]
