"""Regression tests for figure label placement and unparsed-block diagnostics.

The ``\\label`` of a captioned figure must be emitted *after* ``\\caption``:
``\\label`` captures the current ``\\@currentlabel``, which ``\\caption`` sets
to the figure number. Emitted earlier in the environment (the historical
behaviour), a cross-reference such as ``\\ref{my-figure}`` resolved to the
number of the enclosing *section* instead of the figure number.
"""

from __future__ import annotations

from pathlib import Path
import re

from PIL import Image
import pytest

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


def test_figure_label_is_emitted_after_caption(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _render(
        renderer,
        tmp_path,
        '<figure id="my-figure"><img src="a.png"/><figcaption>Cap</figcaption></figure>',
    )
    assert "\\label{my-figure}" in latex
    caption_pos = latex.index("\\caption")
    label_pos = latex.index("\\label{my-figure}")
    assert label_pos > caption_pos, "\\label must follow \\caption to pick up the figure number"


def test_figure_label_is_attached_to_caption_line(renderer: LaTeXRenderer, tmp_path: Path) -> None:
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


def test_figure_without_label_has_no_label(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _render(
        renderer,
        tmp_path,
        '<figure><img src="a.png"/><figcaption>Cap</figcaption></figure>',
    )
    assert "\\label" not in latex


def test_admonition_figure_label_follows_captionof(renderer: LaTeXRenderer, tmp_path: Path) -> None:
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
# Short captions (list of figures)
# ---------------------------------------------------------------------------


def test_alt_becomes_short_caption_when_caption_is_longer(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    # The whole point of the short caption: the list of figures carries the
    # terse ``alt`` while the figure itself carries the explanatory caption.
    latex = _render(
        renderer,
        tmp_path,
        '<figure><img src="a.png" alt="Ripple current"/>'
        "<figcaption>Phase current reconstructed over two switching periods, "
        "worst-case duty cycle.</figcaption></figure>",
    )
    assert "\\caption[Ripple current]{Phase current reconstructed" in latex


def test_short_caption_dropped_when_alt_is_longer_than_caption(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    # A "short" caption more verbose than the caption it stands for would make
    # the list of figures worse, so it is left out.
    latex = _render(
        renderer,
        tmp_path,
        '<figure><img src="a.png" alt="A long-winded description of the figure"/>'
        "<figcaption>Short.</figcaption></figure>",
    )
    assert "\\caption{Short.}" in latex
    assert "\\caption[" not in latex


def test_short_caption_kept_when_alt_matches_caption(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    # Historical behaviour for figures whose alt *is* the caption.
    latex = _render(
        renderer,
        tmp_path,
        '<figure><img src="a.png" alt="Cap"/><figcaption>Cap</figcaption></figure>',
    )
    assert "\\caption[Cap]{Cap}" in latex


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


# ---------------------------------------------------------------------------
# ``attr_list`` identifiers carried by the ``<img>`` element itself
# ---------------------------------------------------------------------------


def _markdown_to_latex(source: str, tmp_path: Path) -> str:
    """Render Markdown through the production extension set into LaTeX."""
    import markdown

    from texsmith.ui.cli import DEFAULT_MARKDOWN_EXTENSIONS

    html = markdown.Markdown(extensions=DEFAULT_MARKDOWN_EXTENSIONS).convert(source)
    renderer = LaTeXRenderer(
        config=BookConfig(project_dir=tmp_path),
        output_root=tmp_path / "build",
        parser="html.parser",
    )
    return renderer.render(html, runtime={"source_dir": tmp_path})


def test_image_id_is_read_into_the_ir() -> None:
    doc = HtmlReader().read('<p><img src="a.png" alt="Legende" id="fig:essai"/></p>')
    image = doc.content[0].content[0]
    assert isinstance(image, ir.Image)
    assert image.identifier == "fig:essai"


def test_attr_list_image_id_becomes_a_label(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _markdown_to_latex("![Legende](a.png){#fig:essai}\n\nVoir @fig:essai.\n", tmp_path)
    assert re.search(r"\\caption(?:\[[^\]]*\])?\{Legende\}\\label\{fig:essai\}", latex)
    # The cross-reference now points at a label that exists.
    assert re.search(r"\\c?ref\{fig:essai\}", latex)


def test_image_id_labels_a_bare_inline_image(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _render(renderer, tmp_path, '<p><img src="a.png" id="fig:bare"/></p>')
    assert "\\label{fig:bare}" in latex


def test_image_without_id_emits_no_label(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _render(renderer, tmp_path, '<p><img src="a.png" alt="Legende"/></p>')
    assert "\\label" not in latex


def test_figure_id_wins_over_image_id(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    # ``pymdownx.blocks.caption`` declares the anchor on the ``<figure>``; an
    # ``attr_list`` id left on the image must not shadow it.
    latex = _render(
        renderer,
        tmp_path,
        '<figure id="fig-block"><p><img src="a.png" id="img-id"/></p>'
        "<figcaption><p>Cap</p></figcaption></figure>",
    )
    assert "\\label{fig-block}" in latex
    assert "img-id" not in latex


def test_linked_image_keeps_its_label(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _render(
        renderer,
        tmp_path,
        '<p><a href="https://example.com"><img src="a.png" alt="Cap" id="fig:linked"/></a></p>',
    )
    assert "\\label{fig:linked}" in latex


# ---------------------------------------------------------------------------
# Typst backend
# ---------------------------------------------------------------------------


def _typst(html: str) -> str:
    from texsmith.writers.typst import TypstWriter, TypstWriterState

    return TypstWriter(TypstWriterState()).write(HtmlReader().read(html))


def test_typst_image_id_labels_the_figure() -> None:
    typst = _typst('<p><img src="a.png" alt="Legende" id="fig:essai"/></p>')
    assert "caption: [Legende]," in typst
    assert typst.strip().endswith("<fig:essai>")


def test_typst_image_id_labels_an_uncaptioned_image() -> None:
    # Without a caption there is no ``#figure`` to hang the label on, so one is
    # introduced rather than labelling an ``#align`` block.
    typst = _typst('<p><img src="a.png" id="fig:bare"/></p>')
    assert typst.strip().startswith("#figure(")
    assert typst.strip().endswith("<fig:bare>")


def test_typst_inline_image_id_trails_the_image() -> None:
    typst = _typst('<p>Voir <img src="a.png" id="fig:inline"/> ici.</p>')
    assert '#image("a.png")<fig:inline>' in typst


def test_typst_image_without_id_has_no_label() -> None:
    typst = _typst('<p><img src="a.png" alt="Legende"/></p>')
    assert "caption: [Legende]," in typst
    assert not typst.strip().endswith(">")


def test_typst_figure_id_wins_over_image_id() -> None:
    typst = _typst(
        '<figure id="fig-block"><p><img src="a.png" id="img-id"/></p>'
        "<figcaption><p>Cap</p></figcaption></figure>"
    )
    assert typst.strip().endswith("<fig-block>")
    assert "img-id" not in typst
