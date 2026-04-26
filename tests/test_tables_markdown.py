"""Tests for the yaml-table Markdown preprocessor."""

from __future__ import annotations

import textwrap

from bs4 import BeautifulSoup
from markdown import Markdown

from texsmith.extensions.tables import YamlTableExtension


def _render(src: str) -> BeautifulSoup:
    md = Markdown(extensions=[YamlTableExtension()])
    html = md.convert(textwrap.dedent(src).strip("\n"))
    return BeautifulSoup(html, "html.parser")


def _render_with_tables(src: str) -> BeautifulSoup:
    md = Markdown(extensions=["tables", YamlTableExtension()])
    html = md.convert(textwrap.dedent(src).strip("\n"))
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_basic_fence_produces_table_element() -> None:
    soup = _render(
        """
        ```yaml table
        columns: [Produit, Genève]
        rows:
          - [Pommes, 120]
        ```
        """
    )
    table = soup.find("table")
    assert table is not None
    assert table.get("data-ts-table") == "1"
    cells = table.find_all(["th", "td"])
    assert any(c.get_text(strip=True) == "Pommes" for c in cells)


def test_caption_line_is_absorbed() -> None:
    soup = _render(
        """
        Table: Stocks par entrepôt

        ```yaml table
        columns: [Produit, Genève]
        rows:
          - [Pommes, 120]
        ```
        """
    )
    table = soup.find("table")
    caption = table.find("caption")
    assert caption is not None
    assert caption.get_text(strip=True) == "Stocks par entrepôt"
    # The Table: line itself must not appear as a paragraph.
    assert "Table:" not in soup.get_text()


def test_caption_with_label_exposes_id() -> None:
    soup = _render(
        """
        Table: Stocks {#tbl:stocks}

        ```yaml table
        columns: [A, B]
        rows:
          - [x, 1]
        ```
        """
    )
    table = soup.find("table")
    assert table.get("id") == "tbl:stocks"
    caption = table.find("caption")
    assert caption.get_text(strip=True) == "Stocks"


def test_tilde_fence_is_supported() -> None:
    soup = _render(
        """
        ~~~yaml table
        columns: [A, B]
        rows:
          - [x, 1]
        ~~~
        """
    )
    assert soup.find("table") is not None


def test_multiple_fences_in_one_document() -> None:
    soup = _render(
        """
        ```yaml table
        columns: [A, B]
        rows: [[x, 1]]
        ```

        Paragraphe intermédiaire.

        ```yaml table
        columns: [C, D]
        rows: [[y, 2]]
        ```
        """
    )
    tables = soup.find_all("table")
    assert len(tables) == 2
    paragraphs = soup.find_all("p")
    assert any("Paragraphe" in p.get_text() for p in paragraphs)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_invalid_yaml_renders_error_admonition() -> None:
    soup = _render(
        """
        ```yaml table
        columns: [A, B]
        rows:
          - [x, 1, 2]   # too many cells
        ```
        """
    )
    error = soup.find("div", class_="ts-table-error")
    assert error is not None
    assert "extra cell" in error.get_text() or "expected" in error.get_text()
    # The failing fence did not produce a real <table>.
    assert soup.find("table") is None


def test_unknown_named_column_surfaces_in_error_block() -> None:
    soup = _render(
        """
        ```yaml table
        columns:
          - Unité
          - name: Actuel
            columns: [S1, S2]
        rows:
          - Info 1: {Acutel: [6]}
        ```
        """
    )
    error = soup.find("div", class_="ts-table-error")
    assert error is not None
    assert "unknown column" in error.get_text()


# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------


def test_unclosed_fence_is_left_alone() -> None:
    # Without a closing fence, Python-Markdown handles it as inline code or a
    # malformed fenced block; our preprocessor must not greedily swallow it.
    soup = _render(
        """
        ```yaml table
        columns: [A, B]
        rows: [[x, 1]]

        Paragraph that is outside any fence.
        """
    )
    assert soup.find("table") is None


def test_non_yaml_table_fence_is_ignored() -> None:
    soup = _render(
        """
        ```yaml
        not a table: true
        ```
        """
    )
    # Generic yaml fence → not captured → no <table> element emitted.
    assert soup.find("table") is None


# ---------------------------------------------------------------------------
# `Table: caption` on standard Markdown tables
# ---------------------------------------------------------------------------


