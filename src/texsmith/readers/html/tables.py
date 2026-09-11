"""HTML ``<table>`` → tables-schema reconstruction, and the schema → IR model map.

Two input shapes converge on one :class:`texsmith.extensions.tables.schema.Table`,
distinguished by the table extension's ``data-ts-table`` marker:

* **Rich tables** (``yaml table`` / ``yaml table-config``): the ``<table>`` is
  the exact output of :func:`texsmith.extensions.tables.html.render_table_html`
  — header levels, native ``colspan`` / ``rowspan`` spans, separator rows and
  per-cell alignment — and :func:`build_schema_table` is its structural
  inverse (column groups, ``RichCell`` spans, ``Separator`` rules).
* **Plain GFM pipe tables** (no marker): flat headers and rows, alignment from
  the inline ``text-align`` style.

The reconstruction validates through ``build_matrix`` (the schema's
``@model_validator``), so any inconsistency is ``None`` — the callers keep the
table lossless as a generic block and report it.

:func:`to_model` then expands a schema table into the generated
:class:`texsmith.ir.model.TableModel` (the leaf matrix tmark's parser builds:
the label is the first cell of every data row, absorbed slots are flagged),
lowering each cell's HTML content to inline nodes.

Shared by the :mod:`texsmith.readers.html` reader and, until phase 5, its
legacy twin :mod:`texsmith.readers.html_legacy`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from bs4.element import PageElement, Tag

from texsmith.extensions.tables import schema as tbl
from texsmith.extensions.tables.constants import ALIGN_ALIASES, TableAttr
from texsmith.ir import model

from ._helpers import coerce_attr


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.extensions.tables.schema import LeafCell


__all__ = [
    "InlineLowering",
    "build_schema_table",
    "cell_tags",
    "extract_rows",
    "is_rich",
    "is_separator",
    "section_rows",
    "separator_of",
    "to_model",
]

InlineLowering = Callable[[Iterable[PageElement]], tuple[model.Inline, ...]]


def is_rich(tag: Tag) -> bool:
    """Whether ``tag`` was rendered by the yaml-table extension (``data-ts-table``)."""
    return coerce_attr(tag.get(TableAttr.TABLE)) == "1"


def cell_tags(tr: Tag) -> list[Tag]:
    """The ``<th>`` / ``<td>`` direct children of a row, in order."""
    return tr.find_all(["th", "td"], recursive=False)


def build_schema_table(tag: Tag) -> tbl.Table | None:
    """Reconstruct the schema ``Table`` of ``tag``; ``None`` when it cannot be modelled."""
    return _build_rich_table_model(tag) if is_rich(tag) else _build_table_model(tag)


def section_rows(tag: Tag) -> tuple[list[Tag], list[Tag]]:
    """The body and footer ``<tr>`` of ``tag`` in order (separator rows included).

    Header rows are skipped: those flagged ``data-ts-role="header"`` and, in a
    plain table without ``<thead>``, a first row made of ``<th>`` only.
    """
    body: list[Tag] = []
    footer: list[Tag] = []
    seen_header = tag.find("thead") is not None
    sections = tag.find_all(["tbody", "tfoot"], recursive=False) or [tag]
    for section in sections:
        target = footer if section.name == "tfoot" else body
        for tr in section.find_all("tr", recursive=False) or section.find_all("tr"):
            if coerce_attr(tr.get(TableAttr.ROLE)) == "header":
                continue
            if not seen_header and tr.find("th") is not None and tr.find("td") is None:
                seen_header = True
                continue
            target.append(tr)
    return body, footer


def is_separator(tr: Tag) -> bool:
    """Whether a row is a ``data-ts-role="separator"`` rule."""
    return coerce_attr(tr.get(TableAttr.ROLE)) == "separator"


def separator_of(tr: Tag) -> tbl.Separator:
    """The schema ``Separator`` of a separator row (label and double rule)."""
    payload: dict[str, object] = {
        "separator": True,
        "double-rule": coerce_attr(tr.get(TableAttr.RULE)) == "double",
    }
    label = coerce_attr(tr.get(TableAttr.SEP_LABEL))
    if label:
        payload["label"] = label
    return tbl.Separator.model_validate(payload)


def extract_rows(tag: Tag) -> list[list[str]]:
    """Every row of ``tag`` as its cells' plain text (the fallback rendering)."""
    return [
        [cell.get_text().strip() for cell in row.find_all(["th", "td"])]
        for row in tag.find_all("tr")
    ]


# ---------------------------------------------------------------------------
# Plain (GFM) tables
# ---------------------------------------------------------------------------


