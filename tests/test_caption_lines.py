"""Caption lines placed after a float: ``Table:``, ``Figure:``, ``Listing:``.

TMark's canonical caption position is the paragraph *after* the block
(``tmark fmt`` prints it there); the ``Table:`` line before its table stays
accepted sugar. Both spellings must lower to the same HTML — and so to the
same LaTeX and Typst — as the shipping forms (``Table:`` before, ``/// caption``).
"""

from __future__ import annotations

from pathlib import Path
import re

from bs4 import BeautifulSoup
from PIL import Image
import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown
from texsmith.core.config import BookConfig
from texsmith.readers.html import HtmlReader
from texsmith.writers.typst import TypstWriter, TypstWriterState


PIPE_TABLE = "| A | B |\n| - | - |\n| 1 | 2 |\n"
YAML_TABLE = "```yaml table\ncolumns: [A, B]\nrows:\n  - [1, 2]\n```\n"
IMAGE = "![Alt](a.png){width=70%}\n"
CODE = "```python\nx = 1\n```\n"


@pytest.fixture
def renderer(tmp_path: Path) -> LaTeXRenderer:
    Image.new("RGB", (16, 16), color="blue").save(tmp_path / "a.png")
    return LaTeXRenderer(
        config=BookConfig(project_dir=tmp_path),
        output_root=tmp_path / "build",
        parser="html.parser",
    )


def _html(markdown: str, base_path: Path | None = None) -> str:
    return render_markdown(
        markdown, extensions=DEFAULT_MARKDOWN_EXTENSIONS, base_path=base_path
    ).html


def _soup(markdown: str) -> BeautifulSoup:
    return BeautifulSoup(_html(markdown), "html.parser")


def _latex(renderer: LaTeXRenderer, tmp_path: Path, markdown: str) -> str:
    return renderer.render(_html(markdown, tmp_path), runtime={"source_dir": tmp_path})


def _typst(markdown: str) -> str:
    return TypstWriter(TypstWriterState()).write(HtmlReader().read(_html(markdown)))


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Tables: ``<caption>`` inside the ``<table>``, id on the table
# ---------------------------------------------------------------------------


def test_table_caption_after_a_pipe_table() -> None:
    table = _soup(PIPE_TABLE + "\nTable: Stock. {#tbl:stock}\n").find("table")
    assert table is not None
    assert table.get("id") == "tbl:stock"
    assert table.caption is not None
    assert table.caption.get_text(strip=True) == "Stock."
    assert "Table:" not in str(table)


def test_table_caption_before_and_after_are_equivalent() -> None:
    before = _html("Table: Stock. {#tbl:stock}\n\n" + PIPE_TABLE)
    after = _html(PIPE_TABLE + "\nTable: Stock. {#tbl:stock}\n")
    assert _squash(after) == _squash(before)


def test_yaml_table_caption_after_the_fence() -> None:
    table = _soup(YAML_TABLE + "\nTable: Stock. {#tbl:stock}\n").find("table")
    assert table is not None
    assert table.get("id") == "tbl:stock"
    assert table.caption is not None and table.caption.get_text(strip=True) == "Stock."


def test_yaml_table_caption_before_and_after_are_equivalent() -> None:
    before = _html("Table: Stock. {#tbl:stock}\n\n" + YAML_TABLE)
    after = _html(YAML_TABLE + "\nTable: Stock. {#tbl:stock}\n")
    assert _squash(after) == _squash(before)


def test_yaml_table_leaves_a_longer_paragraph_alone() -> None:
    soup = _soup(YAML_TABLE + "\nTable: Stock.\nOne more line.\n")
    assert soup.find("table").caption is None
    assert soup.find("p").get_text().startswith("Table: Stock.")


def test_table_caption_after_a_table_config_fence() -> None:
    # Canonical order: the table, its ``table-config`` fence, then the caption.
    source = (
        PIPE_TABLE
        + "\n```yaml table-config\ncolumns:\n  - {width: 30%}\n  - {width: X}\n```\n"
        + "\nTable: Stock. {#tbl:stock}\n"
    )
    table = _soup(source).find("table")
    assert table.get("id") == "tbl:stock"
    assert table.get("data-ts-env") == "tabularx"
    assert table.caption is not None and table.caption.get_text(strip=True) == "Stock."


def test_table_caption_without_an_attribute_list() -> None:
    table = _soup(PIPE_TABLE + "\nTable: Stock.\n").find("table")
    assert table.get("id") is None
    assert table.caption.get_text(strip=True) == "Stock."


