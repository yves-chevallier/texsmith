"""Regression tests for Markdown carried by an image's ``alt`` attribute.

Python-Markdown copies the image description verbatim into ``alt``, so
``![anti-*windup*](x.png)`` reaches the HTML with its asterisks intact. The
alt doubles as the figure caption (bare image) and as the short caption
(list of figures), where the emphasis the author wrote must render as
emphasis — not ship as literal punctuation.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown
from texsmith.core.config import BookConfig
from texsmith.ir import nodes as ir
from texsmith.readers.html import HtmlReader
from texsmith.writers.typst import TypstWriter, TypstWriterState


@pytest.fixture
def renderer(tmp_path: Path) -> LaTeXRenderer:
    Image.new("RGB", (16, 16), color="blue").save(tmp_path / "a.png")
    config = BookConfig(project_dir=tmp_path)
    return LaTeXRenderer(
        config=config,
        output_root=tmp_path / "build",
        parser="html.parser",
    )


def _latex(renderer: LaTeXRenderer, tmp_path: Path, markdown: str) -> str:
    html = render_markdown(
        markdown, extensions=DEFAULT_MARKDOWN_EXTENSIONS, base_path=tmp_path
    ).html
    return renderer.render(html, runtime={"source_dir": tmp_path})


# ---------------------------------------------------------------------------
# Reader: the alt attribute is parsed as inline Markdown
# ---------------------------------------------------------------------------


def _image(html: str) -> ir.Image:
    document = HtmlReader().read(html)
    for block in document.content:
        for inline in getattr(block, "content", ()):
            if isinstance(inline, ir.Image):
                return inline
    raise AssertionError("no image found")


def test_reader_parses_emphasis_in_the_alt() -> None:
    image = _image('<p><img alt="anti-*windup* control" src="a.png"/></p>')
    assert any(isinstance(node, ir.Emph) for node in image.alt)


def test_reader_keeps_a_plain_alt_as_a_single_str() -> None:
    image = _image('<p><img alt="a plain description" src="a.png"/></p>')
    assert image.alt == (ir.Str("a plain description"),)


# ---------------------------------------------------------------------------
# LaTeX: caption and short caption
# ---------------------------------------------------------------------------


def test_alt_markdown_reaches_the_caption_as_emphasis(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    latex = _latex(
        renderer,
        tmp_path,
        "![Structure du régulateur, avec anti-*windup* par"
        " *back-calculation*](a.png){width=100% #fig:pdff}\n",
    )
    assert "\\emph{windup}" in latex
    assert "\\emph{back-calculation}" in latex
    assert "*windup*" not in latex


def test_alt_markdown_reaches_the_short_caption(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _latex(
        renderer,
        tmp_path,
        "![Anti-*windup*](a.png){#fig:pdff}\n\n"
        "/// caption\nStructure canonique du régulateur, avec anticipation.\n///\n",
    )
    assert "\\caption[Anti-\\emph{windup}]" in latex


def test_plain_alt_still_renders_verbatim(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _latex(renderer, tmp_path, "![A plain caption](a.png){#fig:x}\n")
    assert "A plain caption" in latex


# ---------------------------------------------------------------------------
# Typst: same alt, same emphasis
# ---------------------------------------------------------------------------


def test_alt_markdown_reaches_the_typst_caption(tmp_path: Path) -> None:
    html = render_markdown(
        "![anti-*windup* control](a.png){#fig:x}\n",
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
        base_path=tmp_path,
    ).html
    typst = TypstWriter(TypstWriterState()).write(HtmlReader().read(html))
    assert "_windup_" in typst
    assert "*windup*" not in typst
