"""Tests for the yaml-table LaTeX renderer."""

from __future__ import annotations

import textwrap

from markdown import Markdown
import yaml

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.extensions.tables import (
    YamlTableExtension,
    parse_table,
    render_table_html,
)


def _latex_from_yaml(
    src: str,
    *,
    caption: str | None = None,
    label: str | None = None,
) -> str:
    table = parse_table(yaml.safe_load(textwrap.dedent(src)))
    html = render_table_html(table, caption=caption, label=label)
    return LaTeXRenderer().render(html)


def _latex_from_markdown(src: str) -> str:
    md = Markdown(extensions=["attr_list", "tables", YamlTableExtension()])
    html = md.convert(textwrap.dedent(src).strip("\n"))
    return LaTeXRenderer().render(html)


# ---------------------------------------------------------------------------
# Environments and wrappers
# ---------------------------------------------------------------------------


def test_simple_table_renders_tabular() -> None:
    latex = _latex_from_yaml(
        """
        columns: [Produit, Genève]
        rows:
          - [Pommes, 120]
        """
    )
    assert r"\begin{tabular}{ll}" in latex
    assert r"\toprule" in latex
    assert r"Produit & Genève \\" in latex
    assert r"Pommes & 120 \\" in latex
    assert r"\bottomrule" in latex
    assert r"\end{tabular}" in latex


def test_fixed_width_renders_tabularx_with_linewidth() -> None:
    latex = _latex_from_yaml(
        """
        table: {width: 100%}
        columns:
          - A
          - {name: B, align: j}
        rows:
          - [x, "phrase"]
        """
    )
    assert r"\begin{tabularx}{\linewidth}" in latex
    assert "X" in latex


def test_caption_and_label_emit_inside_table_float() -> None:
    latex = _latex_from_yaml(
        """
        columns: [A, B]
        rows: [[x, 1]]
        """,
        caption="Ma légende",
        label="tbl:foo",
    )
    assert r"\begin{table}[H]" in latex
    assert r"\label{tbl:foo}" in latex
    assert r"\caption{Ma légende}" in latex
    # 0.5em breathing room between caption and the tabular body.
    assert r"\vspace{0.5em}" in latex
    assert r"\end{table}" in latex


def test_no_vspace_when_caption_is_absent() -> None:
    latex = _latex_from_yaml(
        """
        columns: [A, B]
        rows: [[x, 1]]
        """
    )
    assert r"\vspace{0.5em}" not in latex


def test_no_caption_wraps_in_center() -> None:
    latex = _latex_from_yaml(
        """
        columns: [A, B]
        rows: [[x, 1]]
        """
    )
    assert r"\begin{center}" in latex
    assert r"\end{center}" in latex
    assert r"\begin{table}" not in latex


# ---------------------------------------------------------------------------
# Multirow / multicolumn
# ---------------------------------------------------------------------------


def test_multirow_body_cell_uses_multirow_and_leaves_ghost_row() -> None:
    latex = _latex_from_yaml(
        """
        columns: [Projet, Évaluateur, Note]
        rows:
          - [Alpha, {value: Marie, rows: 2}, 17]
          - [Beta, ~, 14]
          - [Gamma, Paul, 12]
        """
    )
    assert r"\multirow{2}{*}{Marie}" in latex
    # Absorbed row: row-label then empty slot (single column rowspan) then value.
    assert "Beta &  & 14 \\\\" in latex
    assert "Gamma & Paul & 12 \\\\" in latex


