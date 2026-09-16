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
— and at the top of the document when it opens with something else.
"Opening" is the *first* top-level block, so a heading further down the page
is a section of its own and takes no epigraph.

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

from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from tmark.ir import model

from texsmith.diagnostics import Span
from texsmith.passes import IdAllocator, PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = [
    "EPIGRAPH_CLASS",
    "WEB_CLASS",
    "block",
    "epigraph_of",
    "insertion_index",
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


def insertion_index(first_block_type: str | None) -> int:
    """Where the epigraph goes: ``1`` under an opening heading, ``0`` at the top.

    ``first_block_type`` is the ``type`` of the document's first top-level
    block — ``None`` for a document with no blocks at all.
    """
    return 1 if first_block_type == "Header" else 0


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

    ``1`` puts it after the line the opening heading occupies, ``0`` after
    the blank lines the text opens with — a caller that padded the body to
    keep the file's line numbers reads its padding back where it left it.
    """
    at = len(text) - len(text.lstrip("\r\n"))
    html = web_html(epigraph)
    if index:
        newline = text.find("\n", at)
        at = len(text) if newline < 0 else newline
        return f"{text[:at]}\n\n{html}{text[at:]}"
    return f"{text[:at]}{html}\n\n{text[at:]}"


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
    at = insertion_index(ir.blocks[0].type if ir.blocks else None)
    quote = block(epigraph, span=ir.front_matter.span, ids=ctx.ids)
    blocks = (*ir.blocks[:at], quote, *ir.blocks[at:])
    return document.evolve(ir=replace(ir, blocks=blocks))
