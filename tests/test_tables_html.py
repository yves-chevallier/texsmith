"""Tests for the yaml-table HTML serialiser."""

from __future__ import annotations

import textwrap

from bs4 import BeautifulSoup
import yaml

from texsmith.extensions.tables import parse_table, render_error_html, render_table_html


def _soup(src: str, *, caption: str | None = None, label: str | None = None) -> BeautifulSoup:
    table = parse_table(yaml.safe_load(textwrap.dedent(src)))
    html = render_table_html(table, caption=caption, label=label)
    return BeautifulSoup(html, "html.parser")


def _rows(soup: BeautifulSoup, role: str) -> list:
    return soup.find_all("tr", attrs={"data-ts-role": role})


# ---------------------------------------------------------------------------
# Table-level metadata
# ---------------------------------------------------------------------------


def test_simple_table_carries_env_and_colspec() -> None:
    soup = _soup(
        """
        columns: [Produit, Genève, Lausanne]
        rows:
          - [Pommes, 120, 80]
        """
    )
    table = soup.find("table")
    assert table is not None
    assert table.get("data-ts-table") == "1"
    assert table.get("data-ts-env") == "tabular"
    assert table.get("data-ts-colspec") == "lll"
    assert table.get("data-ts-width") is None


def test_fixed_width_table_exposes_total_width() -> None:
    soup = _soup(
        """
        table: {width: 100%, placement: "H"}
        columns:
          - A
          - {name: B, align: j}
        rows:
          - [x, "bla"]
        """
    )
    table = soup.find("table")
    assert table.get("data-ts-env") == "tabularx"
    assert table.get("data-ts-width") == r"\linewidth"
    assert table.get("data-ts-placement") == "H"


def test_caption_and_label_are_attached() -> None:
    soup = _soup(
        """
        columns: [A, B]
        rows: [[x, 1]]
        """,
        caption="Ma légende",
        label="tbl:foo",
    )
    table = soup.find("table")
    assert table.get("id") == "tbl:foo"
    caption = table.find("caption")
    assert caption is not None
    assert caption.get_text(strip=True) == "Ma légende"


# ---------------------------------------------------------------------------
# Header structure
# ---------------------------------------------------------------------------


def test_flat_header_uses_one_row() -> None:
    soup = _soup(
        """
        columns: [A, B, C]
        rows: [[x, 1, 2]]
        """
    )
    headers = _rows(soup, "header")
    assert len(headers) == 1
    cells = headers[0].find_all("th")
    assert [c.get_text(strip=True) for c in cells] == ["A", "B", "C"]


def test_grouped_header_emits_two_rows_with_spans() -> None:
    soup = _soup(
        """
        columns:
          - Unité
          - name: 2024
            columns: [Q1, Q2]
        rows:
          - [x, [1, 2]]
        """
    )
    headers = _rows(soup, "header")
    assert len(headers) == 2
    # Level 0: "Unité" spans both rows; "2024" spans two sub-columns.
    top = headers[0].find_all("th")
    assert top[0].get_text(strip=True) == "Unité"
    assert top[0].get("rowspan") == "2"
    assert top[1].get_text(strip=True) == "2024"
    assert top[1].get("colspan") == "2"
    # Level 1: the two leaves.
    bottom = headers[1].find_all("th")
    assert [c.get_text(strip=True) for c in bottom] == ["Q1", "Q2"]


def test_three_level_header() -> None:
    soup = _soup(
        """
        columns:
          - Produit
          - name: 2024
            columns:
              - name: Q1
                columns: [Jan, Fév]
              - name: Q2
                columns: [Avr]
        rows:
          - [A, [1, 2, 3]]
        """
    )
    headers = _rows(soup, "header")
    assert len(headers) == 3
    # Leaf row has all three quarters' months.
    leaves = [c.get_text(strip=True) for c in headers[2].find_all("th")]
    assert leaves == ["Jan", "Fév", "Avr"]


# ---------------------------------------------------------------------------
# Body / footer
# ---------------------------------------------------------------------------


def test_body_row_label_is_th_scope_row() -> None:
    soup = _soup(
        """
        columns: [A, B]
        rows: [[Pommes, 120]]
        """
    )
    row = _rows(soup, "body")[0]
    label = row.find("th", attrs={"scope": "row"})
    assert label is not None
    assert label.get_text(strip=True) == "Pommes"
    cells = row.find_all("td")
    assert [c.get_text(strip=True) for c in cells] == ["120"]


def test_separator_renders_as_labelled_row() -> None:
    soup = _soup(
        """
        columns: [A, B, C]
        rows:
          - [x, 1, 2]
          - separator: {label: "Section"}
          - [y, 3, 4]
        """
    )
    seps = _rows(soup, "separator")
    assert len(seps) == 1
    cell = seps[0].find("td")
    assert cell.get("colspan") == "3"
    assert cell.get_text(strip=True) == "Section"
    assert seps[0].get("data-ts-sep-label") == "Section"


