"""HTML reader: lower a BeautifulSoup tree (Markdown output) into the generated IR.

Public surface:

* :class:`HtmlReader` — ``read(html: str) -> texsmith.ir.model.Document`` (or
  ``read_tree``);
* :func:`reads` / :class:`ReaderRegistry` / :class:`ReadLevel` — the extensible
  lowering registry;
* :class:`ReadContext` — threaded through every lowering.

The reader produces the same models ``tmark.parse`` does (``specs/migration/
python-ir-and-passes.md`` §2) and never emits a backend string: an HTML input
(``Document.from_html``) goes through the passes and the tmark writers like a
Markdown one.
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