def _build_table_model(tag: Tag) -> tbl.Table | None:
    """Reconstruct a schema ``Table`` from a plain HTML ``<table>``.

    Reads the header row(s) for column names and alignment, then each body row
    as a positional :class:`~texsmith.extensions.tables.schema.DataRow`. The
    schema validator requires at least two columns; ``None`` signals a table
    too narrow to model.
    """
    header_cells = _header_cells(tag)
    body_rows, footer_rows = _scalar_rows(tag)

    n_cols = _column_count(header_cells, [*body_rows, *footer_rows])
    if n_cols < 2:
        return None

    columns: list[tbl.Column] = []
    for index in range(n_cols):
        name = header_cells[index]["text"] if index < len(header_cells) else None
        align = header_cells[index]["align"] if index < len(header_cells) else None
        # ``model_validate`` runs the schema's ``align`` before-validator, which
        # accepts the normalised one-letter form produced by ``_cell_align``.
        columns.append(tbl.LeafColumn.model_validate({"name": name or None, "align": align}))

    try:
        return tbl.Table(
            columns=columns, rows=_positional_rows(body_rows), footer=_positional_rows(footer_rows)
        )
    except Exception:  # pragma: no cover - defensive; falls back to Div
        return None


def _positional_rows(rows: list[list[str] | None]) -> list[tbl.Row]:
    out: list[tbl.Row] = []
    for row in rows:
        if row is None:
            out.append(tbl.Separator(separator=True))
            continue
        # First cell becomes the row label; the remainder are data cells.
        label = row[0] if row else ""
        out.append(tbl.DataRow(label=label, cells=list(row[1:]), source="positional"))
    return out


def _header_cells(tag: Tag) -> list[dict[str, str | None]]:
    thead = tag.find("thead")
    header_row = None
    if thead is not None:
        header_row = thead.find("tr")
    if header_row is None:
        first_row = tag.find("tr")
        if first_row is not None and first_row.find("th") is not None:
            header_row = first_row
    if header_row is None:
        return []
    cells: list[dict[str, str | None]] = []
    for cell in header_row.find_all(["th", "td"]):
        cells.append({"text": cell.get_text().strip(), "align": _cell_align(cell)})
    return cells


def _scalar_rows(tag: Tag) -> tuple[list[list[str] | None], list[list[str] | None]]:
    """Body and footer rows as their cells' plain text (``None`` for a separator)."""

    def texts(rows: list[Tag]) -> list[list[str] | None]:
        return [
            None if is_separator(tr) else [cell.get_text().strip() for cell in cell_tags(tr)]
            for tr in rows
        ]

    body, footer = section_rows(tag)
    return texts(body), texts(footer)


def _column_count(
    header_cells: list[dict[str, str | None]], body_rows: list[list[str] | None]
) -> int:
    counts = [len(header_cells)]
    counts.extend(len(row) for row in body_rows if row is not None)
    return max(counts) if counts else 0


def _cell_align(cell: Tag) -> str | None:
    explicit = coerce_attr(cell.get(TableAttr.ALIGN))
    if explicit and explicit in ALIGN_ALIASES:
        return ALIGN_ALIASES[explicit]
    style = coerce_attr(cell.get("style")) or ""
    if "text-align: right" in style:
        return "r"
    if "text-align: center" in style:
        return "c"
    if "text-align: left" in style:
        return "l"
    return None


# ---------------------------------------------------------------------------
# Rich (data-ts) tables
# ---------------------------------------------------------------------------


def _build_rich_table_model(tag: Tag) -> tbl.Table | None:
    """Reconstruct the full rich ``schema.Table`` from a ``data-ts-table`` HTML.

    The ``<thead>`` levels rebuild the column hierarchy (groups + leaves), and
    each ``<tbody>`` / ``<tfoot>`` row rebuilds a
    :class:`~texsmith.extensions.tables.schema.DataRow` (with ``RichCell`` spans
    for ``colspan`` / ``rowspan`` / per-cell alignment) or a
    :class:`~texsmith.extensions.tables.schema.Separator` (carrying its label
    and double-rule flag). The table-level settings come from the
    ``data-ts-width`` / ``data-ts-placement`` attributes; the LaTeX environment
    and column preamble are not carried (the writers derive them again).
    """
    columns = _rich_columns(tag)
    if columns is None or len(columns) < 2:
        return None

    # Leaf span of each *data* column (the first column is the row-label column,
    # excluded). Needed to repackage flat HTML leaf cells back into the schema's
    # top-level-column-positional rows (a group column takes a list of leaves).
    data_leaf_spans = [tbl.leaf_count(col) for col in columns[1:]]
    total_data_leaves = sum(data_leaf_spans)

    body, footer = section_rows(tag)
    body_rows = _rich_section_rows(body, data_leaf_spans, total_data_leaves)
    if body_rows is None:
        return None
    footer_rows = _rich_section_rows(footer, data_leaf_spans, total_data_leaves)
    if footer_rows is None:
        return None

    try:
        return tbl.Table(
            settings=_rich_settings(tag), columns=columns, rows=body_rows, footer=footer_rows
        )
    except Exception:  # pragma: no cover - defensive; falls back to Div
        return None


