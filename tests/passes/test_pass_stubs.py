"""The passes not implemented in this wave are registered no-ops."""

from __future__ import annotations

import pytest

from texsmith.passes import REGISTRY, build_pipeline


STUBS = ("include", "snippet", "doi", "highlight")


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
    assert REGISTRY["highlight"].stage == "post"
    assert all(REGISTRY[name].stage == "pre" for name in STUBS if name != "highlight")
