"""The ``assets`` pass: copies, conversions, fetches, generated diagrams (fake strategies)."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

import pytest
from tmark.ir import model
from tmark.ir.walk import walk

from texsmith.core.conversion.models import ConversionRequest
from texsmith.core.exceptions import TransformerExecutionError
from texsmith.passes.assets import mermaid_caption, resolve_asset_path, strip_theme_variant


_PNG = b"\x89PNG\r\n\x1a\nfake"


def materialise(harness, tmp_path: Path, case: str) -> Any:
    """The case's document with its source files created in ``tmp_path``."""
    source_dir = tmp_path / "src"
    source_dir.mkdir(parents=True)
    shutil.copy(harness.source("assets", case), source_dir / f"{case}.md")
    (source_dir / "figure.png").write_bytes(_PNG)
    (source_dir / "diagram.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (source_dir / "sketch.drawio").write_text("<mxfile/>")
    (source_dir / "pipeline.mmd").write_text("%% From file\nflowchart TD\n  A --> B\n")
    document = harness.load("assets", case)
    document.source_path = source_dir / f"{case}.md"
    return document


def context(harness, document, tmp_path: Path, **overrides: Any):
    ctx = harness.context(document)
    ctx.output_dir = tmp_path / "out"
    ctx.request = ConversionRequest()
    for name, value in overrides.items():
        setattr(ctx, name, value)
    return ctx


def images(document) -> list[model.Image]:
    assert document.ir is not None
    return [node for node in walk(document.ir) if isinstance(node, model.Image)]


def test_helpers() -> None:
    assert strip_theme_variant("a.png#only-dark") == "a.png"
    assert strip_theme_variant("a.png#x") == "a.png#x"
    assert mermaid_caption("%% Cap\ngraph LR") == ("Cap", "graph LR")
    assert mermaid_caption("graph LR") == (None, "graph LR")


def test_a_root_relative_path_belongs_to_the_documentation_root(tmp_path: Path) -> None:
    """MkDocs' ``validation.absolute_links: relative_to_docs``, for assets too.

    A site page writes ``/assets/logo.png`` for a file under ``docs_dir``; only a
    standalone conversion means the filesystem root by a leading slash.
    """
    docs = (tmp_path / "docs").resolve()
    (docs / "assets").mkdir(parents=True)
    (docs / "assets" / "logo.png").write_bytes(_PNG)
    page_dir = docs / "course"
    page_dir.mkdir()
    (page_dir / "figure.png").write_bytes(_PNG)

    resolve = resolve_asset_path
    assert resolve("/assets/logo.png", source_dir=page_dir, root_dir=docs) == (
        docs / "assets" / "logo.png"
    )
    assert resolve("figure.png", source_dir=page_dir, root_dir=docs) == page_dir / "figure.png"
    assert resolve("../assets/logo.png", source_dir=page_dir, root_dir=docs) == (
        docs / "assets" / "logo.png"
    )
    assert resolve("/assets/logo.png", source_dir=page_dir, root_dir=None) is None
    assert resolve("/assets/gone.png", source_dir=page_dir, root_dir=docs) is None
    # An absolute path a pass computed — a snippet preview beside the output —
    # still names the file it names, root or no root.
    preview = tmp_path / "press" / "snippets" / "preview.pdf"
    preview.parent.mkdir(parents=True)
    preview.write_bytes(_PNG)
    assert resolve(str(preview), source_dir=page_dir, root_dir=docs) == preview


def test_local_assets_copied_converted_fetched_and_reported(
    harness, tmp_path: Path, fake_converters
) -> None:
    document = materialise(harness, tmp_path, "local")
    ctx = context(harness, document, tmp_path)
    out = harness.run("assets", document, ctx)

    assert out is not document
    assert harness.structural(out) == harness.expected("assets", "local")
    assert harness.diagnostics(ctx) == harness.expected_diagnostics("assets", "local")

    assets = tmp_path / "out" / "assets"
    for name in ("figure.png", "diagram.pdf", "sketch.pdf", "photo.png"):
        assert (assets / name).is_file(), name
    # The draw.io export honoured ``{crop=false}``; the SVG went through the converter.
    drawio = fake_converters["drawio"].calls
    assert len(drawio) == 1 and drawio[0]["crop"] is False
    assert [Path(call["source"]).name for call in fake_converters["svg"].calls] == ["diagram.svg"]
    # The remote fetch went through the manifest of the legacy helper.
    fetch = fake_converters["fetch-image"].calls
    assert fetch[0]["source"] == "https://example.com/pic/photo.png"
    assert fetch[0]["convert"] is False and "manifest" in fetch[0]
    assert fetch[0]["manifest_path"] == assets / ".converted" / "remote-assets.json"
    # The copy list is handed back (key → path) for the wrapper.
    copied = ctx.values["assets"]
    assert {path.name for path in copied.values()} == {
        "figure.png",
        "diagram.pdf",
        "sketch.pdf",
        "photo.png",
    }

    # Span rule 1: a rewritten image keeps its id and span; rule 2: the literal
    # for the missing file takes the image's span and a fresh id.
    before = {node.id: node for node in images(document)}
    for node in images(out):
        assert node.span == before[node.id].span
    missing = next(
        node for node in walk(out.ir) if isinstance(node, model.Str) and "missing" in node.text
    )
    gone = next(node for node in images(document) if node.src == "missing.png")
    assert missing.span == gone.span and missing.id not in before


def test_typst_keeps_native_formats_and_renders_diagrams_as_pdf(
    harness, tmp_path: Path, fake_converters
) -> None:
    """Typst reads SVG itself and embeds the same PDF diagram LaTeX gets."""
    document = materialise(harness, tmp_path, "local")
    ctx = context(harness, document, tmp_path, backend="typst")
    out = harness.run("assets", document, ctx)

    srcs = [node.src for node in images(out)]
    assert srcs == [
        "assets/figure.png",
        "assets/diagram.svg",
        "assets/sketch.pdf",
        "assets/photo.png",
        "assets/figure.png",
    ]
    assert fake_converters["svg"].calls == []
    assert fake_converters["drawio"].calls[0].get("format") in (None, "pdf")


def test_hash_assets_names_by_digest(harness, tmp_path: Path, fake_converters) -> None:
    document = materialise(harness, tmp_path, "local")
    ctx = context(harness, document, tmp_path, hash_assets=True)
    out = harness.run("assets", document, ctx)
    first = images(out)[0].src
    assert first.startswith("assets/") and first.endswith(".png")
    assert len(Path(first).stem) == 64


def test_mermaid_fences_files_and_live_urls(harness, tmp_path: Path, fake_converters) -> None:
    document = materialise(harness, tmp_path, "mermaid")
    ctx = context(harness, document, tmp_path)
    out = harness.run("assets", document, ctx)

    assert harness.structural(out) == harness.expected("assets", "mermaid")
    assert harness.diagnostics(ctx) == harness.expected_diagnostics("assets", "mermaid")

    # Four diagrams rendered from text: two fences, the ``.mmd`` file, the live URL.
    sources = [call["source"] for call in fake_converters["mermaid"].calls]
    assert sources == [
        "flowchart LR\n    A --> B",
        "graph TD; X-->Y",
        "flowchart TD\n  A --> B",
        "graph LR; A-->B",
    ]
    assert all(call["backend"] == "playwright" for call in fake_converters["mermaid"].calls)

    blocks = out.ir.blocks
    # ``%% Build pipeline`` became a Caption right after the paragraph...
    assert isinstance(blocks[1], model.Para) and isinstance(blocks[2], model.Caption)
    assert blocks[2].kind is model.CaptionKind.FIGURE
    # ...with the image's span and fresh ids (span rule 3).
    image = blocks[1].content[0]
    assert isinstance(image, model.Image)
    assert blocks[2].span == image.span and blocks[2].id >= ctx.ids.floor - 4
    # The explicit ``Figure:`` caption stays, no second one is added.
    captions = [block for block in blocks if isinstance(block, model.Caption)]
    assert [block.content[0].text for block in captions] == [
        "Build pipeline",
        "Explicit caption",
        "From file",
    ]
    # The rendered image keeps its id and span, drops the fence text.
    rendered = images(out)[0]
    assert rendered.id == image.id and rendered.attrs.kv == ()


def test_mermaid_for_typst_is_the_same_pdf(harness, tmp_path: Path, fake_converters) -> None:
    document = materialise(harness, tmp_path, "mermaid")
    ctx = context(harness, document, tmp_path, backend="typst")
    out = harness.run("assets", document, ctx)
    assert all(node.src.endswith(".pdf") for node in images(out))
    assert all(call.get("format") in (None, "pdf") for call in fake_converters["mermaid"].calls)


def test_copy_assets_false_substitutes_the_legacy_placeholders(
    harness, tmp_path: Path, fake_converters
) -> None:
    document = materialise(harness, tmp_path, "mermaid")
    ctx = context(harness, document, tmp_path, copy_assets=False)
    out = harness.run("assets", document, ctx)
    texts = [
        block.content[0].text
        for block in out.ir.blocks
        if isinstance(block, model.Para) and isinstance(block.content[0], model.Str)
    ]
    assert texts == [
        "Build pipeline",
        "Mermaid diagram",
        "From file",
        "Mermaid diagram",
        "Mermaid diagram",
    ]
    assert fake_converters["mermaid"].calls == []
    assert not (tmp_path / "out").exists()

    document = materialise(harness, tmp_path / "second", "local")
    ctx = context(harness, document, tmp_path / "second", copy_assets=False)
    out = harness.run("assets", document, ctx)
    assert images(out) == []
    assert [node.text for node in walk(out.ir) if isinstance(node, model.Str)][1:] == [
        "A figure",
        "Vector",
        "Sketch",
        "Gone",
        "Remote",
        "Linked",
    ]


def test_failures_become_literals_with_diagnostics(
    harness, tmp_path: Path, fake_converters
) -> None:
    fake_converters["mermaid"].fail = TransformerExecutionError("no browser")
    fake_converters["fetch-image"].fail = OSError("offline")
    document = materialise(harness, tmp_path, "mermaid")
    ctx = context(harness, document, tmp_path)
    out = harness.run("assets", document, ctx)

    literals = [node.text for node in walk(out.ir) if isinstance(node, model.Str)]
    assert "[Build pipeline unavailable]" in literals
    assert "[Mermaid diagram unavailable]" in literals
    assert images(out) == []
    codes = [record.code for record in ctx.diagnostics]
    assert codes == ["asset-convert-failed"] * 5
    assert "no browser" in next(iter(ctx.diagnostics)).message

    document = materialise(harness, tmp_path / "second", "local")
    ctx = context(harness, document, tmp_path / "second")
    out = harness.run("assets", document, ctx)
    assert "[asset: https://example.com/pic/photo.png: fetch failed]" in [
        node.text for node in walk(out.ir) if isinstance(node, model.Str)
    ]
    assert {record.code for record in ctx.diagnostics} == {
        "asset-missing",
        "asset-convert-failed",
    }


def test_unrendered_generators_and_data_urls_are_left_alone(harness, tmp_path: Path) -> None:
    document = harness.load("stubs", "plain")
    node = model.Image(src="", attrs=model.Attrs(kv=(("generate", "python"), ("code", "1"))))
    data = model.Image(src="data:image/png;base64,AAAA")
    para = model.Para(content=(node, data))
    document.ir = document.ir.__class__(blocks=(para,))
    ctx = context(harness, document, tmp_path)
    assert harness.run("assets", document, ctx) is document


@pytest.mark.parametrize("case", ["keep"])
def test_identity_without_images(harness, tmp_path: Path, case: str) -> None:
    document = harness.load("title", case)
    ctx = context(harness, document, tmp_path)
    assert harness.run("assets", document, ctx) is document
    assert len(ctx.diagnostics) == 0