def _rich_settings(tag: Tag) -> tbl.TableSettings:
    """The ``table:`` knobs recoverable from the ``data-ts-*`` attributes."""
    payload: dict[str, object] = {}
    placement = coerce_attr(tag.get(TableAttr.PLACEMENT))
    if placement:
        payload["placement"] = placement
    if coerce_attr(tag.get(TableAttr.ENV)) == "longtable":
        payload["long"] = True
    width = coerce_attr(tag.get(TableAttr.WIDTH)) or ""
    fraction = width.removesuffix("\\linewidth")
    if width == "\\linewidth":
        payload["width"] = "100%"
    elif fraction != width and fraction.replace(".", "", 1).isdigit():
        payload["width"] = f"{float(fraction) * 100:g}%"
    try:
        return tbl.TableSettings.model_validate(payload)
    except Exception:  # pragma: no cover - defensive
        return tbl.TableSettings()


def _rich_columns(tag: Tag) -> list[tbl.Column] | None:
    """Rebuild the column tree (groups + leaves) from the ``<thead>`` levels.

    Each ``<thead> <tr data-ts-role="header">`` is one level of the hierarchy.
    A cell with ``colspan > 1`` heads a :class:`ColumnGroup` whose children come
    from the next level; a cell with ``colspan == 1`` is a leaf (its
    ``rowspan`` lets it skip the lower levels). Leaf alignment / width are not
    encoded per column in the HTML (they live in the table-level colspec), so
    leaves are rebuilt name-only — enough to regenerate the identical header
    matrix and ``\\cmidrule`` grouping.

    When the table has no ``<thead>`` (every column was unnamed), a flat list of
    nameless leaf columns sized to the widest body row is returned so the body
    still validates.
    """
    thead = tag.find("thead")
    if thead is None:
        n = _rich_leaf_count(tag)
        if n < 2:
            return None
        return [tbl.LeafColumn() for _ in range(n)]

    levels: list[list[Tag]] = []
    for tr in thead.find_all("tr", recursive=False):
        cells = cell_tags(tr)
        if cells:
            levels.append(cells)
    if not levels:
        return None

    cursors = [0] * len(levels)

    def build(level: int, slots: int) -> list[tbl.Column] | None:
        """Consume ``slots`` leaf positions at ``level`` into a column list."""
        cols: list[tbl.Column] = []
        produced = 0
        cells = levels[level]
        while produced < slots:
            if cursors[level] >= len(cells):
                return None
            cell = cells[cursors[level]]
            cursors[level] += 1
            colspan = int(coerce_attr(cell.get("colspan")) or 1)
            name = cell.get_text().strip()
            if colspan > 1:
                if level + 1 >= len(levels):
                    return None
                children = build(level + 1, colspan)
                if children is None:
                    return None
                cols.append(tbl.ColumnGroup(name=name or " ", columns=children))
            else:
                cols.append(tbl.LeafColumn(name=name or None))
            produced += colspan
        return cols

    # The top level spans every leaf slot; that is the sum of its cells'
    # colspans (a leaf cell carries ``rowspan`` to reach the bottom level but
    # still occupies a single slot).
    top_slots = sum(int(coerce_attr(c.get("colspan")) or 1) for c in levels[0])
    return build(0, top_slots)


def _rich_leaf_count(tag: Tag) -> int:
    """Widest leaf-slot count across body / footer data rows (sum of colspans)."""
    body, footer = section_rows(tag)
    best = 0
    for tr in (*body, *footer):
        if is_separator(tr):
            continue
        slots = sum(int(coerce_attr(c.get("colspan")) or 1) for c in cell_tags(tr))
        best = max(best, slots)
    return best


