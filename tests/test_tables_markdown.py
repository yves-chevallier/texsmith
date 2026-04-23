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
