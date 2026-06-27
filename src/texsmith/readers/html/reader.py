"""The :class:`HtmlReader` — lower a BeautifulSoup tree into IR.

The reader is the inverse of the old mutate-and-flatten pipeline: instead of
rewriting the DOM into LaTeX strings and calling ``soup.get_text()``, it
*constructs* a :class:`texsmith.ir.Document`. It never emits a backend string.

Dispatch model
--------------
Two recursive passes share one registry (:mod:`.registry`):

* :meth:`lower_blocks` collects block-level IR from a run of siblings. Loose
  inline content between block tags is gathered and wrapped in a ``Para``.
* :meth:`lower_inline` collects phrasing IR from a run of siblings, turning
  text nodes into ``Str`` / ``Space`` and recursing into inline tags.

For each element tag the reader asks the registry for candidate lowerings at
the active level (plus the level-agnostic ones). The first candidate that does
not return :data:`~.registry.NotHandled` wins.

Fallback (no construct is ever dropped silently)
------------------------------------------------
If no lowering claims a tag, the reader emits a diagnostic warning *and* a
generic :class:`~texsmith.ir.Div` (block level) or :class:`~texsmith.ir.Span`
(inline level) that preserves the tag name and its classes in ``attrs`` and
keeps the recursively-lowered children. Unknown content is therefore always
represented and traceable, never lost.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from texsmith.core.diagnostics import DiagnosticEmitter, NullEmitter
from texsmith.ir import nodes as ir

from . import blocks as _blocks, extensions as _extensions, inline as _inline
from .context import ReadContext
from .registry import NotHandled, ReaderRegistry, ReadLevel


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import PageElement


# Literal inline-math payloads Markdown may leave untouched in text nodes
# (``$…$`` / ``\(…\)`` / ``\[…\]`` / math environments). Kept verbatim so the
# writer does not escape them — the legacy ``escape_plain_text`` did the same.
_MATH_PAYLOAD_PATTERN = re.compile(
    r"""
    (?:\$\$.*?\$\$)
    |(?:\\\[.*?\\\])
    |(?:\\\(.*?\\\))
    |(?:\\begin\{[a-zA-Z*]+\}.*?\\end\{[a-zA-Z*]+\})
    |(?<!\\)\$(?!\$)(?!\s)(?:\\.|[^$])*?(?<!\\)\$
    """,
    re.DOTALL | re.VERBOSE,
)


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


def _build_registry() -> ReaderRegistry:
    """Assemble the default registry from the lowering modules."""
    registry = ReaderRegistry()
    for module in (_inline, _blocks, _extensions):
        registry.collect_from(module)
    return registry


class HtmlReader:
    """Lower HTML (string or parsed tree) into a :class:`texsmith.ir.Document`."""

    def __init__(
        self,
        *,
        registry: ReaderRegistry | None = None,
        diagnostics: DiagnosticEmitter | None = None,
        parser: str = "html.parser",
    ) -> None:
        self._registry = registry or _build_registry()
        self._parser = parser
        self._context = ReadContext(self, diagnostics or NullEmitter())

    # -- public API --------------------------------------------------------

    def read(self, html: str) -> ir.Document:
        """Parse an HTML string and return the document IR."""
        soup = BeautifulSoup(html, self._parser)
        return self.read_tree(soup)

    def read_tree(self, root: Tag) -> ir.Document:
        """Lower an already-parsed BeautifulSoup tree into a ``Document``."""
        body = root.find("body")
        container = body if isinstance(body, Tag) else root
        return ir.Document(content=self.lower_blocks(container.children))

    # -- recursion entry points (called back from handlers via context) ----

    def lower_blocks(self, children: Iterable[PageElement]) -> tuple[ir.Block, ...]:
        """Lower a run of siblings into block IR, wrapping loose inline runs."""
        result: list[ir.Block] = []
        pending: list[PageElement] = []

        def flush() -> None:
            if not pending:
                return
            inlines = self._lower_inline_run(pending)
            pending.clear()
            inlines = _strip_edges(inlines)
            if inlines:
                result.append(ir.Para(content=inlines))

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

    def lower_inline(self, children: Iterable[PageElement]) -> tuple[ir.Inline, ...]:
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

    def _lower_block_tag(self, tag: Tag) -> tuple[ir.Block, ...]:
        name = tag.name or ""
        for rule in self._registry.candidates(name, ReadLevel.BLOCK):
            outcome = rule.handler(tag, self._context)
            if outcome is NotHandled:
                continue
            return _as_blocks(outcome)
        return (self._fallback_block(tag),)

    def _fallback_block(self, tag: Tag) -> ir.Div:
        self._context.warn(
            f"HtmlReader: no block lowering for <{tag.name}> "
            f"(class={_classes(tag) or '∅'}); preserved as a generic Div."
        )
        return ir.Div(
            content=self.lower_blocks(tag.children),
            attrs=_fallback_attrs(tag),
        )

    # -- inline dispatch ---------------------------------------------------

    def _lower_inline_run(self, children: list[PageElement]) -> tuple[ir.Inline, ...]:
        result: list[ir.Inline] = []
        for child in children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                result.extend(_text_to_inline(str(child)))
                continue
            if not isinstance(child, Tag):
                continue
            result.extend(self._lower_inline_tag(child))
        return tuple(result)

    def _lower_inline_tag(self, tag: Tag) -> tuple[ir.Inline, ...]:
        name = tag.name or ""
        for rule in self._registry.candidates(name, ReadLevel.INLINE):
            outcome = rule.handler(tag, self._context)
            if outcome is NotHandled:
                continue
            return _as_inlines(outcome)
        return (self._fallback_inline(tag),)

    def _fallback_inline(self, tag: Tag) -> ir.Span:
        self._context.warn(
            f"HtmlReader: no inline lowering for <{tag.name}> "
            f"(class={_classes(tag) or '∅'}); preserved as a generic Span."
        )
        return ir.Span(
            content=self.lower_inline(tag.children),
            attrs=_fallback_attrs(tag),
        )


# ---------------------------------------------------------------------------
# Free helpers
# ---------------------------------------------------------------------------


def _classes(tag: Tag) -> str:
    raw = tag.get("class")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (list, tuple)):
        return " ".join(str(item) for item in raw)
    return ""


def _fallback_attrs(tag: Tag) -> tuple[tuple[str, str], ...]:
    """Preserve the original tag name and class on a fallback Div/Span."""
    attrs: list[tuple[str, str]] = [("html-tag", tag.name or "")]
    classes = _classes(tag)
    if classes:
        attrs.append(("class", classes))
    return tuple(attrs)


def _text_to_inline(text: str) -> list[ir.Inline]:
    """Split a text node into inline IR.

    Literal math payloads (``$…$`` / ``\\(…\\)`` / ``\\[…\\]`` / math envs that
    Markdown left as plain text) are kept verbatim as ``RawInline`` so the
    writer does not escape them — mirroring the legacy ``escape_plain_text``
    PRE phase, which protected math before escaping. The prose between math
    payloads is tokenised into ``Str`` runs / ``Space`` separators.
    """
    if not text:
        return []
    matches = list(_MATH_PAYLOAD_PATTERN.finditer(text))
    if not matches:
        return _tokenize_prose(text)
    out: list[ir.Inline] = []
    cursor = 0
    for match in matches:
        if match.start() > cursor:
            out.extend(_tokenize_prose(text[cursor : match.start()]))
        out.append(ir.RawInline(format="latex", text=match.group(0)))
        cursor = match.end()
    if cursor < len(text):
        out.extend(_tokenize_prose(text[cursor:]))
    return out


def _tokenize_prose(text: str) -> list[ir.Inline]:
    """Tokenise prose into ``Str`` runs and ``Space`` / soft-wrap separators."""
    if not text:
        return []
    out: list[ir.Inline] = []
    run: list[str] = []
    ws: list[str] = []

    def flush_ws() -> None:
        if not ws:
            return
        # Preserve the distinction the legacy ``soup.get_text()`` kept: a
        # whitespace run that contains a newline (Markdown's soft line wrap,
        # possibly with continuation indentation) is kept verbatim as a
        # ``SoftBreak`` carrying the literal whitespace; inter-word spacing
        # collapses to a single ``Space`` (rendered as ``" "``).
        run = "".join(ws)
        # The legacy ``get_text()`` preserved source whitespace verbatim. A run
        # containing a newline (soft line wrap + any continuation indentation)
        # or a run of more than one space is kept literally in a ``Str`` (the
        # writer leaves whitespace unescaped); a single inter-word space
        # collapses to a ``Space``. Paragraph edge-stripping treats a
        # whitespace-only ``Str`` like a ``Space``.
        if "\n" in run or len(run) > 1:
            out.append(ir.Str(run))
        elif not out or not isinstance(out[-1], (ir.Space, ir.SoftBreak)):
            out.append(ir.Space())
        ws.clear()

    for char in text:
        if char.isspace():
            if run:
                out.append(ir.Str("".join(run)))
                run.clear()
            ws.append(char)
        else:
            flush_ws()
            run.append(char)
    if run:
        out.append(ir.Str("".join(run)))
    flush_ws()
    return out


def _strip_edges(inlines: tuple[ir.Inline, ...]) -> tuple[ir.Inline, ...]:
    """Drop leading/trailing ``Space`` from a paragraph's inline content."""
    start = 0
    end = len(inlines)
    while start < end and _is_edge_space(inlines[start]):
        start += 1
    while end > start and _is_edge_space(inlines[end - 1]):
        end -= 1
    return inlines[start:end]