def test_table_caption_renders_the_same_latex_and_typst(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    latex = _latex(renderer, tmp_path, PIPE_TABLE + "\nTable: Stock. {#tbl:stock}\n")
    assert "\\caption{Stock.}" in latex
    assert "\\label{tbl:stock}" in latex
    typst = _typst(PIPE_TABLE + "\nTable: Stock. {#tbl:stock}\n")
    assert "caption: [Stock.]" in typst
    assert "<tbl:stock>" in typst


# ---------------------------------------------------------------------------
# Figures: the ``<figure><figcaption>`` shape of ``/// caption``
# ---------------------------------------------------------------------------


def test_figure_caption_after_an_image() -> None:
    figure = _soup(IMAGE + "\nFigure: Full *caption*. {#fig:plot}\n").find("figure")
    assert figure is not None
    assert figure.get("id") == "fig:plot"
    assert figure.find("img") is not None
    caption = figure.find("figcaption")
    assert caption is not None
    assert caption.find("em").get_text() == "caption"
    assert _squash(caption.get_text()) == "Full caption."


def test_figure_caption_matches_the_caption_block_output(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    # ``/// caption`` rejects ids with a colon, so compare on a plain id.
    block = _latex(
        renderer, tmp_path, IMAGE + "\n/// caption\n    attrs: {id: plot}\nFull caption.\n///\n"
    )
    line = _latex(renderer, tmp_path, IMAGE + "\nFigure: Full caption. {#plot}\n")
    assert line == block
    assert "\\caption[Alt]{Full caption.}\\label{plot}" in line


def test_figure_caption_keeps_a_prefixed_id(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    latex = _latex(renderer, tmp_path, IMAGE + "\nFigure: Full *caption*. {#fig:plot}\n")
    assert "\\caption[Alt]{Full \\emph{caption}.}\\label{fig:plot}" in latex
    typst = _typst(IMAGE + "\nFigure: Full *caption*. {#fig:plot}\n")
    assert "caption: [Full _caption_.]" in typst
    assert "<fig:plot>" in typst


def test_figure_caption_accepts_a_full_attribute_list() -> None:
    figure = _soup(IMAGE + "\nFigure: Full caption. {#fig:plot .wide lang=fr}\n").find("figure")
    assert figure.get("id") == "fig:plot"
    assert figure.get("class") == ["wide"]
    assert figure.get("lang") == "fr"
    assert "{" not in figure.find("figcaption").get_text()


def test_figure_caption_before_the_image_attaches_to_it() -> None:
    # Attachment rule: no float before the line, so the float after it.
    figure = _soup("Figure: Full caption. {#fig:plot}\n\n" + IMAGE).find("figure")
    assert figure is not None and figure.get("id") == "fig:plot"
    assert figure.find("img") is not None


# ---------------------------------------------------------------------------
# Listings: the code block's title slot and label
# ---------------------------------------------------------------------------


def test_listing_caption_after_a_code_block() -> None:
    figure = _soup(CODE + "\nListing: Bubble sort. {#lst:bubble}\n").find("figure")
    assert figure is not None
    assert figure.get("id") == "lst:bubble"
    assert figure.find("div", class_="highlight") is not None
    assert _squash(figure.find("figcaption").get_text()) == "Bubble sort."


def test_listing_caption_renders_as_the_listing_title(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    latex = _latex(renderer, tmp_path, CODE + "\nListing: Bubble *sort*. {#lst:bubble}\n")
    assert "\\begin{code}[label={lst:bubble}]{python}{Bubble \\emph{sort}.}" in latex
    typst = _typst(CODE + "\nListing: Bubble *sort*. {#lst:bubble}\n")
    assert "#figure(" in typst
    assert "caption: [Bubble _sort_.]" in typst
    assert "<lst:bubble>" in typst


def test_listing_caption_matches_the_caption_block_output(
    renderer: LaTeXRenderer, tmp_path: Path
) -> None:
    block = _latex(
        renderer, tmp_path, CODE + "\n/// caption\n    attrs: {id: bubble}\nBubble sort.\n///\n"
    )
    line = _latex(renderer, tmp_path, CODE + "\nListing: Bubble sort. {#bubble}\n")
    assert line == block
    assert "\\begin{code}[label={bubble}]{python}{Bubble sort.}" in line


def test_uncaptioned_code_block_has_no_label(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    assert "\\begin{code}{python}{}" in _latex(renderer, tmp_path, CODE)


def test_listing_caption_ignores_a_diagram_fence() -> None:
    soup = _soup("```mermaid\nflowchart LR\n  A --> B\n```\n\nListing: Nope. {#lst:x}\n")
    assert soup.find("figure") is None
    assert soup.find("p").get_text().startswith("Listing:")


# ---------------------------------------------------------------------------
# Attachment: kind mismatch and orphan lines are left alone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "line"),
    [
        (PIPE_TABLE + "\nFigure: Nope. {#fig:x}\n", "Figure: Nope. {#fig:x}"),
        (IMAGE + "\nTable: Nope. {#tbl:x}\n", "Table: Nope. {#tbl:x}"),
        (CODE + "\nTable: Nope. {#tbl:x}\n", "Table: Nope. {#tbl:x}"),
        (IMAGE + "\nListing: Nope. {#lst:x}\n", "Listing: Nope. {#lst:x}"),
        ("Intro.\n\nTable: Nope. {#tbl:x}\n\nOutro.\n", "Table: Nope. {#tbl:x}"),
    ],
)
def test_mismatched_or_orphan_caption_stays_a_paragraph(source: str, line: str) -> None:
    soup = _soup(source)
    assert soup.find("figure") is None
    assert soup.find("figcaption") is None
    assert soup.find("caption") is None
    assert any(p.get_text() == line for p in soup.find_all("p"))


def test_a_captioned_table_does_not_take_a_second_caption() -> None:
    soup = _soup("Table: First. {#tbl:a}\n\n" + PIPE_TABLE + "\nTable: Second. {#tbl:b}\n")
    table = soup.find("table")
    assert table.get("id") == "tbl:a"
    assert table.caption.get_text(strip=True) == "First."
    assert soup.find("p").get_text() == "Table: Second. {#tbl:b}"