def _rich_section_rows(
    rows_html: list[Tag],
    data_leaf_spans: list[int],
    total_data_leaves: int,
) -> list[tbl.Row] | None:
    """Rebuild ``DataRow`` / ``Separator`` rows from a section's ``<tr>`` list.

    The HTML lists data cells flat at *leaf* granularity, with absorbed multirow
    positions omitted. The schema, however, wants cells at *top-level-column*
    granularity (a column group takes a list of its leaf cells). This walks the
    flat ``<td>`` stream against the per-column leaf spans, tracks active
    multirow carry-over (so absorbed leaves below an origin cell are skipped just
    as ``build_matrix`` expects), and re-groups leaves into the positional cell
    list the schema validates. ``None`` signals an inconsistency.
    """
    rows: list[tbl.Row] = []
    # active[leaf_pos] -> remaining rows the multirow span still absorbs.
    active: dict[int, int] = {}
    for tr in rows_html:
        if is_separator(tr):
            rows.append(separator_of(tr))
            continue
        cells = cell_tags(tr)
        # First cell is the row label (``<th scope="row">``); rest are data.
        label = cells[0].get_text().strip() if cells else ""
        data_cells = _regroup_row_cells(cells[1:], data_leaf_spans, total_data_leaves, active)
        if data_cells is None:
            return None
        rows.append(tbl.DataRow(label=label, cells=data_cells, source="positional"))
    return rows


def _regroup_row_cells(
    html_cells: list[Tag],
    data_leaf_spans: list[int],
    total_data_leaves: int,
    active: dict[int, int],
) -> list[object] | None:
    """Re-group flat leaf ``<td>``s into top-level-column-positional cells.

    Walks the leaf grid left to right: absorbed leaves (carried from a multirow
    span above) are skipped, the remaining leaves are consumed from
    ``html_cells``. A single-leaf data column yields a scalar / ``RichCell``; a
    multi-leaf (grouped) column yields the list of its leaf cells. Multirow
    origins seed ``active`` so their absorbed leaves are skipped on later rows.
    Returns ``None`` on any structural surprise (e.g. ran out of HTML cells).
    """
    # Leaves still absorbed on *this* row by a multirow span opened above.
    carried = set(active)

    cell_iter = iter(html_cells)
    leaf_pos = 0
    col_index = 0
    col_leaf_start = 0
    out: list[object] = []

    while col_index < len(data_leaf_spans):
        span = data_leaf_spans[col_index]
        # Skip leaves of this column absorbed by a multirow span from above; a
        # single-leaf column fully absorbed contributes ``None`` (schema skips).
        if leaf_pos in carried:
            leaf_pos += 1
            if leaf_pos >= col_leaf_start + span:
                if span == 1:
                    out.append(None)
                col_leaf_start += span
                col_index += 1
            continue

        cell = next(cell_iter, None)
        if cell is None:
            return None
        value, rspan, cspan = _rich_cell_parts(cell)
        if rspan > 1:
            for offset in range(cspan):
                active[leaf_pos + offset] = rspan - 1

        if cspan > span:
            # Cross-column span (``_place_rich``): one positional cell that
            # consumes ``cspan`` leaves across the columns it covers.
            out.append(value)
            leaf_pos += cspan
            while (
                col_index < len(data_leaf_spans)
                and leaf_pos >= col_leaf_start + data_leaf_spans[col_index]
            ):
                col_leaf_start += data_leaf_spans[col_index]
                col_index += 1
            continue

        # Cell lives within the current column.
        if span == 1:
            out.append(value)
            leaf_pos += cspan  # cspan == 1 here
            col_leaf_start += span
            col_index += 1
        else:
            # Grouped column: collect this column's leaf cells into a list.
            leaves: list[object] = [value]
            leaf_pos += cspan
            consumed = cspan
            while consumed < span:
                if leaf_pos in carried:
                    leaf_pos += 1
                    consumed += 1
                    continue
                nxt = next(cell_iter, None)
                if nxt is None:
                    return None
                nval, nrspan, ncspan = _rich_cell_parts(nxt)
                if ncspan > span - consumed:
                    return None
                if nrspan > 1:
                    for offset in range(ncspan):
                        active[leaf_pos + offset] = nrspan - 1
                leaves.append(nval)
                leaf_pos += ncspan
                consumed += ncspan
            out.append(leaves)
            col_leaf_start += span
            col_index += 1

    if next(cell_iter, None) is not None or leaf_pos != total_data_leaves:
        return None

    # Age the carry-over: previously-absorbed slots lose one row of reach;
    # freshly-opened spans (added on this row) keep their full remaining count.
    for pos in list(active):
        if pos in carried:
            active[pos] -= 1
            if active[pos] <= 0:
                del active[pos]
    return out


