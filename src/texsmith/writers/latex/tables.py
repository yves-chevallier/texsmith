"""Table emission for the LaTeX backend.

Reproduces the two legacy table paths from a single IR :class:`~texsmith.ir.Table`:

* plain GFM tables → the ``table.tex`` partial (``tabularx`` with
  ``>{\\raggedright}X`` columns, bold header row, ``\\midrule`` separators);
* yaml / ``data-ts`` tables → the ``yaml_table.tex`` partial via the rich
  layout assembled from the validated tables-schema model (custom colspec,
  ``tabular``/``tabularx``/``longtable``, multirow/multicolumn, ``\\cmidrule``,
  labelled separators).

Table *shape* (columns, spans, separators, colspec) comes from ``node.model``
(the validated SSOT); rendered cell *content* comes from ``node.cells`` (inline
IR, in HTML document order), so cell markup (bold/code/links/escaping) survives
exactly as the legacy POST-phase ``get_text()`` produced it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from texsmith.extensions.tables import schema as tbl
from texsmith.ir import nodes as ir


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

    from .writer import LaTeXWriter


_ALIGN_WORD = {"l": "left", "c": "center", "r": "right", "j": "left"}


def render_table(writer: LaTeXWriter, node: ir.Table) -> str:
    """Render an IR table to LaTeX (yaml path if marked, else plain GFM)."""
    if _is_yaml_table(node):
        return _render_yaml_table(writer, node)
    return _render_plain_table(writer, node)


def _is_yaml_table(node: ir.Table) -> bool:
    return bool(getattr(node, "env", "") or getattr(node, "colspec", ""))


def _rendered_cells(writer: LaTeXWriter, node: ir.Table) -> list[str]:
    """Render each cell's inline content (document order) to LaTeX strings."""
    return [writer.render_inlines(cell).strip() for cell in node.cells]


# --------------------------------------------------------------------------- #
# Plain GFM tables → table.tex
# --------------------------------------------------------------------------- #


def _render_plain_table(writer: LaTeXWriter, node: ir.Table) -> str:
    model = node.model
    leaves = _leaf_columns(model.columns)
    n_cols = len(leaves)
    columns = [_ALIGN_WORD.get((leaf.align or "l"), "left") for leaf in leaves]

    cells = _rendered_cells(writer, node)
    cursor = 0
    # Header row: one rendered cell per leaf column (in document order).
    header = cells[cursor : cursor + n_cols]
    cursor += n_cols

    rows: list[list[str] | None] = [header]
    for row in model.rows:
        if isinstance(row, tbl.Separator):
            rows.append(None)
            continue
        width = 1 + len(row.cells)
        rows.append(cells[cursor : cursor + width])
        cursor += width

    caption = writer.render_inlines(node.caption).strip() if node.caption else None
    is_large = _is_large(rows)
    latex = writer.state.formatter.render_template(
        "table",
        columns=columns,
        rows=rows,
        caption=caption or None,
        label=node.label or None,
        is_large=is_large,
    )
    return latex.rstrip() + "\n"


def _is_large(rows: list[list[str] | None]) -> bool:
    for row in rows:
        if row is None:
            continue
        stripped = "".join(re.sub(r"\\href\{[^\}]+?\}|\\\w{3,}|[\{\}|]", "", col) for col in row)
        if len(stripped) > 50:
            return True
    return False


def _leaf_columns(columns: Sequence[tbl.Column]) -> list[tbl.LeafColumn]:
    leaves: list[tbl.LeafColumn] = []
    for column in columns:
        leaves.extend(tbl.column_leaves(column))
    return leaves


# --------------------------------------------------------------------------- #
# yaml tables → yaml_table.tex
# --------------------------------------------------------------------------- #


def _in_separator_row(cell: object) -> bool:
    from texsmith.extensions.tables.constants import TableAttr

    row = cell.find_parent("tr")  # type: ignore[attr-defined]
    return row is not None and row.get(TableAttr.ROLE) == "separator"


def _render_yaml_table(writer: LaTeXWriter, node: ir.Table) -> str:
    import xml.etree.ElementTree as ET

    from bs4 import BeautifulSoup
    from bs4.element import Tag

    from texsmith.extensions.tables.html import render_table_html
    from texsmith.extensions.tables.renderer import (
        _count_colspec_slots,
        _render_header,
        _render_section,
    )

    # Regenerate the canonical data-ts HTML for the shape, then inject the
    # rendered cell content (document order) so the existing assembler — which
    # reads ``cell.get_text()`` — emits the writer-rendered inline LaTeX.
    element = render_table_html(node.model)
    html = ET.tostring(element, encoding="unicode") if not isinstance(element, str) else element
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not isinstance(table, Tag):  # pragma: no cover - defensive
        return ""

    rendered = _rendered_cells(writer, node)
    # ``node.cells`` excludes caption and separator-row cells, in document
    # order — align the injection to the same set.
    html_cells = [
        c
        for c in table.find_all(["th", "td"])
        if c.find_parent("caption") is None and not _in_separator_row(c)
    ]
    for cell, content in zip(html_cells, rendered, strict=False):
        cell.clear()
        cell.append(content)

    colspec = node.colspec
    total_cols = _count_colspec_slots(colspec)
    thead = table.find("thead")
    tbody = table.find("tbody")
    tfoot = table.find("tfoot")
    header_tex = _render_header(thead, total_cols) if thead else ""
    body_tex = _render_section(tbody, total_cols)
    footer_tex = _render_section(tfoot, total_cols)

    caption = writer.render_inlines(node.caption).strip() if node.caption else None
    latex = writer.state.formatter.render_template(
        "yaml_table",
        env=node.env or "tabular",
        colspec=colspec,
        width=node.width or "",
        placement=node.placement or None,
        caption=caption or None,
        label=node.label or None,
        header=header_tex,
        body=body_tex,
        footer=footer_tex,
    )
    return latex.rstrip() + "\n"


__all__ = ["render_table"]
