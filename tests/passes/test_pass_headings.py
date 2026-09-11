"""The ``headings`` pass: per-body ``base_level`` and ``numbered`` (decision X1)."""

from __future__ import annotations

import json

from texsmith.ir import model
from texsmith.passes import SlotTemplate
from texsmith.passes.headings import body_offset


def _template(document) -> SlotTemplate:
    return SlotTemplate(
        requests=document.slot_requests,
        levels={"mainmatter": 1, "abstract": 1, "preface": 1},
        strip_heading=frozenset({"abstract"}),
        base_level=1,
    )


def test_body_offset() -> None:
    assert body_offset(()) == 0
    assert body_offset((1, 2)) == 0
    assert body_offset((2, 3)) == -1
    assert body_offset((3,)) == -2


def test_offsets_per_body(harness) -> None:
    document = harness.load("headings", "offsets")
    ctx = harness.context(document, template=_template(document))
    split = harness.run("slots", document, ctx)
    out = harness.run("headings", split, ctx)

    bodies = {body.name: body for body in out.bodies}
    # ``## Starts deep`` becomes the top level of its body: 1 + 0 + (1 - 2).
    assert bodies["mainmatter"].heading_levels == (2, 3)
    assert bodies["mainmatter"].base_level == 0
    assert bodies["mainmatter"].numbered is True
    # No heading left after strip_heading: offset 0.
    assert bodies["abstract"].heading_levels == ()
    assert bodies["abstract"].base_level == 1
    # The preface is never numbered.
    assert bodies["preface"].heading_levels == (1,)
    assert bodies["preface"].base_level == 1
    assert bodies["preface"].numbered is False

    # Header.level stays the author's (X1).
    assert document.ir is not None and out.ir is not None
    assert [b.level for b in out.ir.blocks if isinstance(b, model.Header)] == [
        b.level for b in document.ir.blocks if isinstance(b, model.Header)
    ]
    # The slots pass output is not mutated.
    assert all(body.base_level == 1 for body in split.bodies)

    summary = {
        name: {"base_level": body.base_level, "numbered": body.numbered}
        for name, body in bodies.items()
    }
    assert summary == harness.expected("headings", "offsets")


def test_document_base_level_and_numbered_flag(harness) -> None:
    document = harness.load("headings", "offsets", base_level=1, numbered=False)
    ctx = harness.context(document, template=_template(document))
    out = harness.run("headings", harness.run("slots", document, ctx), ctx)
    bodies = {body.name: body for body in out.bodies}
    assert bodies["mainmatter"].base_level == 1
    assert bodies["abstract"].base_level == 2
    assert all(body.numbered is False for body in out.bodies)


def test_slot_without_template_level_uses_the_fallback(harness) -> None:
    document = harness.load("headings", "offsets")
    template = SlotTemplate(requests=document.slot_requests, levels={}, base_level=0)
    ctx = harness.context(document, template=template)
    out = harness.run("headings", harness.run("slots", document, ctx), ctx)
    bodies = {body.name: body for body in out.bodies}
    assert bodies["preface"].base_level == 0
    assert bodies["mainmatter"].base_level == -1


def test_without_bodies_the_pass_is_identity(harness) -> None:
    document = harness.load("headings", "offsets")
    assert harness.run("headings", document) is document
    json.dumps(harness.structural(document))  # the IR stays serialisable
