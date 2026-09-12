"""Legacy HTML reader: a BeautifulSoup tree into :mod:`texsmith.ir.nodes`.

The reader of the legacy Python writers (``texsmith.writers.latex`` /
``texsmith.writers.typst``), reached through the ``html`` reader of
``Document.from_markdown`` — Python-Markdown → HTML → this reader → the
legacy writers. It shares the lowering registry (``@reads``), the attribute
helpers and the table reconstruction with :mod:`texsmith.readers.html`, which
produces the generated models for the tmark writers. Deleted with the legacy
writers in phase 5 of the TMark migration (``specs/tmark-migration.md``).
"""

from __future__ import annotations

from texsmith.readers.html.registry import NotHandled, ReaderRegistry, ReaderRule, ReadLevel, reads

from .context import ReadContext
from .reader import HtmlReader, build_reader_registry


__all__ = [
    "HtmlReader",
    "NotHandled",
    "ReadContext",
    "ReadLevel",
    "ReaderRegistry",
    "ReaderRule",
    "build_reader_registry",
    "reads",
]
