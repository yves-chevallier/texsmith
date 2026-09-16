"""The ``epigraph`` pass: the front matter's ``epigraph:`` key as a block quote."""

from __future__ import annotations

from tmark.ir import model

from texsmith.core.documents import TitleStrategy
from texsmith.passes import IdAllocator
from texsmith.passes.epigraph import (
    block,
    epigraph_of,
    insertion_index,
    splice_web,
    web_html,
)


def test_the_epigraph_is_set_under_the_opening_heading(harness) -> None:
    document = harness.load("epigraph", "heading")

    out = harness.run("epigraph", document)

    assert out is not document
    assert out.ir is not None and document.ir is not None
    quote = out.ir.blocks[1]
    assert isinstance(quote, model.BlockQuote)
    assert quote.attrs.classes == ("epigraph",)
    assert quote.attrs.kv == (("source", "Albert Einstein"),)
    assert isinstance(out.ir.blocks[0], model.Header)
    # The input is untouched, and the section further down took none.
    assert len(document.ir.blocks) == len(out.ir.blocks) - 1
    assert harness.structural(out) == harness.expected("epigraph", "heading")


def test_a_document_with_no_opening_heading_takes_it_at_the_top(harness) -> None:
    document = harness.load("epigraph", "top")

    out = harness.run("epigraph", document)

    assert out.ir is not None
    assert isinstance(out.ir.blocks[0], model.BlockQuote)
    assert out.ir.blocks[0].attrs.kv == ()
    assert harness.structural(out) == harness.expected("epigraph", "top")


def test_a_blank_quote_is_not_an_epigraph(harness) -> None:
    document = harness.load("epigraph", "blank")

    assert harness.run("epigraph", document) is document


def test_the_promoted_title_leaves_the_epigraph_at_the_top(harness) -> None:
    """``title`` runs first, so a promoted heading is gone when the rule is read.

    The epigraph then opens the body, under the title the template sets —
    which is where it was under the opening heading the promotion removed.
    """
    document = harness.load("epigraph", "top", title_strategy=TitleStrategy.PROMOTE_METADATA)
    dropped = harness.run("title", document)

    out = harness.run("epigraph", dropped)

    assert out.ir is not None
    assert isinstance(out.ir.blocks[0], model.BlockQuote)


def test_the_nodes_carry_the_front_matter_span_and_fresh_ids(harness) -> None:
    """Span rule 2: the front matter's span, ids above every id of the file."""
    document = harness.load("epigraph", "heading")
    assert document.ir is not None
    span = document.ir.front_matter.span
    ceiling = max(node.id for node in (*document.ir.blocks,))

    out = harness.run("epigraph", document)

    assert out.ir is not None
    quote = out.ir.blocks[1]
    assert isinstance(quote, model.BlockQuote)
    para = quote.content[0]
    assert isinstance(para, model.Para)
    assert quote.span == para.span == para.content[0].span == span
    assert min(quote.id, para.id, para.content[0].id) > ceiling


def test_the_placement_rule_reads_the_first_block_only() -> None:
    assert insertion_index("Header") == 1
    assert insertion_index("Para") == 0
    assert insertion_index(None) == 0


def test_a_blank_source_is_no_source() -> None:
    assert epigraph_of({"quote": " Q ", "source": "  "}) == model.Epigraph(quote="Q", source=None)
    assert epigraph_of({"quote": "Q", "source": " S "}) == model.Epigraph(quote="Q", source="S")
    assert epigraph_of(model.Epigraph(quote="Q", source="S")).source == "S"
    assert epigraph_of(None) is None
    assert epigraph_of({"quote": ""}) is None


def test_the_built_quote_holds_the_two_plain_strings() -> None:
    ids = IdAllocator(10)
    span = model.Span(file=3, start=0, end=12)
    quote = block(model.Epigraph(quote="Q", source="S"), span=span, ids=ids)

    assert quote.attrs.classes == ("epigraph",)
    assert quote.attrs.kv == (("source", "S"),)
    para = quote.content[0]
    assert isinstance(para, model.Para)
    assert para.content == (model.Str(id=10, span=span, text="Q"),)


def test_the_web_shape_escapes_its_two_values() -> None:
    html = web_html(model.Epigraph(quote='a < b & "c"', source="R & D"))

    assert html == (
        '<blockquote class="ts-epigraph">a &lt; b &amp; &quot;c&quot;'
        "<footer>R &amp; D</footer></blockquote>"
    )
    assert web_html(model.Epigraph(quote="Q")) == '<blockquote class="ts-epigraph">Q</blockquote>'


def test_the_web_text_is_spliced_after_the_heading_line() -> None:
    epigraph = model.Epigraph(quote="Q")
    html = web_html(epigraph)

    assert splice_web("# T\n\nBody.\n", epigraph, 1) == f"# T\n\n{html}\n\nBody.\n"
    assert splice_web("Body.\n", epigraph, 0) == f"{html}\n\nBody.\n"
    # The padding a caller left to keep the file's line numbers stays in front.
    assert splice_web("\n\n\nBody.\n", epigraph, 0) == f"\n\n\n{html}\n\nBody.\n"
    assert splice_web("\n\n# T\n\nBody.\n", epigraph, 1) == f"\n\n# T\n\n{html}\n\nBody.\n"
    # A heading with nothing under it.
    assert splice_web("# T", epigraph, 1) == f"# T\n\n{html}"
