"""The ``slots`` pass: sections into template slots (decision X11)."""

from __future__ import annotations

from typing import Any

from texsmith.core.conversion.inputs import SlotOptions
from texsmith.ir import codec, model
from texsmith.ir.walk import plain_text
from texsmith.passes import SlotTemplate


def _bodies_json(document) -> list[dict[str, Any]]:
    return [
        {
            "name": body.name,
            "position": body.position,
            "heading_levels": list(body.heading_levels),
            "whole_document": body.whole_document,
            "blocks": [codec.structural(block) for block in body.blocks],
        }
        for body in document.bodies
    ]


def _titles(blocks: tuple[model.Block, ...]) -> list[str]:
    return [plain_text(b.content) for b in blocks if isinstance(b, model.Header)]


def test_sections_are_claimed_by_id_then_text(harness) -> None:
    document = harness.load("slots", "sections")
    assert document.slot_requests == {"abstract": "Abstract", "appendix": "#appendix"}
    template = SlotTemplate(requests=document.slot_requests, strip_heading=frozenset({"abstract"}))
    ctx = harness.context(document, template=template)
    out = harness.run("slots", document, ctx)

    bodies = {body.name: body for body in out.bodies}
    assert [body.name for body in out.bodies] == ["abstract", "appendix", "mainmatter"]
    assert _titles(bodies["abstract"].blocks) == []  # strip_heading
    assert len(bodies["abstract"].blocks) == 1
    assert _titles(bodies["appendix"].blocks) == ["Appendix", "Listings"]
    assert bodies["appendix"].heading_levels == (1, 2)
    assert _titles(bodies["mainmatter"].blocks) == ["Introduction", "Detail", "Closing"]
    assert bodies["mainmatter"].heading_levels == (1, 2, 1)
    assert len(ctx.diagnostics) == 0

    # Block sub-slices keep their ids: the appendix header is the original node.
    assert document.ir is not None
    original = next(
        b for b in document.ir.blocks if isinstance(b, model.Header) and b.attrs.id == "appendix"
    )
    assert bodies["appendix"].blocks[0].id == original.id
    assert document.bodies == ()
    assert _bodies_json(out) == harness.expected("slots", "sections")["bodies"]


def test_flatten_option_drops_the_header(harness) -> None:
    document = harness.load(
        "slots", "sections", slot_options={"appendix": SlotOptions(flatten=True)}
    )
    template = SlotTemplate(requests=document.slot_requests)
    out = harness.run("slots", document, template=template)
    bodies = {body.name: body for body in out.bodies}
    assert _titles(bodies["appendix"].blocks) == ["Listings"]
    assert _titles(bodies["abstract"].blocks) == ["Abstract"]


def test_unsupported_nested_and_missing_selectors_are_reported(harness) -> None:
    document = harness.load("slots", "problems")
    requests = {
        "abstract": "Inside a container",
        "appendix": "#nowhere",
        "cover": ".hero",
    }
    ctx = harness.context(document, template=SlotTemplate(requests=requests))
    out = harness.run("slots", document, ctx)

    assert [body.name for body in out.bodies] == ["mainmatter"]
    assert document.ir is not None
    assert out.bodies[0].blocks == document.ir.blocks
    assert [record.code for record in ctx.diagnostics] == [
        "slot-selector-unsupported",
        "slot-nested-heading",
        "slot-missing",
    ]
    nested = next(record for record in ctx.diagnostics if record.code == "slot-nested-heading")
    nested_header = next(
        node
        for block in document.ir.blocks
        if isinstance(block, model.Admonition)
        for node in block.content
        if isinstance(node, model.Header)
    )
    assert nested.span.start == nested_header.span.start
    assert harness.diagnostics(ctx) == harness.expected_diagnostics("slots", "problems")


def test_wildcard_takes_the_whole_document(harness) -> None:
    document = harness.load("slots", "wildcard")
    requests = {"cover": "@document", "extra": "*"}
    out = harness.run("slots", document, template=SlotTemplate(requests=requests))
    names = [body.name for body in out.bodies]
    assert names == ["cover", "extra", "mainmatter"]
    assert document.ir is not None
    assert out.bodies[0].blocks == document.ir.blocks
    assert out.bodies[0].whole_document is True
    assert out.bodies[1].blocks == document.ir.blocks
    assert out.bodies[2].blocks == ()
    assert _bodies_json(out) == harness.expected("slots", "wildcard")["bodies"]


def test_without_ir_the_pass_is_identity(harness) -> None:
    document = harness.load("slots", "wildcard")
    plain = document.evolve(ir=None)
    assert harness.run("slots", plain) is plain
