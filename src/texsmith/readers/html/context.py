"""Reader context: diagnostics, the document-level registries and the recursion.

A :class:`ReadContext` is threaded through every lowering. It carries the
diagnostic records (so an unrecognised construct is *reported*, never
dropped), the footnote and abbreviation definitions a document accumulates
(``Document.footnotes`` / ``Document.abbreviations`` in the generated models)
and exposes the recursive entry points a handler needs to lower its own
children: :meth:`lower_inline`, :meth:`inline_content` and
:meth:`lower_blocks`. Keeping the recursion on the context (rather than
importing the reader into every handler module) avoids an import cycle and
keeps handlers small and declarative.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from texsmith.diagnostics import Diagnostic, Span, default_severity
from texsmith.ir import model


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable

    from bs4.element import PageElement, Tag


#: A construct the generated models cannot express; kept as a ``Div`` / ``Span``.
READER_UNSUPPORTED = "reader-unsupported"
#: A ``///`` block marker Python-Markdown left as prose.
READER_UNPROCESSED_BLOCK = "reader-unprocessed-block"


class _Lowerer(Protocol):
    """The subset of :class:`HtmlReader` the context delegates back into."""

    def lower_inline(self, children: Iterable[PageElement]) -> tuple[model.Inline, ...]: ...

    def lower_blocks(self, children: Iterable[PageElement]) -> tuple[model.Block, ...]: ...


class Diagnostics(Protocol):
    """Minimal emitter shape (matches :class:`core.diagnostics.DiagnosticEmitter`)."""

    def diagnostic(self, diagnostic: Diagnostic) -> None: ...


class ReadContext:
    """Per-read state handed to every lowering."""

    __slots__ = ("_emitter", "_reader", "abbreviations", "diagnostics", "file", "footnotes")

    def __init__(self, reader: _Lowerer, emitter: Diagnostics, *, file: int = 0) -> None:
        self._reader = reader
        self._emitter = emitter
        self.file = file
        self.diagnostics: list[Diagnostic] = []
        self.footnotes: list[model.Footnote] = []
        self.abbreviations: dict[str, str] = {}

    # -- recursion ---------------------------------------------------------

    def lower_inline(self, nodes: Iterable[PageElement]) -> tuple[model.Inline, ...]:
        """Lower a run of HTML children into inline IR nodes, whitespace verbatim."""
        return self._reader.lower_inline(nodes)

    def inline_content(self, host: Tag | Iterable[PageElement]) -> tuple[model.Inline, ...]:
        """Lower the phrasing content of a paragraph-like host, edges trimmed.

        The whitespace Python-Markdown leaves around a block's text (a
        newline after ``<li>``, the space before a stripped anchor) is not
        content: the leading and trailing whitespace of the run is dropped, as
        tmark's parser never produces it.
        """
        children = host.children if hasattr(host, "children") else host
        return strip_edges(self._reader.lower_inline(children))

    def lower_blocks(self, nodes: Iterable[PageElement]) -> tuple[model.Block, ...]:
        """Lower a run of HTML children into block IR nodes."""
        return self._reader.lower_blocks(nodes)

    # -- diagnostics -------------------------------------------------------

    def warn(self, message: str, *, code: str = READER_UNSUPPORTED) -> Diagnostic:
        """Record a reader diagnostic (never silently drop) and forward it to the emitter.

        HTML input has no source spans: the record names the file and nothing
        more, as ``FileTable`` entries with an empty text render.
        """
        record = Diagnostic(
            code=code,
            severity=default_severity(code),
            span=Span(self.file, 0, 0),
            message=message,
        )
        self.diagnostics.append(record)
        self._emitter.diagnostic(record)
        return record

    # -- document-level registries -----------------------------------------

    def define_footnote(self, label: str, content: tuple[model.Block, ...]) -> None:
        """Register a ``[^label]: …`` definition (the first one for a label wins)."""
        if any(note.label == label for note in self.footnotes):
            return
        self.footnotes.append(model.Footnote(label=label, content=content))

    def define_abbreviation(self, key: str, expansion: str) -> None:
        """Register a ``*[key]: expansion`` definition (the first one for a key wins)."""
        self.abbreviations.setdefault(key, expansion)


def strip_edges(inlines: tuple[model.Inline, ...]) -> tuple[model.Inline, ...]:
    """Drop the leading and trailing whitespace of an inline run.

    Edge ``Str`` nodes are trimmed on their outer side (and dropped when
    nothing remains); an edge ``SoftBreak`` is dropped.
    """
    items = list(inlines)
    while items:
        head = items[0]
        if isinstance(head, model.SoftBreak):
            items.pop(0)
        elif isinstance(head, model.Str):
            text = head.text.lstrip()
            if text:
                if text != head.text:
                    items[0] = model.Str(text)
                break
            items.pop(0)
        else:
            break
    while items:
        tail = items[-1]
        if isinstance(tail, model.SoftBreak):
            items.pop()
        elif isinstance(tail, model.Str):
            text = tail.text.rstrip()
            if text:
                if text != tail.text:
                    items[-1] = model.Str(text)
                break
            items.pop()
        else:
            break
    return tuple(items)


__all__ = [
    "READER_UNPROCESSED_BLOCK",
    "READER_UNSUPPORTED",
    "Diagnostics",
    "ReadContext",
    "strip_edges",
]
