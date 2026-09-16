r"""The ``epigraph`` pass: the front matter's ``epigraph:`` key as a block quote.

``epigraph: {quote, source}`` is TMark's own typed metadata key (spec
§BlockQuote), and no writer reads it: the key is *data*, and the construct
it stands for is the ``> {.epigraph}`` block quote every backend already
emits. So TeXSmith builds that quote from the key and inserts it in the
block list, and each writer keeps the one emitter it has —
``\tsepigraph[source={…}]{…}`` for LaTeX, ``#ts-epigraph(source: […])[…]``
for Typst, ``<blockquote class="epigraph">`` with the source in a
``<footer>`` for HTML.

**Where it goes** is :func:`insertion_index`, the one statement of the rule:
under the document's opening heading — between that heading and its content
— and at the top of the document when it opens with something else. The
opening heading is the first block that *renders something*: a page may open
with an anchor paragraph (``[]{#id}`` spans, whitespace), an HTML comment or
a stray ``table-config`` fence, and none of those is what the reader sees
first, so the rule reads past them and the epigraph lands under the heading
they precede, after them. A heading further down the page, under something
the page does print, is a section of its own and takes no epigraph.

The rule is read twice, because the web reads text where the pass reads
nodes. ``tmark.lower_web`` splices a page's source bytes, and a node a pass
invented has no bytes to splice, so :meth:`texsmith.site.index.SiteIndex.lower`
inserts the lowered shape into the lowered *text* instead
(:func:`web_html`, :func:`splice_web`) — at the position the same
:func:`insertion_index` returns, read off the page's raw parse rather than
off a decoded document.

``quote`` and ``source`` are plain text, not Markdown. The three nodes carry
the front matter's span — that island is where the text comes from, so a
diagnostic naming the epigraph points the author at the key they wrote — and
fresh ids (span rule 2).

The pass runs after ``title``: when title promotion or ``--strip-heading``
removed the opening heading, the epigraph opens the body, under the title
the template sets.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
import re
from typing import TYPE_CHECKING, Any

from tmark.ir import model

from texsmith.diagnostics import Span
from texsmith.passes import IdAllocator, PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = [
    "BLANK_BLOCKS",
    "BLANK_INLINES",
    "EPIGRAPH_CLASS",
    "TEXT_BLOCKS",
    "WEB_CLASS",
    "block",
    "epigraph_of",
    "insertion_index",
    "prints_nothing",
    "run",
    "splice_web",
    "web_html",
]

#: The class a ``> {.epigraph}`` quote carries, and the one the built node takes.
EPIGRAPH_CLASS = "epigraph"
#: The same class once the web lowering has prefixed it.
WEB_CLASS = "ts-epigraph"


def epigraph_of(value: model.Epigraph | Mapping[str, Any] | None) -> model.Epigraph | None:
    """The epigraph to set, trimmed, or ``None`` when there is none to set.

    ``value`` is the typed ``epigraph`` key (:class:`tmark.ir.model.Keys`)
    or the mapping it was decoded from — the site lowering reads a page's
    front matter and never decodes the page itself. An absent key, a blank
    ``quote`` and a blank ``source`` are all "none".
    """
    if value is None:
        return None
    if isinstance(value, Mapping):
        quote = str(value.get("quote") or "")
        source = str(value.get("source") or "")
    else:
        quote = value.quote or ""
        source = value.source or ""
    quote, source = quote.strip(), source.strip()
    if not quote:
        return None
    return model.Epigraph(quote=quote, source=source or None)


#: Blocks that stand in the list and print nothing: an HTML comment (spec
#: §Comment, "zero width in the flow") and a ``table-config`` fence, which a
#: pass attaches to the table before it and which the web lowering drops.
BLANK_BLOCKS = frozenset({"Comment", "TableConfig"})
#: Blocks whose inlines decide whether they print: a paragraph of anchors
#: prints nothing, a paragraph of prose prints.
TEXT_BLOCKS = frozenset({"Para", "Plain"})
#: Inlines that print nothing wherever they sit.
BLANK_INLINES = frozenset({"Space", "SoftBreak", "Comment"})


def prints_nothing(node: model.Block | Mapping[str, Any]) -> bool:
    """Whether a top-level block puts nothing on the page.

    An anchor paragraph — ``[]{#id}`` spans, whitespace, comments, in any
    number — is the shape a page uses to name a target before its title;
    :data:`BLANK_BLOCKS` is the rest. ``node`` is a decoded block (the pass)
    or the raw parse's mapping (the site lowering), read through the same
    two field names either way.
    """
    kind = _type(node)
    if kind in BLANK_BLOCKS:
        return True
    if kind not in TEXT_BLOCKS:
        return False
    return all(_inline_prints_nothing(inline) for inline in _field(node, "content", ()))


def insertion_index(blocks: Sequence[model.Block | Mapping[str, Any]]) -> int:
    """Where the epigraph goes: under the opening heading, else at the top.

    The opening heading is the first block that *renders something*
    (:func:`prints_nothing`), and "under" it is the index just after it, so
    the anchors a page opens with keep the position their author gave them.
    A page that opens with anything else — and a page that prints nothing at
    all — takes the epigraph at index ``0``, the very top.
    """
    for at, node in enumerate(blocks):
        if prints_nothing(node):
            continue
        return at + 1 if _type(node) == "Header" else 0
    return 0


def _inline_prints_nothing(node: model.Inline | Mapping[str, Any]) -> bool:
    """Whether an inline puts nothing on the page (:func:`prints_nothing`)."""
    kind = _type(node)
    if kind in BLANK_INLINES:
        return True
    if kind == "Str":
        return not str(_field(node, "text", "")).strip()
    if kind == "Span":
        return all(_inline_prints_nothing(inline) for inline in _field(node, "content", ()))
    return False


def _type(node: model.Node | Mapping[str, Any]) -> str:
    """The node's ``type`` tag, from a mapping or from a decoded node."""
    return str(node["type"] if isinstance(node, Mapping) else getattr(node, "type", ""))


def _field(node: model.Node | Mapping[str, Any], name: str, default: Any) -> Any:
    """A node's field, from a mapping or from a decoded node."""
    value = node.get(name) if isinstance(node, Mapping) else getattr(node, name, None)
    return default if value is None else value


def block(epigraph: model.Epigraph, *, span: Span, ids: IdAllocator) -> model.BlockQuote:
    """The epigraph as the block quote every writer already renders."""
    attrs = model.Attrs(
        classes=(EPIGRAPH_CLASS,),
        kv=(("source", epigraph.source),) if epigraph.source else (),
    )
    quote = model.Str(id=ids.next(), span=span, text=epigraph.quote)
    return model.BlockQuote(
        id=ids.next(),
        span=span,
        attrs=attrs,
        content=(model.Para(id=ids.next(), span=span, content=(quote,)),),
    )


def web_html(epigraph: model.Epigraph) -> str:
    """``<blockquote class="ts-epigraph">`` for the lowered page (spec §BlockQuote).

    The two values are plain text, so the wrapper carries no ``markdown``
    attribute and the Markdown renderer leaves its content alone.
    """
    out = f'<blockquote class="{WEB_CLASS}">{_escape(epigraph.quote)}'
    if epigraph.source:
        out += f"<footer>{_escape(epigraph.source)}</footer>"
    return out + "</blockquote>"


def splice_web(text: str, epigraph: model.Epigraph, index: int) -> str:
    """``text`` with :func:`web_html` inserted at ``index`` (:func:`insertion_index`).

    ``0`` puts it after the blank lines the text opens with — a caller that
    padded the body to keep the file's line numbers reads its padding back
    where it left it. Any other index puts it under the opening heading,
    which the lowered text names where :func:`insertion_index` said it
    would: past whatever prints nothing, which the lowering writes as blank
    lines, HTML comments and anchors (``[](){#id}``).
    """
    html = web_html(epigraph)
    if not index:
        at = len(text) - len(text.lstrip("\r\n"))
        return f"{text[:at]}{html}\n\n{text[at:]}"
    end = _heading_end(text, _first_printed(text))
    return f"{text[:end]}\n\n{html}{text[end:]}"


#: An anchor as the web lowering writes it: ``[](){#id}``, with whatever
#: classes and pairs the author gave it.
_WEB_ANCHOR = re.compile(r"\[\]\(\)\{[^{}\n]*\}")
#: An HTML comment, which the lowering copies through as the author wrote it.
_WEB_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
#: The blank lines a dropped block leaves behind, and the blanks between blocks.
_WEB_BLANK = re.compile(r"\s+")


def _first_printed(text: str) -> int:
    """The offset of the first thing the lowered page prints.

    The counterpart of :func:`prints_nothing` in text: the blocks the rule
    reads past reach the web as blank lines, comments and anchors, and the
    heading the epigraph goes under is what follows them.
    """
    at = 0
    while at < len(text):
        for pattern in (_WEB_BLANK, _WEB_ANCHOR, _WEB_COMMENT):
            match = pattern.match(text, at)
            if match is not None and match.end() > at:
                at = match.end()
                break
        else:
            return at
    return at


#: The second line of a setext heading: the ``===`` under its title, indented
#: by at most three spaces. A ``---`` under an **ATX** heading is a thematic
#: rule of its own, which is why the first line decides.
_SETEXT_UNDERLINE = re.compile(r"[ \t]{0,3}(?:=+|-+)[ \t]*")


def _heading_end(text: str, at: int) -> int:
    """The offset just past the opening heading that starts at ``at``.

    A heading is one line when it is written with hashes and two when it is
    written with an underline: splicing between the title and its ``===``
    would leave the page a paragraph followed by a row of equals signs.
    """
    end = text.find("\n", at)
    if end < 0:
        return len(text)
    if text[at:end].lstrip().startswith("#"):
        return end
    underline = text.find("\n", end + 1)
    line = text[end + 1 :] if underline < 0 else text[end + 1 : underline]
    if not _SETEXT_UNDERLINE.fullmatch(line):
        return end
    return len(text) if underline < 0 else underline


def _escape(value: str) -> str:
    """HTML text escaping as the lowering does it: ``&``, ``<``, ``>`` and ``"``."""
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


@spec("epigraph", after=("title",))
def run(document: Document, ctx: PassContext) -> Document:
    ir = document.ir
    if ir is None:
        return document
    epigraph = epigraph_of(ir.front_matter.keys.epigraph)
    if epigraph is None:
        return document
    at = insertion_index(ir.blocks)
    quote = block(epigraph, span=ir.front_matter.span, ids=ctx.ids)
    blocks = (*ir.blocks[:at], quote, *ir.blocks[at:])
    return document.evolve(ir=replace(ir, blocks=blocks))