def test_footer_is_rendered_in_tfoot() -> None:
    soup = _soup(
        """
        columns: [A, B]
        rows: [[x, 1]]
        footer:
          - [Total, 99]
        """
    )
    tfoot = soup.find("tfoot")
    assert tfoot is not None
    row = tfoot.find("tr", attrs={"data-ts-role": "footer"})
    assert row is not None
    assert row.find("th").get_text(strip=True) == "Total"


def test_empty_cell_carries_data_attr() -> None:
    soup = _soup(
        """
        columns: [A, B]
        rows: [[x, ~]]
        """
    )
    cell = _rows(soup, "body")[0].find("td")
    assert cell.get("data-ts-empty") == "1"
    assert cell.get_text(strip=True) == ""


# ---------------------------------------------------------------------------
# Multirow / multicolumn
# ---------------------------------------------------------------------------


def test_multirow_cell_emits_rowspan_once() -> None:
    soup = _soup(
        """
        columns: [Projet, Évaluateur, Note]
        rows:
          - [Alpha, {value: Marie, rows: 2}, 17]
          - [Beta, ~, 14]
          - [Gamma, Paul, 12]
        """
    )
    bodies = _rows(soup, "body")
    # Row 1: origin with rowspan=2 + Note=17.
    alpha_cells = bodies[0].find_all("td")
    assert len(alpha_cells) == 2
    assert alpha_cells[0].get("rowspan") == "2"
    assert alpha_cells[0].get_text(strip=True) == "Marie"
    # Row 2: the absorbed cell is NOT emitted; only the Note cell is.
    beta_cells = bodies[1].find_all("td")
    assert len(beta_cells) == 1
    assert beta_cells[0].get_text(strip=True) == "14"


def test_multicol_cell_emits_colspan_and_skips_absorbed() -> None:
    soup = _soup(
        """
        columns:
          - Unité
          - name: 2024
            columns: [Q1, Q2, Q3, Q4]
        rows:
          - [Ventes, [120, 130, 150, 170]]
          - [Total, {value: "545 k€", cols: 4, align: c}]
        """
    )
    total_row = _rows(soup, "body")[1]
    cells = total_row.find_all("td")
    assert len(cells) == 1
    assert cells[0].get("colspan") == "4"
    assert cells[0].get("data-ts-align") == "c"
    assert cells[0].get_text(strip=True) == "545 k€"


def test_mixed_rectangle_emits_single_origin_with_both_spans() -> None:
    soup = _soup(
        """
        columns: [A, B, C, D]
        rows:
          - [r1, {value: "Bloc", rows: 2, cols: 3, align: c}]
          - [r2, ~, ~, ~]
          - [r3, x, y, z]
        """
    )
    bodies = _rows(soup, "body")
    origin = bodies[0].find_all("td")[0]
    assert origin.get("rowspan") == "2"
    assert origin.get("colspan") == "3"
    # r2 has no data cells, only the row label.
    assert bodies[1].find_all("td") == []


# ---------------------------------------------------------------------------
# Error rendering
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Headerless tables
# ---------------------------------------------------------------------------


def test_headerless_table_omits_thead() -> None:
    soup = _soup(
        """
        table: {width: 100%}
        columns:
          - align: l
            width: 40%
          - align: j
        rows:
          - ["Project codename", "Northwind"]
          - ["Workload estimate", "175 hours"]
        """
    )
    table = soup.find("table")
    assert table is not None
    assert table.find("thead") is None
    # Body rows still expose their row label as a scoped <th>.
    body_rows = _rows(soup, "body")
    assert len(body_rows) == 2
    assert body_rows[0].find("th", attrs={"scope": "row"}).get_text(strip=True) == "Project codename"


def test_partially_named_columns_keep_thead_with_blank_cells() -> None:
    soup = _soup(
        """
        columns:
          - name: Key
          - align: r
        rows:
          - [Alpha, 1]
        """
    )
    headers = _rows(soup, "header")
    assert len(headers) == 1
    cells = headers[0].find_all("th")
    assert [c.get_text(strip=True) for c in cells] == ["Key", ""]


def test_render_error_html_produces_admonition_with_code_block() -> None:
    html = render_error_html("missing 'columns'")
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find("div")
    assert div is not None
    classes = div.get("class", [])
    assert "admonition" in classes
    assert "error" in classes
    assert "ts-table-error" in classes
    # Title lives in its own paragraph; message is wrapped in <pre><code>.
    title = div.find("p", class_="admonition-title")
    assert title is not None
    code = div.find("code")
    assert code is not None
    assert "missing 'columns'" in code.get_text()
