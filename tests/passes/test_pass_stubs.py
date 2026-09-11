"""The passes not implemented yet are registered no-ops."""

from __future__ import annotations

import pytest

from texsmith.passes import REGISTRY, build_pipeline


STUBS = ("assets", "emoji", "scripts")


@pytest.mark.parametrize("name", STUBS)
def test_stub_returns_its_input(harness, name: str) -> None:
    document = harness.load("stubs", "plain")
    ctx = harness.context(document)
    assert harness.run(name, document, ctx) is document
    assert len(ctx.diagnostics) == 0


def test_stubs_are_registered_with_io() -> None:
    build_pipeline()
    for name in STUBS:
        assert REGISTRY[name].needs_io is True
        assert REGISTRY[name].stage == "pre"


def test_implemented_passes_keep_their_documented_positions() -> None:
    order = [item.name for item in build_pipeline()]
    assert order[0] == "include"
    assert order.index("include") < order.index("snippet") < order.index("assets")
    assert order.index("doi") < order.index("slots")
    assert order[-1] == "highlight"
    assert REGISTRY["include"].stage == "pre" and REGISTRY["include"].needs_io
    assert REGISTRY["snippet"].stage == "pre" and REGISTRY["snippet"].needs_io
    assert REGISTRY["doi"].stage == "pre" and REGISTRY["doi"].needs_io
    assert REGISTRY["highlight"].stage == "post" and not REGISTRY["highlight"].needs_io