def test_multicolumn_body_cell_uses_multicolumn() -> None:
    latex = _latex_from_yaml(
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
    assert r"\multicolumn{4}{c}{545 k€}" in latex


def test_rectangle_span_composes_multicolumn_and_multirow() -> None:
    latex = _latex_from_yaml(
        """
        columns: [A, B, C, D]
        rows:
          - [r1, {value: Bloc, rows: 2, cols: 3, align: c}]
          - [r2, ~, ~, ~]
          - [r3, x, y, z]
        """
    )
    assert r"\multicolumn{3}{c}{\multirow{2}{*}{Bloc}}" in latex
    # Absorbed row emits the ghost multicolumn to preserve column structure.
    assert r"r2 & \multicolumn{3}{c}{} \\" in latex


# ---------------------------------------------------------------------------
# Grouped headers / cmidrule
# ---------------------------------------------------------------------------


def test_grouped_header_emits_cmidrule() -> None:
    latex = _latex_from_yaml(
        """
        columns:
          - Unité
          - name: 2024
            columns: [Q1, Q2]
        rows:
          - [x, [1, 2]]
        """
    )
    assert r"\multicolumn{2}{c}{2024}" in latex
    assert r"\cmidrule(lr){2-3}" in latex


def test_three_level_header_emits_cmidrules_between_levels() -> None:
    latex = _latex_from_yaml(
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
    # Level 0 spans the whole 2024 group (cols 2..4).
    assert r"\cmidrule(lr){2-4}" in latex
    # Level 1 has Q1 (cols 2..3) and Q2 (col 4 alone → no cmidrule needed).
    assert r"\cmidrule(lr){2-3}" in latex


# ---------------------------------------------------------------------------
# Separators and footer
# ---------------------------------------------------------------------------


def test_separator_with_label_uses_multicolumn_italic() -> None:
    latex = _latex_from_yaml(
        """
        columns: [A, B, C]
        rows:
          - [x, 1, 2]
          - separator: {label: "Rupture"}
          - [y, 3, 4]
        """
    )
    assert r"\midrule" in latex
    assert r"\multicolumn{3}{l}{\textit{Rupture}}" in latex


def test_plain_separator_emits_midrule_only() -> None:
    latex = _latex_from_yaml(
        """
        columns: [A, B]
        rows:
          - [x, 1]
          - separator: true
          - [y, 2]
        """
    )
    assert r"\midrule" in latex
    assert r"\textit" not in latex


def test_footer_is_separated_by_midrule() -> None:
    latex = _latex_from_yaml(
        """
        columns: [A, B]
        rows: [[x, 1]]
        footer:
          - [Total, 99]
        """
    )
    # Footer block appears after a \midrule and before \bottomrule.
    assert r"Total & 99 \\" in latex
    after_body = latex.split("x & 1 \\\\", 1)[1]
    assert after_body.count(r"\midrule") >= 1
    assert r"\bottomrule" in after_body


# ---------------------------------------------------------------------------
# End-to-end from Markdown
# ---------------------------------------------------------------------------


def test_end_to_end_markdown_to_latex_attaches_caption() -> None:
    latex = _latex_from_markdown(
        """
        Table: Stocks par entrepôt {#tbl:stocks}

        ```yaml table
        columns: [Produit, Genève]
        rows:
          - [Pommes, 120]
        ```
        """
    )
    assert r"\begin{table}[H]" in latex
    assert r"\label{tbl:stocks}" in latex
    assert r"\caption{Stocks par entrepôt}" in latex


def test_markdown_table_with_yaml_table_config_uses_tabularx() -> None:
    latex = _latex_from_markdown(
        """
        Table: Inventaire {#tbl:inv}

        | Abbr | Sem | Nom du cours       | Or.  | Charge |
        | ---- | --- | ------------------ | ---- | ------ |
        | I1   | S1  | Informatique 1     | EMA  | 120    |
        | I2   | S2  | Informatique 2     | EMA  | 100    |

        ```yaml table-config
        columns:
          - {align: left}
          - {align: right}
          - {align: justify, width: X}
          - {align: left}
          - {align: right}
        ```
        """
    )
    assert r"\begin{tabularx}{\linewidth}{lrXlr}" in latex
    assert r"\caption{Inventaire}" in latex
    assert r"\label{tbl:inv}" in latex


def test_plain_markdown_table_still_goes_through_legacy_handler() -> None:
    # A normal Markdown table must not be captured by the yaml-table handler.
    md = Markdown(extensions=["tables"])
    html = md.convert("| A | B |\n|---|---|\n| x | 1 |\n")
    latex = LaTeXRenderer().render(html)
    # The legacy renderer uses tabularx with raggedright by default.
    assert r"\begin{tabularx}" in latex
    assert "data-ts-table" not in latex


def test_latex_escaping_applied_to_cell_values() -> None:
    latex = _latex_from_yaml(
        """
        columns: [Produit, Description]
        rows:
          - [Pommes, "50% remise"]
        """
    )
    # % is a LaTeX comment marker — it must be escaped.
    assert r"50\%" in latex or r"50{\%}" in latex
