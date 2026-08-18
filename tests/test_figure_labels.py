"""Regression tests for figure label placement and unparsed-block diagnostics.

The ``\\label`` of a captioned figure must be emitted *after* ``\\caption``:
``\\label`` captures the current ``\\@currentlabel``, which ``\\caption`` sets
to the figure number. Emitted earlier in the environment (the historical
behaviour), a cross-reference such as ``\\ref{my-figure}`` resolved to the
number of the enclosing *section* instead of the figure number.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.config import BookConfig
from texsmith.ir import nodes as ir
from texsmith.readers.html import HtmlReader


@pytest.fixture
def renderer(tmp_path: Path) -> LaTeXRenderer:
    Image.new("RGB", (16, 16), color="blue").save(tmp_path / "a.png")
    config = BookConfig(project_dir=tmp_path)
    return LaTeXRenderer(
        config=config,
        output_root=tmp_path / "build",
        parser="html.parser",
    )


def _render(renderer: LaTeXRenderer, tmp_path: Path, html: str) -> str:
    return renderer.render(html, runtime={"source_dir": tmp_path})


# ---------------------------------------------------------------------------
# Label placement in the ``figure`` template
# ---------------------------------------------------------------------------


def test_figure_label_is_emitted_after_caption(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    latex = _render(
        renderer,
        tmp_path,
        '<figure id="my-figure"><img src="a.png"/><figcaption>Cap</figcaption></figure>',
    )
    assert "\\label{my-figure}" in latex
    caption_pos = latex.index("\\caption")
    label_pos = latex.index("\\label{my-figure}")
    assert label_pos > caption_pos, "\\label must follow \\caption to pick up the figure number"


def test_figure_label_is_attached_to_caption_line(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    latex = _render(
        renderer,
        tmp_path,
        '<figure id="my-figure"><img src="a.png"/><figcaption>Cap</figcaption></figure>',
    )
    # The label must live on the caption statement itself, not merely
    # somewhere later in the environment.
    assert re.search(r"\\caption(?:\[[^\]]*\])?\{Cap\}\\label\{my-figure\}", latex)


def test_figure_label_without_caption_is_still_emitted(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    latex = _render(renderer, tmp_path, '<figure id="lonely"><img src="a.png"/></figure>')
    assert "\\label{lonely}" in latex
    assert "\\caption" not in latex


def test_figure_without_label_has_no_label(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    latex = _render(
        renderer,
        tmp_path,
        '<figure><img src="a.png"/><figcaption>Cap</figcaption></figure>',
    )
    assert "\\label" not in latex


def test_admonition_figure_label_follows_captionof(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    # Inside admonitions the ``figure_tcolorbox`` template is used, which
    # relies on \captionof{figure}; the same ordering constraint applies.
    latex = _render(
        renderer,
        tmp_path,
        '<div class="admonition note"><p class="admonition-title">Note</p>'
        '<figure id="boxed"><img src="a.png"/><figcaption>Cap</figcaption></figure></div>',
    )
    assert "\\label{boxed}" in latex
    captionof_pos = latex.index("\\captionof{figure}")
    label_pos = latex.index("\\label{boxed}")
    assert label_pos > captionof_pos


# ---------------------------------------------------------------------------
# Diagnostics for pymdownx blocks that leaked through as plain text
# ---------------------------------------------------------------------------


class _CollectingEmitter:
    debug_enabled = False

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        self.warnings.append(message)

    def error(self, message: str, exc: BaseException | None = None) -> None:
        pass

    def event(self, name: str, payload: object) -> None:
        pass


def test_unprocessed_caption_block_emits_warning() -> None:
    emitter = _CollectingEmitter()
    # This is what python-markdown produces when a ``/// caption`` block fails
    # to parse (e.g. an id containing ':') and degrades to a plain paragraph.
    html = "<p>/// caption\n    attrs: {id: fig:x}\nLa légende.\n///</p>"
    doc = HtmlReader(diagnostics=emitter).read(html)
    assert any("Unprocessed block marker" in w for w in emitter.warnings)
    # The paragraph is still rendered (visible in the output), only flagged.
    assert any(isinstance(block, ir.Para) for block in doc.content)


def test_regular_paragraph_does_not_warn() -> None:
    emitter = _CollectingEmitter()
    HtmlReader(diagnostics=emitter).read("<p>Un paragraphe // ordinaire.</p>")
    assert not any("Unprocessed block marker" in w for w in emitter.warnings)
