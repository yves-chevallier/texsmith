"""The ``snippet`` pass: fences to figures through a fake renderer, failures to diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import pytest
from tmark.ir import model
from tmark.ir.walk import walk

from texsmith.adapters.plugins.snippet import SnippetAssets, SnippetBlock
from texsmith.passes import REGISTRY, build_pipeline, snippet as snippet_pass


FIXTURES = Path(__file__).resolve().parent


@dataclass
class FakeRenderer:
    """Writes ``snippet-<n>.pdf``/``.png`` placeholders instead of running LaTeX."""

    failing: str | None = None
    calls: list[tuple[SnippetBlock, Path, Path]] = field(default_factory=list)

    def __call__(
        self, block: SnippetBlock, *, output_dir: Path, source_path: Path, emitter: object
    ) -> SnippetAssets:
        del emitter
        self.calls.append((block, output_dir, source_path))
        if self.failing and block.content and self.failing in block.content:
            raise RuntimeError("tectonic exited with status 1")
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf = output_dir / f"snippet-{len(self.calls)}.pdf"
        png = output_dir / f"snippet-{len(self.calls)}.png"
        pdf.write_bytes(b"%PDF-1.4")
        png.write_bytes(b"\x89PNG\r\n")
        return SnippetAssets(pdf=pdf, png=png)


@pytest.fixture
def renderer(monkeypatch: pytest.MonkeyPatch) -> FakeRenderer:
    fake = FakeRenderer()
    monkeypatch.setattr(snippet_pass, "render_snippet_assets", fake)
    return fake


def _figures(document) -> list[model.Figure]:
    assert document.ir is not None
    return [node for node in walk(document.ir) if isinstance(node, model.Figure)]


def _structural(harness, document, output_dir: Path) -> dict:
    """``structural()`` with the temporary output directory spelled ``<out>`` (the goldens)."""
    text = json.dumps(harness.structural(document))
    return json.loads(text.replace(output_dir.resolve().as_posix(), "<out>"))


def test_snippet_is_registered_after_include_before_assets() -> None:
    order = [item.name for item in build_pipeline()]
    assert order.index("include") < order.index("snippet") < order.index("assets")
    assert REGISTRY["snippet"].stage == "pre" and REGISTRY["snippet"].needs_io


def test_fences_become_figures(harness, renderer: FakeRenderer, tmp_path: Path) -> None:
    document = harness.load("snippet", "basic")
    ctx = harness.context(document, output_dir=tmp_path)
    floor = ctx.ids.floor
    out = harness.run("snippet", document, ctx)

    assert out is not document
    assert _structural(harness, out, tmp_path) == harness.expected("snippet", "basic")
    assert harness.diagnostics(ctx) == []

    # The plain fence is untouched; each snippet fence became one figure.
    assert document.ir is not None and out.ir is not None
    codes = [node for node in walk(out.ir) if isinstance(node, model.CodeBlock)]
    assert [code.lang for code in codes] == ["python"]
    assert len(_figures(out)) == 3

    # The figure keeps the fence's id and span; the nodes inside take fresh ids.
    fences = [
        node
        for node in walk(document.ir)
        if isinstance(node, model.CodeBlock) and "snippet" in node.options.classes
    ]
    for fence, figure in zip(fences, _figures(out), strict=True):
        assert figure.id == fence.id and figure.span == fence.span
        for node in walk(figure):
            if node is not figure:
                assert node.id >= floor and node.span == fence.span

    # The assets land in ``<output>/snippets``; ``src`` is their absolute path,
    # the hand-off the ``assets`` pass stores under ``assets/`` like any image.
    assert all(call[1] == tmp_path / "snippets" for call in renderer.calls)
    assert all(call[2] == FIXTURES / "snippet" / "basic.md" for call in renderer.calls)
    assert (tmp_path / "snippets" / "snippet-1.pdf").exists()
    images = [node for node in walk(out.ir) if isinstance(node, model.Image)]
    assert all(Path(image.src).is_absolute() and Path(image.src).exists() for image in images)

    # The real fence parser ran: content, template, caption, width, label.
    first, second, third = (call[0] for call in renderer.calls)
    assert first.content == "Hello **World**!"
    assert first.template_id == "snippet" and first.caption == "Hello preview"
    assert first.figure_width == "60%" and first.label is None
    assert second.content.startswith("```c\n") and second.label == "snip:code"
    assert second.caption is None and second.figure_width == "50%"
    assert third.template_id == "article" and third.label == "fig:nested"
    assert third.content.strip() == "# Inside a callout"


def test_typst_backend_takes_the_png(harness, renderer: FakeRenderer, tmp_path: Path) -> None:
    document = harness.load("snippet", "basic")
    ctx = harness.context(document, output_dir=tmp_path, backend="typst")
    out = harness.run("snippet", document, ctx)
    images = [node for node in walk(out.ir) if isinstance(node, model.Image)]
    snippets = (tmp_path / "snippets").resolve()
    assert [image.src for image in images] == [
        (snippets / f"snippet-{n}.png").as_posix() for n in (1, 2, 3)
    ]


def test_failed_builds_keep_the_fence(harness, renderer: FakeRenderer, tmp_path: Path) -> None:
    renderer.failing = "fails"
    document = harness.load("snippet", "failure")
    ctx = harness.context(document, output_dir=tmp_path)
    out = harness.run("snippet", document, ctx)

    assert _structural(harness, out, tmp_path) == harness.expected("snippet", "failure")
    assert harness.diagnostics(ctx) == harness.expected_diagnostics("snippet", "failure")
    assert len(_figures(out)) == 1
    # The three failing fences stay as code, classes and all.
    codes = [node for node in walk(out.ir) if isinstance(node, model.CodeBlock)]
    assert len(codes) == 3 and all("snippet" in code.options.classes for code in codes)


def test_no_snippet_returns_the_input(harness, renderer: FakeRenderer) -> None:
    document = harness.load("stubs", "plain")
    ctx = harness.context(document)
    assert harness.run("snippet", document, ctx) is document
    assert renderer.calls == [] and len(ctx.diagnostics) == 0
