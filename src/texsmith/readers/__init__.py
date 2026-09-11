"""Readers: lower an input format into the TeXSmith IR.

Two readers produce the generated models (:mod:`texsmith.ir.model`):
:mod:`texsmith.readers.tmark` parses Markdown with ``tmark.parse`` and
:class:`~texsmith.readers.html.HtmlReader` lowers an HTML page. The legacy
:mod:`texsmith.readers.html_legacy` feeds the legacy Python writers until
phase 5 of the migration. A reader never emits a backend string.
"""

from __future__ import annotations

from texsmith.readers.html import HtmlReader, ReaderRegistry, reads


__all__ = ["HtmlReader", "ReaderRegistry", "reads"]