def test_standard_markdown_table_gets_caption_from_caption_line() -> None:
    soup = _render_with_tables(
        """
        Table: Répartition actuelle

        | Orientation | S1 | S2 |
        | ----------- | -- | -- |
        | SE          | 35 | 38 |
        """
    )
    # No figure wrapper: the caption is attached directly to the table so the
    # yaml-table and legacy renderers pick it up without special-casing.
    assert soup.find("figure") is None
    table = soup.find("table")
    assert table is not None
    caption = table.find("caption")
    assert caption is not None
    assert caption.get_text(strip=True) == "Répartition actuelle"
    # The "Table:" line must not survive as a stray paragraph.
    assert "Table:" not in soup.get_text()


def test_standard_markdown_table_caption_with_label() -> None:
    soup = _render_with_tables(
        """
        Table: Stocks {#tbl:stocks}

        | A | B |
        | - | - |
        | x | 1 |
        """
    )
    assert soup.find("figure") is None
    table = soup.find("table")
    assert table is not None
    assert table.get("id") == "tbl:stocks"
    assert table.find("caption").get_text(strip=True) == "Stocks"


def test_standalone_caption_without_following_table_is_left_alone() -> None:
    # A "Table: ..." line not followed by a table must keep its paragraph so
    # the user sees something is off; we don't silently drop text.
    soup = _render_with_tables(
        """
        Table: No table follows here

        Just a paragraph.
        """
    )
    assert soup.find("figure") is None
    assert "No table follows here" in soup.get_text()


def test_paragraph_between_caption_and_table_breaks_the_pair() -> None:
    soup = _render_with_tables(
        """
        Table: Unrelated caption

        A paragraph interrupts the pairing.

        | A | B |
        | - | - |
        | x | 1 |
        """
    )
    # The intervening paragraph means the caption shouldn't attach to the table.
    assert soup.find("figure") is None
    # The table still renders as a standalone markdown table.
    assert soup.find("table") is not None


# ---------------------------------------------------------------------------
# `yaml table-config` block: applies layout to a plain Markdown table
# ---------------------------------------------------------------------------


def test_table_config_block_marks_preceding_table_for_yaml_renderer() -> None:
    soup = _render_with_tables(
        """
        | A | B | C |
        | - | - | - |
        | 1 | 2 | 3 |

        ```yaml table-config
        columns:
          - {align: left}
          - {align: right}
          - {align: justify, width: X}
        ```
        """
    )
    table = soup.find("table")
    assert table is not None
    assert table.get("data-ts-table") == "1"
    assert table.get("data-ts-env") == "tabularx"
    assert table.get("data-ts-colspec") == "lrX"
    assert table.get("data-ts-width") == r"\linewidth"
    # The marker element itself is consumed.
    assert soup.find("texsmith-table-config") is None


def test_table_config_block_caption_pairs_with_plain_table() -> None:
    soup = _render_with_tables(
        """
        Table: Demo {#tbl:demo}

        | A | B |
        | - | - |
        | x | 1 |

        ```yaml table-config
        columns:
          - {align: left}
          - {align: right, width: X}
        ```
        """
    )
    assert soup.find("figure") is None
    table = soup.find("table")
    assert table is not None
    assert table.get("id") == "tbl:demo"
    assert table.find("caption").get_text(strip=True) == "Demo"
    # Config binds to the table regardless of the caption.
    assert table.get("data-ts-table") == "1"
    colspec = table.get("data-ts-colspec")
    assert colspec.startswith("l")
    assert "X" in colspec
    assert r"\raggedleft\arraybackslash" in colspec


def test_table_config_block_invalid_yaml_renders_error_admonition() -> None:
    soup = _render_with_tables(
        """
        | A | B |
        | - | - |
        | x | 1 |

        ```yaml table-config
        columns:
          - {align: diagonal}
        ```
        """
    )
    error = soup.find("div", class_="ts-table-error")
    assert error is not None
    assert "invalid align" in error.get_text()


