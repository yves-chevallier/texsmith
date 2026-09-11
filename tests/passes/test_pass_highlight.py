"""The ``highlight`` pass: Pygments payloads for the LaTeX backend (decision X3)."""

from __future__ import annotations

from typing import Any

from texsmith.ir import model
from texsmith.ir.walk import walk
from texsmith.passes.highlight import code_engine, highlight_lines


def _redact(structural: Any) -> Any:
    """The structural JSON with the Pygments payloads replaced by a marker.

    The ``\\PY`` text depends on the Pygments release; the golden checks the
    shape and the tests below check the payloads.
    """
    if isinstance(structural, dict):
        if structural.get("type") in ("RawBlock", "RawInline"):
            return {**structural, "text": "<latex>"}
        return {key: _redact(value) for key, value in structural.items()}
    if isinstance(structural, list):
        return [_redact(item) for item in structural]
    return structural


def test_helpers() -> None:
    assert highlight_lines("2-3 5,7") == [2, 3, 5, 7]
    assert highlight_lines(None) == []
    assert highlight_lines("x") == []
    assert code_engine({}) == "pygments"
    assert code_engine({"engine": "Minted"}) == "minted"
    assert code_engine("listings") == "listings"
    assert code_engine({"engine": "unknown"}) == "pygments"


def test_pygments_blocks_and_inline(harness) -> None:
    document = harness.load("highlight", "blocks")
    ctx = harness.context(document, code={"inline": {"breaks": "-."}})
    out = harness.run("highlight", document, ctx)

    assert out is not document and out.ir is not None and document.ir is not None
    listing = out.ir.blocks[1]
    assert isinstance(listing, model.Div) and listing.name == "code"
    assert dict(listing.attrs.kv) == {
        "lang": "py",
        "title": "bubble_sort.py",
        "linenums": "1",
        "hl_lines": "2-3",
        "engine": "pygments",
    }
    (payload,) = listing.content
    assert isinstance(payload, model.RawBlock) and payload.format == "latex"
    assert payload.text.startswith("\\begin{Verbatim}[commandchars=\\\\\\{\\}")
    assert "numbers=left" in payload.text
    assert "breaklines, breakanywhere" in payload.text
    assert "highlightlines={2-3}" in payload.text
    assert "\\PY{k}{def}" in payload.text
    assert payload.text.endswith("\\end{Verbatim}\n")
    # The Div keeps the block's id and span; the payload takes the span and a fresh id.
    source = document.ir.blocks[1]
    assert (listing.id, listing.span) == (source.id, source.span)
    assert payload.span == source.span and payload.id != source.id
    # The listing caption still follows the block.
    assert isinstance(out.ir.blocks[2], model.Caption)

    art = out.ir.blocks[3]
    assert isinstance(art, model.Div)
    assert dict(art.attrs.kv) == {"lang": "text", "stretch": "0.5", "engine": "pygments"}

    inlines = [
        node for node in walk(out.ir.blocks[4]) if isinstance(node, model.RawInline | model.Code)
    ]
    assert [type(node).__name__ for node in inlines] == ["RawInline", "Code", "RawInline"]
    assert inlines[0].text.startswith("{\\ttfamily ") and inlines[0].text.endswith("}")
    assert "\\PYZhy{}\\allowbreak{}" in inlines[0].text
    assert ".\\allowbreak{}" in inlines[0].text
    assert "\n" not in inlines[0].text
    assert inlines[1].text == "x-y"  # no language: left to ``\tscodeinline``

    assert set(ctx.pygments_styles) == {"bw:PY"}
    assert "\\PY@reset" in ctx.pygments_styles["bw:PY"]
    assert _redact(harness.structural(out)) == harness.expected("highlight", "blocks")
    assert len(ctx.diagnostics) == 0


def test_bodies_are_rewritten_with_the_ir(harness) -> None:
    document = harness.load("highlight", "blocks")
    ctx = harness.context(document)
    split = harness.run("slots", document, ctx)
    out = harness.run("highlight", split, ctx)
    assert out.ir is not None
    (body,) = out.bodies
    assert body.blocks == out.ir.blocks
    assert all(a is b for a, b in zip(body.blocks, out.ir.blocks, strict=True))


def test_inline_plain_leaves_code_spans(harness) -> None:
    document = harness.load("highlight", "blocks")
    ctx = harness.context(document, code={"inline": {"plain": True}})
    out = harness.run("highlight", document, ctx)
    assert out.ir is not None
    assert not [node for node in walk(out.ir) if isinstance(node, model.RawInline)]
    assert isinstance(out.ir.blocks[1], model.Div)


def test_minted_highlights_inline_only(harness) -> None:
    document = harness.load("highlight", "blocks")
    ctx = harness.context(document, code={"engine": "minted"})
    out = harness.run("highlight", document, ctx)
    assert out.ir is not None
    assert isinstance(out.ir.blocks[1], model.CodeBlock)
    raws = [node for node in walk(out.ir) if isinstance(node, model.RawInline)]
    assert [node.text for node in raws] == [
        "\\mintinline[breaklines=true]{py}|a-b.c|",
        "\\mintinline[breaklines=true]{c}!z|w!",  # ``|`` is in the text
    ]
    assert ctx.pygments_styles == {}


def test_other_backends_and_engines_are_untouched(harness) -> None:
    document = harness.load("highlight", "blocks")
    assert (
        harness.run("highlight", document, harness.context(document, backend="typst")) is document
    )
    assert harness.run("highlight", document, harness.context(document, backend="html")) is document
    for engine in ("listings", "verbatim"):
        ctx = harness.context(document, code={"engine": engine})
        assert harness.run("highlight", document, ctx) is document


def test_pass_is_identity_without_highlightable_code(harness) -> None:
    # ``var/basic`` has one inline span without a language and no fence.
    document = harness.load("var", "basic")
    assert harness.run("highlight", document) is document
