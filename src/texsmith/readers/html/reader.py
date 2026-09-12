"""The :class:`HtmlReader` — lower a BeautifulSoup tree into the generated IR.

The reader *constructs* a :class:`texsmith.ir.model.Document` from the HTML
Python-Markdown (or a MkDocs page) produced; it never emits a backend string.
Its output is the shape ``tmark.parse`` gives the same constructs
(``specs/migration/python-ir-and-passes.md`` §2): dense node ids from the
reader's own counter, ``NO_SPAN`` everywhere, whitespace kept inside ``Str``
(no ``Space`` node), footnote bodies and abbreviations on the document.

Dispatch model
--------------
Two recursive passes share one registry (:mod:`.registry`):

* :meth:`lower_blocks` collects block-level IR from a run of siblings. Loose
  inline content between block tags is gathered and wrapped in a ``Para``.
* :meth:`lower_inline` collects phrasing IR from a run of siblings, turning
  text nodes into ``Str`` / ``SoftBreak`` / ``Math`` and recursing into
  inline tags.

For each element tag the reader asks the registry for candidate lowerings at
the active level (plus the level-agnostic ones). The first candidate that does
not return :data:`~.registry.NotHandled` wins.

Fallback (no construct is ever dropped silently)
------------------------------------------------
If no lowering claims a tag, the reader emits a ``reader-unsupported``
diagnostic *and* a generic :class:`~texsmith.ir.model.Div` (block level) or
:class:`~texsmith.ir.model.SpanNode` (inline level) that preserves the tag
name and its classes in ``attrs`` and keeps the recursively-lowered children.
Unknown content is therefore always represented and traceable, never lost.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from texsmith.core.diagnostics import DiagnosticEmitter, NullEmitter
from texsmith.ir import model
from texsmith.ir.walk import map_tree

from . import blocks as _blocks, extensions as _extensions, inline as _inline
from ._helpers import classes, make_attrs
from .context import ReadContext, strip_edges
from .registry import NotHandled, ReaderRegistry, ReadLevel


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import PageElement

    from texsmith.diagnostics import Diagnostic


# Literal math payloads Markdown may leave untouched in text nodes (``$…$`` /
# ``\(…\)`` / ``\[…\]`` / math environments): the same constructs tmark's
# parser reads as ``Math``; an environment is kept verbatim as raw LaTeX.
_MATH_PAYLOAD_PATTERN = re.compile(
    r"""
    (?P<display>\$\$.*?\$\$|\\\[.*?\\\])
    |(?P<env>\\begin\{[a-zA-Z*]+\}.*?\\end\{[a-zA-Z*]+\})
    |(?P<inline>\\\(.*?\\\)|(?<!\\)\$(?!\$)(?!\s)(?:\\.|[^$])*?(?<!\\)\$)
    """,
    re.DOTALL | re.VERBOSE,
)

#: A soft line wrap with its continuation indentation.
_SOFT_BREAK = re.compile(r"[ \t]*\n[ \t]*")


# Tags whose presence means "structure": when collecting blocks, hitting one of
# these flushes any pending loose-inline run into a paragraph. Everything else
# encountered at block level that is not a registered block lowering is treated
# as inline and folded into the running paragraph.
_BLOCK_TAGS: frozenset[str] = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "details",
        "div",
        "dl",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "ul",
    }
)

# Inline-natured tags that nonetheless register at ``ReadLevel.ANY`` and may
# appear as a paragraph's sole child (a bare image, a margin note, a display
# math script). They are collected as inline content, not as blocks.
_INLINE_TAGS: frozenset[str] = frozenset({"img", "script", "ts-marginnote"})


def build_reader_registry(extra_modules: Iterable[object] = ()) -> ReaderRegistry:
    """Assemble a registry from the bundled lowering modules plus ``extra_modules``.

    The bundled modules are collected first; any ``extra_modules`` are layered
    on top. Because :meth:`ReaderRegistry.candidates` orders by descending
    priority (stable on registration order), an extra handler declaring a higher
    ``priority`` than a bundled one for the same tag is tried first and may
    return ``NotHandled`` to fall through to the bundled handler. Nothing in the
    tree passes ``extra_modules`` since the template ``readers`` hook went: the
    seam is the reader's own composition point.
    """
    registry = ReaderRegistry()
    for module in (_inline, _blocks, _extensions, *extra_modules):
        registry.collect_from(module)
    return registry


class HtmlReader:
    """Lower HTML (string or parsed tree) into a :class:`texsmith.ir.model.Document`."""

    def __init__(
        self,
        *,
        registry: ReaderRegistry | None = None,
        diagnostics: DiagnosticEmitter | None = None,
        parser: str = "html.parser",
    ) -> None:
        self._registry = registry or build_reader_registry()
        self._parser = parser
        self._emitter = diagnostics or NullEmitter()
        self._context = ReadContext(self, self._emitter)

    # -- public API --------------------------------------------------------

    @property
    def diagnostics(self) -> list[Diagnostic]:
        """The records of every read so far (also forwarded to the emitter as they occur)."""
        return self._context.diagnostics

    def read(self, html: str, *, file: int = 0) -> model.Document:
        """Parse an HTML string and return the document IR (``file`` is its ``FileTable`` id)."""
        soup = BeautifulSoup(html, self._parser)
        return self.read_tree(soup, file=file)

    def read_tree(self, root: Tag, *, file: int = 0) -> model.Document:
        """Lower an already-parsed BeautifulSoup tree into a ``Document``."""
        body = root.find("body")
        container = body if isinstance(body, Tag) else root
        self._context.file = file
        self._context.footnotes = []
        self._context.abbreviations = {}
        blocks = self.lower_blocks(container.children)
        document = model.Document(
            abbreviations=tuple(
                model.AbbrDef(expansion=expansion, key=key)
                for key, expansion in self._context.abbreviations.items()
            ),
            blocks=blocks,
            file=file,
            footnotes=tuple(self._context.footnotes),
        )
        return _number(document)

    # -- recursion entry points (called back from handlers via context) ----

    def lower_blocks(self, children: Iterable[PageElement]) -> tuple[model.Block, ...]:
        """Lower a run of siblings into block IR, wrapping loose inline runs."""
        result: list[model.Block] = []
        pending: list[PageElement] = []

        def flush() -> None:
            if not pending:
                return
            inlines = strip_edges(self._lower_inline_run(pending))
            pending.clear()
            if inlines:
                result.append(model.Para(content=inlines))

        for child in children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                if str(child).strip():
                    pending.append(child)
                continue
            if not isinstance(child, Tag):
                continue
            if self._is_block_element(child):
                flush()
                result.extend(self._lower_block_tag(child))
            else:
                pending.append(child)

        flush()
        return tuple(result)

    def lower_inline(self, children: Iterable[PageElement]) -> tuple[model.Inline, ...]:
        """Lower a run of siblings into inline IR."""
        return self._lower_inline_run(list(children))

    # -- block dispatch ----------------------------------------------------

    def _is_block_element(self, tag: Tag) -> bool:
        name = tag.name or ""
        if name in _INLINE_TAGS:
            return False
        if name in _BLOCK_TAGS:
            return True
        if self._registry.candidates(name, ReadLevel.BLOCK):
            return True
        # Unknown element with no inline lowering either: treat as a block so it
        # surfaces through the block fallback (a Div) rather than being folded
        # silently into a paragraph.
        return not self._registry.candidates(name, ReadLevel.INLINE)

    def _lower_block_tag(self, tag: Tag) -> tuple[model.Block, ...]:
        name = tag.name or ""
        for rule in self._registry.candidates(name, ReadLevel.BLOCK):
            outcome = rule.handler(tag, self._context)
            if outcome is NotHandled:
                continue
            return _as_blocks(outcome)
        return (self._fallback_block(tag),)

    def _fallback_block(self, tag: Tag) -> model.Div:
        self._context.warn(
            f"no block lowering for <{tag.name}> (class={_class_text(tag) or '∅'}); "
            "preserved as a generic Div"
        )
        return model.Div(
            name="div",
            attrs=_fallback_attrs(tag),
            content=self.lower_blocks(tag.children),
        )

    # -- inline dispatch ---------------------------------------------------

    def _lower_inline_run(self, children: list[PageElement]) -> tuple[model.Inline, ...]:
        result: list[model.Inline] = []
        for child in children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                result.extend(text_to_inline(str(child)))
                continue
            if not isinstance(child, Tag):
                continue
            result.extend(self._lower_inline_tag(child))
        return _merge_strs(result)

    def _lower_inline_tag(self, tag: Tag) -> tuple[model.Inline, ...]:
        name = tag.name or ""
        for rule in self._registry.candidates(name, ReadLevel.INLINE):
            outcome = rule.handler(tag, self._context)
            if outcome is NotHandled:
                continue
            return _as_inlines(outcome)
        return (self._fallback_inline(tag),)

    def _fallback_inline(self, tag: Tag) -> model.SpanNode:
        self._context.warn(
            f"no inline lowering for <{tag.name}> (class={_class_text(tag) or '∅'}); "
            "preserved as a generic Span"
        )
        return model.SpanNode(attrs=_fallback_attrs(tag), content=self.lower_inline(tag.children))


# ---------------------------------------------------------------------------
# Free helpers
# ---------------------------------------------------------------------------


def _class_text(tag: Tag) -> str:
    return " ".join(classes(tag.get("class")))


def _fallback_attrs(tag: Tag) -> model.Attrs:
    """Preserve the original tag name and classes on a fallback Div/Span."""
    return make_attrs(classes=classes(tag.get("class")), kv={"html-tag": tag.name or ""})


def text_to_inline(text: str) -> list[model.Inline]:
    """Split a text node into inline IR.

    Literal math payloads Markdown left as plain text become ``Math`` (an
    environment stays a raw LaTeX inline); the prose between them is kept
    verbatim in ``Str`` runs, a soft line wrap (with its continuation
    indentation) becoming a ``SoftBreak`` as in tmark's parser.
    """
    if not text:
        return []
    out: list[model.Inline] = []
    cursor = 0
    for match in _MATH_PAYLOAD_PATTERN.finditer(text):
        if match.start() > cursor:
            out.extend(_prose(text[cursor : match.start()]))
        payload = match.group(0)
        if match.group("env") is not None:
            out.append(model.RawInline(format="latex", text=payload))
        else:
            display = match.group("display") is not None
            width = 1 if payload.startswith("$") and not payload.startswith("$$") else 2
            out.append(model.Math(text=payload[width:-width].strip(), display=display))
        cursor = match.end()
    if cursor < len(text):
        out.extend(_prose(text[cursor:]))
    return out


def _prose(text: str) -> list[model.Inline]:
    out: list[model.Inline] = []
    for index, piece in enumerate(_SOFT_BREAK.split(text)):
        if index:
            out.append(model.SoftBreak())
        if piece:
            out.append(model.Str(piece))
    return out


def _merge_strs(inlines: list[model.Inline]) -> tuple[model.Inline, ...]:
    """Join adjacent ``Str`` nodes (bs4 splits text at entities and stripped tags)."""
    merged: list[model.Inline] = []
    for node in inlines:
        previous = merged[-1] if merged else None
        if isinstance(node, model.Str) and isinstance(previous, model.Str):
            merged[-1] = model.Str(previous.text + node.text)
        else:
            merged.append(node)
    return tuple(merged)


def _number(document: model.Document) -> model.Document:
    """Give every node (and footnote / abbreviation record) a dense id from 1."""
    counter = 0

    def assign(node: model.Node) -> model.Node:
        nonlocal counter
        counter += 1
        return replace(node, id=counter)

    numbered = map_tree(document, assign)
    footnotes = []
    for note in numbered.footnotes:
        counter += 1
        footnotes.append(replace(note, id=counter))
    abbreviations = []
    for abbr in numbered.abbreviations:
        counter += 1
        abbreviations.append(replace(abbr, id=counter))
    return replace(numbered, footnotes=tuple(footnotes), abbreviations=tuple(abbreviations))


def _as_blocks(outcome: object) -> tuple[model.Block, ...]:
    if outcome is None:
        return ()
    if isinstance(outcome, model.Block):
        return (outcome,)
    # An ANY-level lowering invoked at block level may yield an inline node
    # (e.g. a standalone image); wrap it in a Para so the IR stays well-formed.
    if isinstance(outcome, model.Inline):
        return (model.Para(content=(outcome,)),)
    if isinstance(outcome, (list, tuple)):
        blocks: list[model.Block] = []
        for item in outcome:
            if isinstance(item, model.Block):
                blocks.append(item)
            elif isinstance(item, model.Inline):
                blocks.append(model.Para(content=(item,)))
        return tuple(blocks)
    msg = f"block lowering returned a non-block node: {outcome!r}"
    raise TypeError(msg)


def _as_inlines(outcome: object) -> tuple[model.Inline, ...]:
    if outcome is None:
        return ()
    if isinstance(outcome, model.Inline):
        return (outcome,)
    if isinstance(outcome, (list, tuple)):
        return tuple(item for item in outcome if isinstance(item, model.Inline))
    msg = f"inline lowering returned a non-inline node: {outcome!r}"
    raise TypeError(msg)


__all__ = ["HtmlReader", "build_reader_registry", "text_to_inline"]