def _is_edge_space(node: ir.Inline) -> bool:
    """Whether an inline is trimmable paragraph-edge whitespace."""
    if isinstance(node, (ir.Space, ir.SoftBreak)):
        return True
    return isinstance(node, ir.Str) and not node.text.strip()


def _as_blocks(outcome: object) -> tuple[ir.Block, ...]:
    if outcome is None:
        return ()
    if isinstance(outcome, ir.Block):
        return (outcome,)
    # An ANY-level lowering invoked at block level may yield an inline node
    # (e.g. a standalone image); wrap it in a Plain so the IR stays well-formed.
    if isinstance(outcome, ir.Inline):
        return (ir.Plain(content=(outcome,)),)
    if isinstance(outcome, (list, tuple)):
        blocks: list[ir.Block] = []
        for item in outcome:
            if isinstance(item, ir.Block):
                blocks.append(item)
            elif isinstance(item, ir.Inline):
                blocks.append(ir.Plain(content=(item,)))
        return tuple(blocks)
    msg = f"block lowering returned a non-block node: {outcome!r}"
    raise TypeError(msg)


def _as_inlines(outcome: object) -> tuple[ir.Inline, ...]:
    if outcome is None:
        return ()
    if isinstance(outcome, ir.Inline):
        return (outcome,)
    if isinstance(outcome, (list, tuple)):
        return tuple(item for item in outcome if isinstance(item, ir.Inline))
    msg = f"inline lowering returned a non-inline node: {outcome!r}"
    raise TypeError(msg)


__all__ = ["HtmlReader"]
