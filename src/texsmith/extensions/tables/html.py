"""Render a validated YAML :class:`Table` into semantic HTML.

The resulting ``<table>`` carries everything the LaTeX renderer needs to build
the appropriate ``tabular`` / ``tabularx`` / ``longtable`` output:

* table-level metadata lives in ``data-ts-*`` attributes on the ``<table>``;
* headers are split across as many ``<tr>`` rows inside ``<thead>`` as the
  header hierarchy requires, with ``colspan`` / ``rowspan`` already computed;
* body and footer rows go to ``<tbody>`` / ``<tfoot>``; separator rows are
  marked with ``data-ts-role="separator"``;
* multirow / multicolumn cells use the native HTML attributes so the output
  previews correctly in a browser, and absorbed positions are simply omitted.
"""

from __future__ import annotations

import html as html_lib
import re
from xml.etree import ElementTree as ET

import markdown as _md

from .constants import TableAttr
from .layout import TableLayout, compute_layout
from .schema import (
    Column,
    ColumnGroup,
    LeafCell,
    LeafColumn,
    LeafMatrix,
    Separator,
    Table,
    build_matrix,
    header_depth,
    leaf_count,
    total_leaves,
)


# ---------------------------------------------------------------------------
# Header construction
# ---------------------------------------------------------------------------


def _header_matrix(columns: list[Column]) -> list[list[dict[str, object]]]:
    """Return a level-by-level matrix of header cells with spans computed."""
    depth = max((header_depth(c) for c in columns), default=1)
    rows: list[list[dict[str, object]]] = [[] for _ in range(depth)]

    def walk(col: Column, level: int) -> None:
        if isinstance(col, LeafColumn):
            rows[level].append(
                {
                    "text": col.name or "",
                    "colspan": 1,
                    "rowspan": depth - level,
                }
            )
            return
        rows[level].append(
            {
                "text": col.name or "",
                "colspan": leaf_count(col),
                "rowspan": 1,
            }
        )
        for child in col.columns:
            walk(child, level + 1)

    for col in columns:
        walk(col, 0)
    return rows


def _has_named_column(columns: list[Column]) -> bool:
    """Return ``True`` when any column or column group carries a name."""
    for col in columns:
        if col.name:
            return True
        if isinstance(col, ColumnGroup) and _has_named_column(col.columns):
            return True
    return False


# ---------------------------------------------------------------------------
# Cell formatting
# ---------------------------------------------------------------------------


