"""Convenience alias for the Mermaid Markdown extension."""

from __future__ import annotations

from .adapters.markdown_extensions.mermaid import MermaidExtension, makeExtension


__all__ = ["MermaidExtension", "makeExtension"]
