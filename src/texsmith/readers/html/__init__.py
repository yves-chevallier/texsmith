"""HTML reader: lower a BeautifulSoup tree (Markdown output) into TeXSmith IR.

Public surface:

* :class:`HtmlReader` — ``read(html: str) -> ir.Document`` (or ``read_tree``);
* :func:`reads` / :class:`ReaderRegistry` / :class:`ReadLevel` — the extensible
  lowering registry;
* :class:`ReadContext` — threaded through every lowering.

The reader produces a pure, backend-agnostic IR tree and never emits LaTeX.
"""

from __future__ import annotations

from .context import ReadContext
from .reader import HtmlReader, build_reader_registry
from .registry import NotHandled, ReaderRegistry, ReaderRule, ReadLevel, reads


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
