"""The ``emoji`` pass: clusters → ``Span{emoji}`` (font modes) or ``Image{.icon}`` (artifact)."""

from __future__ import annotations

from pathlib import Path

from tmark.ir import model
from tmark.ir.walk import walk

from texsmith.passes.emoji import resolve_emoji_mode, twemoji_url


def _spans(document) -> list[model.SpanNode]:
    return [node for node in walk(document.ir) if isinstance(node, model.SpanNode)]


def test_twemoji_url() -> None:
    assert twemoji_url("😀") == "https://twemoji.maxcdn.com/v/latest/svg/1f600.svg"
    assert twemoji_url("🛰️") == "https://twemoji.maxcdn.com/v/latest/svg/1f6f0-fe0f.svg"


def test_mode_resolution_reads_the_legacy_spellings(harness) -> None:
    document = harness.load("emoji", "basic")
    for contexts, expected in (
        (({}, {}), None),
        (({"emoji": "color"}, {}), "color"),
        (({"fonts": {"emoji": "artifact"}}, {}), "artifact"),
        (({}, {"press": {"fonts": {"emoji": "twemoji"}}}), "twemoji"),
        (({"press": {"emoji": "symbola"}}, {"emoji": "color"}), "symbola"),
    ):
        ctx = harness.context(document, contexts=contexts)
        assert resolve_emoji_mode(ctx) == expected


def test_font_modes_wrap_clusters_in_emoji_spans(harness) -> None:
    document = harness.load("emoji", "basic")
    ctx = harness.context(document, contexts=({}, document.front_matter))
    floor = ctx.ids.floor
    out = harness.run("emoji", document, ctx)

    assert out is not document
    assert harness.structural(out) == harness.expected("emoji", "basic")
    assert len(ctx.diagnostics) == 0
    assert "emoji_mode" not in ctx.values  # nothing explicit: the default stays implicit

    spans = _spans(out)
    assert [dict(node.attrs.kv)["emoji"] for node in spans] == ["😀", "👋", "🚀", "🛰️"]
    # Span rule 2: the source span, fresh ids, for the span and its text.
    header = out.ir.blocks[0]
    source = document.ir.blocks[0].content[0]
    assert header.content[1].span == source.span == header.content[1].content[0].span
    assert all(node.id >= floor for node in spans)
    # The code span kept its emoji: no ``Str`` lives inside ``Code``.
    assert [node.text for node in walk(out.ir) if isinstance(node, model.Code)] == ["code 😀"]

    # Idempotent: a second run sees the fenced spans and changes nothing.
    assert harness.run("emoji", out, harness.context(out, contexts=({},))) is out


def test_explicit_mode_is_handed_back(harness) -> None:
    document = harness.load("emoji", "basic")
    ctx = harness.context(document, contexts=({"fonts": {"emoji": "color"}},))
    harness.run("emoji", document, ctx)
    assert ctx.values["emoji_mode"] == "color"


def test_artifact_mode_fetches_icons(harness, tmp_path: Path, fake_converters) -> None:
    document = harness.load("emoji", "basic")
    ctx = harness.context(document, contexts=({"emoji": "artifact"},))
    ctx.output_dir = tmp_path
    out = harness.run("emoji", document, ctx)

    assert harness.structural(out) == harness.expected("emoji", "basic.artifact")
    assert ctx.values["emoji_mode"] == "artifact"
    icons = [node for node in walk(out.ir) if isinstance(node, model.Image)]
    assert all(node.attrs.classes == ("icon",) for node in icons)
    assert all((tmp_path / node.src).is_file() for node in icons)
    fetched = [call["source"] for call in fake_converters["fetch-image"].calls]
    assert fetched == [twemoji_url(cluster) for cluster in ("😀", "👋", "🚀", "🛰️")]
    assert set(ctx.values["assets"]) == set(fetched)


def test_artifact_fetch_failure_keeps_the_character(
    harness, tmp_path: Path, fake_converters
) -> None:
    fake_converters["fetch-image"].fail = OSError("offline")
    document = harness.load("emoji", "basic")
    ctx = harness.context(document, contexts=({"emoji": "artifact"},))
    ctx.output_dir = tmp_path
    out = harness.run("emoji", document, ctx)

    assert [node for node in walk(out.ir) if isinstance(node, model.Image)] == []
    texts = [node.text for node in out.ir.blocks[1].content if isinstance(node, model.Str)]
    assert texts == ["Hello ", "👋", " world, a rocket ", "🚀", " and ", " and ", "."]
    assert [record.code for record in ctx.diagnostics] == ["asset-missing"] * 4
    assert "offline" in next(iter(ctx.diagnostics)).message


def test_identity_without_emoji(harness) -> None:
    document = harness.load("stubs", "plain")
    assert harness.run("emoji", document) is document