def test_multiple_table_config_blocks_survive_superfences() -> None:
    """Regression: with ``pymdownx.superfences`` in the pipeline, two adjacent
    ``yaml table-config`` blocks used to be misparsed.

    Superfences sees ``table-config`` as an unrecognised info string and
    abandons the opening fence, then reads the next bare ```````
    as the *opening* of a new fenced block — swallowing every line up to the
    next fence pair. The first config never bound to its table, and a huge
    chunk of intermediate content was rendered as a code block.

    The :class:`_TableConfigPreprocessor` consumes the fence before
    superfences can see it, so both configs now bind to their respective
    tables.
    """
    md = Markdown(extensions=["tables", "pymdownx.superfences", YamlTableExtension()])
    src = textwrap.dedent(
        """
        | A | B | C | D |
        | - | - | - | - |
        | 1 | 2 | 3 | 4 |

        ```yaml table-config
        columns: [{align: left}, {align: right}, {width: auto}, {align: right}]
        ```

        Some text in between.

        | E | F | G | H | I |
        | - | - | - | - | - |
        | 1 | 2 | 3 | 4 | 5 |

        ```yaml table-config
        columns: [{align: left}, {align: right}, {width: auto}, {align: left}, {align: right}]
        ```
        """
    ).strip("\n")
    soup = BeautifulSoup(md.convert(src), "html.parser")

    tables = soup.find_all("table")
    assert len(tables) == 2
    assert tables[0].get("data-ts-colspec") == "lr>{\\raggedright\\arraybackslash}Xr"
    assert tables[1].get("data-ts-colspec") == "lr>{\\raggedright\\arraybackslash}Xlr"
    # No leftover code blocks from the misparse.
    assert soup.find("pre") is None
    assert soup.find("code") is None


def test_table_config_block_without_table_is_dropped_silently() -> None:
    soup = _render_with_tables(
        """
        Just a paragraph.

        ```yaml table-config
        columns:
          - {align: left}
        ```
        """
    )
    # No table to bind to; the marker is dropped, and the document still
    # renders the paragraph normally.
    assert soup.find("texsmith-table-config") is None
    assert "Just a paragraph" in soup.get_text()


# ---------------------------------------------------------------------------
# Plain Markdown table: dash-only row → separator
# ---------------------------------------------------------------------------


def test_dash_only_body_row_becomes_separator() -> None:
    soup = _render_with_tables(
        """
        | Cours     | Sem. |
        | --------- | ---- |
        | Info1     | S1   |
        | --------- | ---- |
        | **Total** | S1-S3|
        """
    )
    table = soup.find("table")
    assert table is not None
    body = table.find("tbody")
    rows = body.find_all("tr")
    assert len(rows) == 3
    sep = rows[1]
    assert sep.get("data-ts-role") == "separator"
    cells = sep.find_all(["td", "th"])
    assert len(cells) == 1
    assert cells[0].get("colspan") == "2"
    assert cells[0].get_text(strip=True) == ""
    # Surrounding rows are untouched.
    assert rows[0].find_all("td")[0].get_text(strip=True) == "Info1"
    assert rows[2].find_all("td")[0].get_text(strip=True) == "Total"


def test_dash_row_must_have_three_or_more_dashes_in_every_cell() -> None:
    soup = _render_with_tables(
        """
        | A | B |
        | - | - |
        | - | - |
        | x | y |
        """
    )
    table = soup.find("table")
    body = table.find("tbody")
    rows = body.find_all("tr")
    # First body row has only single-dash cells: NOT a separator.
    assert rows[0].get("data-ts-role") is None
    cells = rows[0].find_all(["td", "th"])
    assert [c.get_text(strip=True) for c in cells] == ["-", "-"]


def test_partial_dash_row_is_not_a_separator() -> None:
    soup = _render_with_tables(
        """
        | A | B |
        | - | - |
        | --- | data |
        | foo | bar |
        """
    )
    table = soup.find("table")
    body = table.find("tbody")
    rows = body.find_all("tr")
    # Second cell is non-dash content, so the row stays a regular data row.
    assert rows[0].get("data-ts-role") is None
    cells = rows[0].find_all(["td", "th"])
    assert [c.get_text(strip=True) for c in cells] == ["---", "data"]


def test_dash_row_inside_yaml_tables_is_unaffected() -> None:
    # In yaml tables, separators are declared explicitly; literal "---" inside
    # a string cell must round-trip as plain text.
    soup = _render(
        """
        ```yaml table
        columns: [A, B]
        rows:
          - ["---", "value"]
        ```
        """
    )
    table = soup.find("table")
    body = table.find("tbody")
    rows = body.find_all("tr")
    assert all(row.get("data-ts-role") != "separator" for row in rows)


def test_grouped_headers_round_trip_through_markdown() -> None:
    soup = _render(
        """
        ```yaml table
        columns:
          - Unité
          - name: 2024
            columns: [Q1, Q2]
        rows:
          - [x, [1, 2]]
        ```
        """
    )
    table = soup.find("table")
    assert table is not None
    thead_rows = table.find("thead").find_all("tr")
    assert len(thead_rows) == 2
