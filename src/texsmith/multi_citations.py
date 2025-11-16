"""Convenience alias for the multi-citations Markdown extension."""

from __future__ import annotations

from .extensions.multi_citations import MultiCitationExtension, makeExtension


__all__ = ["MultiCitationExtension", "makeExtension"]