def _rich_cell_parts(cell: Tag) -> tuple[object, int, int]:
    """Return ``(value_or_RichCell, rowspan, colspan)`` for one data ``<td>``.

    A plain single-slot cell with no alignment override becomes its scalar text
    (or ``None`` when flagged ``data-ts-empty``); any ``colspan`` / ``rowspan``
    / ``data-ts-align`` promotes it to a :class:`RichCell` carrying the span.
    """
    empty = coerce_attr(cell.get(TableAttr.EMPTY)) == "1"
    text = cell.get_text().strip()
    value: object = None if empty else text
    cols = int(coerce_attr(cell.get("colspan")) or 1)
    rows = int(coerce_attr(cell.get("rowspan")) or 1)
    align = coerce_attr(cell.get(TableAttr.ALIGN))
    if cols > 1 or rows > 1 or align:
        payload: dict[str, object] = {"value": value, "rows": rows, "cols": cols}
        if align:
            payload["align"] = align
        return tbl.RichCell.model_validate(payload), rows, cols
    return value, rows, cols


# ---------------------------------------------------------------------------
# Schema → generated model
# ---------------------------------------------------------------------------


def to_model(table: tbl.Table, tag: Tag, lower_inline: InlineLowering) -> model.TableModel:
    """Expand a schema ``Table`` into the generated :class:`~texsmith.ir.model.TableModel`.

    Every data row is the leaf matrix ``build_matrix`` computes (the label cell
    first, absorbed slots flagged), which is the shape tmark's parser produces
    for the same table. Cell content is lowered from the HTML cells of ``tag``:
    per data row the ``<th>`` label then the non-absorbed ``<td>`` in order —
    exactly the cells the HTML lists — so bold, code and links inside a cell
    survive; a cell the HTML does not hold falls back to its scalar text.
    """
    matrix = tbl.build_matrix(table)
    body_html, footer_html = section_rows(tag)
    settings = table.settings
    return model.TableModel(
        rows=_model_rows(table.rows, matrix.body, matrix.body_row_kinds, body_html, lower_inline),
        footer=_model_rows(
            table.footer, matrix.footer, matrix.footer_row_kinds, footer_html, lower_inline
        ),
        columns=tuple(_model_column(column) for column in table.columns),
        settings=model.TableSettings(
            long=None if settings.long == "auto" else bool(settings.long),
            placement=settings.placement,
            width=settings.width,
        ),
    )


def _model_column(column: tbl.Column) -> model.Column:
    align = model.Align(column.align) if column.align else None
    if isinstance(column, tbl.ColumnGroup):
        return model.ColumnGroup(
            columns=tuple(_model_column(child) for child in column.columns),
            name=column.name,
            align=align,
            width=column.width,
            width_group=column.width_group,
        )
    return model.LeafColumn(
        align=align, name=column.name, width=column.width, width_group=column.width_group
    )


def _model_rows(
    rows: list[tbl.Row],
    leaf_rows: list[list[LeafCell]],
    kinds: list[str],
    rows_html: list[Tag],
    lower_inline: InlineLowering,
) -> tuple[model.Row, ...]:
    out: list[model.Row] = []
    html_iter = iter(tr for tr in rows_html if not is_separator(tr))
    for row, leaves, kind in zip(rows, leaf_rows, kinds, strict=True):
        if kind == "separator" or isinstance(row, tbl.Separator):
            separator = row if isinstance(row, tbl.Separator) else tbl.Separator()
            out.append(model.Separator(double_rule=separator.double_rule, label=separator.label))
            continue
        assert isinstance(row, tbl.DataRow)
        tr = next(html_iter, None)
        html_cells = cell_tags(tr) if tr is not None else []
        visible = [leaf for leaf in leaves if not leaf.absorbed]
        runs: list[tuple[model.Inline, ...] | None] = [None] * (1 + len(visible))
        if len(html_cells) == len(runs):
            runs = [lower_inline(cell.children) for cell in html_cells]
        cells = [model.Cell(content=runs[0] if runs[0] is not None else _text(row.label))]
        cursor = 1
        for leaf in leaves:
            if leaf.absorbed:
                cells.append(model.Cell(absorbed=True))
                continue
            run = runs[cursor]
            cursor += 1
            cells.append(
                model.Cell(
                    align=model.Align(leaf.align) if leaf.align else None,
                    cols=leaf.cols,
                    content=run if run is not None else _text(leaf.value),
                    rows=leaf.rows,
                )
            )
        out.append(model.DataRow(cells=tuple(cells), named=row.source == "named"))
    return tuple(out)


def _text(value: object) -> tuple[model.Inline, ...]:
    if value is None or value == "":
        return ()
    return (model.Str(str(value)),)
