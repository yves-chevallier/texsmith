"""Readers: lower an input format into the TeXSmith IR.

Today the only reader is :class:`~texsmith.readers.html.HtmlReader`, which
consumes the HTML produced by the Markdown front-end. A reader's output is a
pure :class:`texsmith.ir.Document`; it never emits a backend string.
"""

from __future__ import annotations

from texsmith.readers.html import HtmlReader, ReaderRegistry, reads


__all__ = ["HtmlReader", "ReaderRegistry", "reads"]