def _format_scalar(value: object) -> str:
    """Render a leaf value as its user-facing string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


_INLINE_MARKER_RE = re.compile(r"[`*_~\[]")
_P_WRAP_RE = re.compile(r"\A<p>(.*)</p>\Z", flags=re.DOTALL)
_INLINE_MD: _md.Markdown | None = None


def _inline_markdown_to_html(text: str) -> str:
    """Convert inline markdown syntax in ``text`` to an HTML fragment.

    The leading ``<p>...</p>`` wrapper that python-markdown emits for any
    standalone text is stripped so the result can be spliced back into a
    ``<td>`` / ``<th>`` that already owns the paragraph-level context.
    """
    global _INLINE_MD
    if _INLINE_MD is None:
        _INLINE_MD = _md.Markdown(extensions=[], output_format="html")
    _INLINE_MD.reset()
    html = _INLINE_MD.convert(text).strip()
    match = _P_WRAP_RE.match(html)
    if match:
        return match.group(1)
    return html


def _set_inline_content(element: ET.Element, text: str) -> None:
    """Populate ``element`` with ``text``, honouring inline markdown.

    Supports inline code (``\\`x\\```), emphasis (``*x*``, ``_x_``), strong
    (``**x**``), strikethrough and inline links — whatever python-markdown's
    default inline parser produces. The resulting nodes flow through the
    standard TeXSmith handler chain (``render_inline_code`` converts ``<code>``
    to ``\\texttt{…}`` etc.) so the LaTeX output picks them up automatically.

    Falls back to plain text assignment when no inline markers are detected
    or when the generated fragment cannot be parsed back as XML.
    """
    if not text:
        element.text = text
        return
    if _INLINE_MARKER_RE.search(text) is None:
        element.text = text
        return
    fragment = _inline_markdown_to_html(text)
    if "<" not in fragment:
        element.text = text
        return
    try:
        wrapped = ET.fromstring(f"<wrap>{fragment}</wrap>")
    except ET.ParseError:
        element.text = text
        return
    element.text = wrapped.text
    for child in wrapped:
        element.append(child)


# ---------------------------------------------------------------------------
# HTML element helpers
# ---------------------------------------------------------------------------


def _set_span_attrs(element: ET.Element, rows: int, cols: int) -> None:
    if rows > 1:
        element.set("rowspan", str(rows))
    if cols > 1:
        element.set("colspan", str(cols))


def _append_cell(
    parent: ET.Element,
    leaf: LeafCell,
    *,
    tag: str = "td",
) -> None:
    cell = ET.SubElement(parent, tag)
    _set_span_attrs(cell, leaf.rows, leaf.cols)
    if leaf.align is not None:
        cell.set(TableAttr.ALIGN, leaf.align)
    if leaf.value is None:
        cell.set(TableAttr.EMPTY, "1")
    _set_inline_content(cell, _format_scalar(leaf.value))


# ---------------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------------


def _render_header(
    thead: ET.Element,
    columns: list[Column],
) -> None:
    matrix = _header_matrix(columns)
    for level_cells in matrix:
        tr = ET.SubElement(thead, "tr")
        tr.set(TableAttr.ROLE, "header")
        for cell in level_cells:
            th = ET.SubElement(tr, "th", {"scope": "col"})
            _set_span_attrs(th, int(cell["rowspan"]), int(cell["colspan"]))
            _set_inline_content(th, str(cell["text"]))


def _render_data_row(
    parent: ET.Element,
    row_index: int,
    label: str,
    leaves: list[LeafCell],
    role: str,
) -> None:
    tr = ET.SubElement(parent, "tr")
    tr.set(TableAttr.ROLE, role)

    label_th = ET.SubElement(tr, "th", {"scope": "row"})
    _set_inline_content(label_th, label)

    for col_index, leaf in enumerate(leaves):
        if leaf.absorbed:
            continue
        # The cell is emitted at its origin position; its row/col span is
        # already carried on the LeafCell so rendering is a direct translation.
        if leaf.origin != (row_index, col_index):
            # Defensive: ``build_matrix`` always pins the origin to the
            # first occurrence; anything else is a bug in span placement.
            msg = f"inconsistent origin for cell at ({row_index}, {col_index}): {leaf.origin!r}"
            raise AssertionError(msg)
        _append_cell(tr, leaf)


def _render_separator_row(
    parent: ET.Element,
    separator: Separator,
    total_cols: int,
) -> None:
    tr = ET.SubElement(parent, "tr")
    tr.set(TableAttr.ROLE, "separator")
    if separator.double_rule:
        tr.set(TableAttr.RULE, "double")
    cell = ET.SubElement(tr, "td", {"colspan": str(total_cols)})
    if separator.label:
        tr.set(TableAttr.SEP_LABEL, separator.label)
        cell.text = separator.label


def _render_body_or_footer(
    parent: ET.Element,
    rows_matrix: list[list[LeafCell]],
    row_kinds: list[str],
    separators: list[Separator],
    data_labels: list[str],
    total_cols: int,
    role: str,
    starting_row_index: int,
) -> None:
    sep_cursor = 0
    data_cursor = 0
    for i, kind in enumerate(row_kinds):
        if kind == "separator":
            _render_separator_row(parent, separators[sep_cursor], total_cols)
            sep_cursor += 1
            continue
        _render_data_row(
            parent,
            row_index=starting_row_index + i,
            label=data_labels[data_cursor],
            leaves=rows_matrix[i],
            role=role,
        )
        data_cursor += 1


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_table_html(
    table: Table,
    *,
    caption: str | None = None,
    label: str | None = None,
) -> str:
    """Render ``table`` as a standalone ``<table>`` HTML string.

    ``caption`` is inserted as a ``<caption>`` child when provided. ``label``
    becomes the ``id`` attribute of the ``<table>``.
    """
    layout: TableLayout = compute_layout(table)
    matrix: LeafMatrix = build_matrix(table)
    total_cols = total_leaves(table.columns)

    root = ET.Element("table")
    root.set(TableAttr.TABLE, "1")
    root.set(TableAttr.ENV, layout.env)
    root.set(TableAttr.COLSPEC, layout.colspec)
    if layout.total_width_spec is not None:
        root.set(TableAttr.WIDTH, layout.total_width_spec)
    if layout.placement:
        root.set(TableAttr.PLACEMENT, layout.placement)
    if label:
        root.set("id", label)

    if caption:
        caption_el = ET.SubElement(root, "caption")
        _set_inline_content(caption_el, caption)

    if _has_named_column(table.columns):
        thead = ET.SubElement(root, "thead")
        _render_header(thead, table.columns)

    # Data-row labels are needed because the matrix only holds data leaves,
    # while the first column in the rendered table shows the row label.
    body_labels = [row.label for row in table.rows if not isinstance(row, Separator)]
    footer_labels = [row.label for row in table.footer if not isinstance(row, Separator)]

    tbody = ET.SubElement(root, "tbody")
    _render_body_or_footer(
        tbody,
        rows_matrix=matrix.body,
        row_kinds=matrix.body_row_kinds,
        separators=matrix.separators,
        data_labels=body_labels,
        total_cols=total_cols,
        role="body",
        starting_row_index=0,
    )

    if matrix.footer:
        tfoot = ET.SubElement(root, "tfoot")
        _render_body_or_footer(
            tfoot,
            rows_matrix=matrix.footer,
            row_kinds=matrix.footer_row_kinds,
            separators=matrix.footer_separators,
            data_labels=footer_labels,
            total_cols=total_cols,
            role="footer",
            starting_row_index=len(table.rows),
        )

    return ET.tostring(root, encoding="unicode", method="html")


def build_error_element(message: str, *, title: str = "YAML table error") -> ET.Element:
    """Build an admonition-shaped error element for a failed table parse.

    The message is wrapped in a ``<pre><code>`` block so multiline validator
    output keeps its formatting and stands out from regular prose. Returning
    a live ElementTree node lets callers either stash it as HTML (via
    :func:`render_error_html`) or append it straight into a tree processor's
    parent.
    """
    root = ET.Element("div", {"class": "admonition error ts-table-error"})
    title_el = ET.SubElement(root, "p", {"class": "admonition-title"})
    title_el.text = title
    pre = ET.SubElement(root, "pre")
    code = ET.SubElement(pre, "code")
    code.text = html_lib.unescape(message)
    return root


def render_error_html(message: str, *, title: str = "YAML table error") -> str:
    """Render an admonition-shaped error block as an HTML fragment."""
    return ET.tostring(build_error_element(message, title=title), encoding="unicode", method="html")


__all__ = ["build_error_element", "render_error_html", "render_table_html"]
