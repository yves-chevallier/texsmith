"""Every bundled pass is implemented; the pipeline keeps the documented order."""

from __future__ import annotations

from texsmith.passes import DEFAULT_PIPELINE, REGISTRY, build_pipeline


def test_every_listed_pass_is_registered() -> None:
    build_pipeline()
    assert set(DEFAULT_PIPELINE) <= set(REGISTRY)


def test_implemented_passes_keep_their_documented_positions() -> None:
    order = [item.name for item in build_pipeline()]
    assert order[0] == "include"
    assert order.index("include") < order.index("snippet") < order.index("assets")
    assert order.index("emoji") < order.index("scripts")
    assert order.index("doi") < order.index("slots")
    assert order[-1] == "highlight"
    for name in ("include", "snippet", "assets", "doi"):
        assert REGISTRY[name].stage == "pre" and REGISTRY[name].needs_io
    assert REGISTRY["highlight"].stage == "post" and not REGISTRY["highlight"].needs_io
