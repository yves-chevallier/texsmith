"""Extension lowerings: TeXSmith / Material constructs into typed IR nodes.

These mirror the HTML→semantic half of ``extensions/*/renderer.py`` and the
Material plugin handlers, but they *return IR* (the LaTeX half stays with the
writer). Covered here:

* admonitions / callouts — ``div.admonition``, ``<details>`` callouts, and
  ``> [!TYPE]`` blockquote callouts → :class:`~texsmith.ir.Admonition`;
* margin notes — ``<ts-marginnote data-side>`` → :class:`~texsmith.ir.MarginNote`;
* progress bars — ``div.progress`` → :class:`~texsmith.ir.ProgressBar`;
* tables — ``<table>`` (yaml ``data-ts-*`` or plain GFM) →
  :class:`~texsmith.ir.Table` wrapping the validated tables schema model.

(Index, TeX logos and keystrokes are inline constructs handled in
:mod:`.inline` because they originate from ``<span>``.)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from texsmith.extensions.tables import schema as tbl
from texsmith.extensions.tables.constants import ALIGN_ALIASES, TableAttr
from texsmith.ir import nodes as ir

from ._helpers import attrs_tuple, classes, coerce_attr
from .registry import NotHandled, ReadLevel, reads


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import Tag

    from .context import ReadContext
    from .registry import _NotHandledType


# Admonition wrapper classes that do not name the callout kind.
_ADMONITION_NOISE = {
    "admonition",
    "annotate",
    "inline",
    "end",
    "left",
    "right",
    "checkbox",
}
_CALLOUT_PATTERN = re.compile(r"^\s*\[!(?P<kind>[A-Za-z0-9_-]+)\]\s*(?P<content>.*)$", re.DOTALL)


# ---------------------------------------------------------------------------
# Snippet blocks (file-inclusion previews)
# ---------------------------------------------------------------------------


@reads("div", "pre", level=ReadLevel.BLOCK, name="snippet", priority=120)
def read_snippet(tag: Tag, _ctx: ReadContext) -> ir.Div | _NotHandledType:
    """A ``.snippet`` code fence (file-inclusion preview).

    The snippet block is the snippet plugin's own format (a fenced YAML/markup
    payload describing documents to render into an embedded preview). The reader
    preserves the element verbatim — like ``data-ts`` tables, this is an
    extension format, not a backend string — so the writer can run the
    self-contained snippet compiler on it.
    """
    pre = tag.find("pre")
    code = tag.find("code")
    cls = set(classes(tag.get("class")))
    cls.update(classes(pre.get("class") if pre is not None else None))
    cls.update(classes(code.get("class") if code is not None else None))
    if "snippet" not in cls:
        return NotHandled
    return ir.Div(content=(), attrs=attrs_tuple({"role": "snippet", "html": str(tag)}))


# ---------------------------------------------------------------------------
# Admonitions / callouts
# ---------------------------------------------------------------------------


@reads("div", level=ReadLevel.BLOCK, name="admonition", priority=100)
def read_admonition(tag: Tag, ctx: ReadContext) -> ir.Admonition | _NotHandledType:
    cls = classes(tag.get("class"))
    if "admonition" not in cls:
        return NotHandled
    kind = _admonition_kind(cls)
    title_el = tag.find("p", class_="admonition-title")
    title: tuple[ir.Inline, ...] = ()
    body_children = list(tag.children)
    if title_el is not None:
        title = ctx.lower_inline(title_el.children)
        body_children = [c for c in body_children if c is not title_el]
    return ir.Admonition(
        kind=kind,
        title=title,
        content=ctx.lower_blocks(body_children),
        collapsible=False,
    )


@reads("details", level=ReadLevel.BLOCK, name="details_callout", priority=100)
def read_details_callout(tag: Tag, ctx: ReadContext) -> ir.Admonition:
    """A ``<details>`` block (collapsible callout)."""
    cls = classes(tag.get("class"))
    summary = tag.find("summary")
    title: tuple[ir.Inline, ...] = ()
    body_children = list(tag.children)
    if summary is not None:
        title = ctx.lower_inline(summary.children)
        body_children = [c for c in body_children if c is not summary]
    kind = _admonition_kind(cls)
    return ir.Admonition(
        kind=kind,
        title=title,
        content=ctx.lower_blocks(body_children),
        collapsible=True,
    )


@reads("blockquote", level=ReadLevel.BLOCK, name="blockquote_callout", priority=50)
def read_blockquote_callout(tag: Tag, ctx: ReadContext) -> ir.Admonition | _NotHandledType:
    """Obsidian / Docusaurus ``> [!TYPE] title`` callout."""
    first_p = tag.find("p")
    if first_p is None:
        return NotHandled
    text = first_p.get_text()
    match = _CALLOUT_PATTERN.match(text.lstrip())
    if not match:
        return NotHandled

    kind = match.group("kind").lower()
    remainder = (match.group("content") or "").strip()
    lines = [line.strip() for line in remainder.splitlines() if line.strip()]
    title_text = lines[0] if lines else kind.capitalize()

    # The first marker line is the title; any further lines inside the marker
    # paragraph form the leading body text, followed by the remaining blocks.
    content: list[ir.Block] = []
    if len(lines) > 1:
        body_text = " ".join(lines[1:])
        content.append(ir.Para(content=(ir.Str(body_text),)))
    body_children = [c for c in tag.children if c is not first_p]
    content.extend(ctx.lower_blocks(body_children))
    return ir.Admonition(
        kind=kind,
        title=(ir.Str(title_text),) if title_text else (),
        content=tuple(content),
        collapsible=False,
    )


def _admonition_kind(cls: list[str]) -> str:
    candidates = [c for c in cls if c not in _ADMONITION_NOISE]
    return candidates[0] if candidates else "note"


# ---------------------------------------------------------------------------
# Margin notes
# ---------------------------------------------------------------------------


@reads("ts-marginnote", level=ReadLevel.ANY, name="marginnote")
def read_marginnote(tag: Tag, ctx: ReadContext) -> ir.MarginNote:
    side_raw = (coerce_attr(tag.get("data-side")) or "").strip().lower()
    side = ir.MarginSide.LEFT if side_raw in {"l", "left", "i", "inner"} else ir.MarginSide.RIGHT
    # Margin-note bodies are inline-flavoured; wrap them in a Plain block so the
    # IR contract (MarginNote.content is a block tuple) is honoured.
    inline = ctx.lower_inline(tag.children)
    content = (ir.Plain(content=inline),) if inline else ()
    return ir.MarginNote(content=content, side=side)


# ---------------------------------------------------------------------------
# Progress bars
# ---------------------------------------------------------------------------


@reads("div", level=ReadLevel.BLOCK, name="progressbar", priority=90)
def read_progressbar(tag: Tag, ctx: ReadContext) -> ir.ProgressBar | _NotHandledType:
    cls = classes(tag.get("class"))
    if "progress" not in cls:
        return NotHandled
    bar = tag.find("div", class_="progress-bar")
    if bar is None:
        return NotHandled
    percent = _progress_percent(tag, bar)
    fraction = max(0.0, min(1.0, percent / 100.0))
    label_el = bar.find("p", class_="progress-label")
    label = ctx.lower_inline(label_el.children) if label_el is not None else ()
    thin = "thin" in cls or "progress-thin" in cls
    return ir.ProgressBar(fraction=fraction, label=label, thin=thin)


def _progress_percent(tag: Tag, bar: Tag) -> float:
    for attr in ("data-progress-percent", "data-progress", "data-progress-value"):
        value = coerce_attr(tag.get(attr)) or coerce_attr(bar.get(attr))
        if value:
            try:
                return float(value)
            except ValueError:
                continue
    fraction_attr = coerce_attr(bar.get("data-progress-fraction"))
    if fraction_attr:
        try:
            return float(fraction_attr) * 100.0
        except ValueError:
            pass
    style = coerce_attr(bar.get("style")) or ""
    match = re.search(r"width:\s*([0-9.]+)", style)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


@reads("table", level=ReadLevel.BLOCK, name="table")
def read_table(tag: Tag, ctx: ReadContext) -> ir.Block:
    """Lower a ``<table>`` into an IR :class:`~texsmith.ir.Table`.

    Two distinct input shapes converge on the same :class:`~texsmith.ir.Table`
    node, distinguished by the table extension's ``data-ts-table`` marker:

    * **Rich tables** (``yaml table`` / ``yaml table-config``): the ``<table>``
      carries ``data-ts-*`` layout attributes plus header / body / footer rows
      with native ``colspan`` / ``rowspan`` spans, separator rows and per-cell
      alignment. The full structure is reconstructed into a validated
      :class:`texsmith.extensions.tables.schema.Table` (column *groups*,
      ``RichCell`` multirow / multicolumn spans, ``Separator`` rules) — the same
      shape the markdown extension built before it rendered the HTML — so the
      writer reproduces the yaml-table LaTeX losslessly. The precomputed layout
      directive (``env`` / ``colspec`` / ``width`` / ``placement``) is lifted
      verbatim from the ``data-ts-*`` attributes onto the IR node, because the
      per-column widths and group preamble wrappers folded into the colspec are
      not recoverable from cell text alone.

    * **Plain GFM pipe tables** (no ``data-ts-table``): flat headers and rows;
      reconstructed into a flat ``schema.Table`` and left with empty layout
      fields so the writer takes the plain ``table.tex`` path.

    Per the IR contract, cell content is scalar text (rich inline inside cells
    is not yet representable).
    """
    caption_el = tag.find("caption")
    caption: tuple[ir.Inline, ...] = ()
    if caption_el is not None:
        for span in list(caption_el.find_all("span")):
            if {"caption-prefix", "figure-prefix"}.intersection(classes(span.get("class"))):
                span.extract()
        caption = ctx.lower_inline(caption_el.children)
    label = coerce_attr(tag.get("id")) or ""

    is_rich = coerce_attr(tag.get(TableAttr.TABLE)) == "1"

    model = _build_rich_table_model(tag) if is_rich else _build_table_model(tag)
    if model is None:
        # Degenerate table (e.g. a single column): keep it lossless as a Div
        # carrying the rendered cell text, and report the limitation.
        ctx.warn(
            "HtmlReader: table with fewer than 2 columns is not representable "
            "by the tables schema; preserved as a generic Div."
        )
        rows = _extract_rows(tag)
        blocks = tuple(
            ir.Para(content=(ir.Str(" | ".join(cell for cell in row)),)) for row in rows if row
        )
        return ir.Div(content=blocks, attrs=attrs_tuple({"role": "table-fallback"}))

    cells = _collect_cell_content(tag, ctx)

    if is_rich:
        return ir.Table(
            model=model,
            caption=caption,
            label=label,
            cells=cells,
            env=coerce_attr(tag.get(TableAttr.ENV)) or "",
            colspec=coerce_attr(tag.get(TableAttr.COLSPEC)) or "",
            width=coerce_attr(tag.get(TableAttr.WIDTH)) or "",
            placement=coerce_attr(tag.get(TableAttr.PLACEMENT)) or "",
        )

    return ir.Table(model=model, caption=caption, label=label, cells=cells)


def _collect_cell_content(tag: Tag, ctx: ReadContext) -> tuple[tuple[ir.Inline, ...], ...]:
    """Lower every table cell's inline content, in HTML document order.

    Returns one inline run per ``<th>`` / ``<td>``, ordered exactly as
    :func:`texsmith.extensions.tables.html.render_table_html` emits them
    (header levels first, then per body / footer row the label cell followed by
    its data cells). The ``<caption>`` is excluded (carried as ``Table.caption``)
    and separator rows contribute no entry (their plain-text label stays scalar
    on ``model``). This is what lets a writer recover bold / inline-code / links
    / escaped specials inside cells, which the scalar ``model`` cannot hold.
    """
    out: list[tuple[ir.Inline, ...]] = []

    thead = tag.find("thead")
    if thead is not None:
        for tr in thead.find_all("tr", recursive=False):
            for cell in tr.find_all(["th", "td"], recursive=False):
                out.append(ctx.lower_inline(cell.children))
    else:
        # Plain GFM tables may keep the header row directly under the table.
        first = tag.find("tr")
        if first is not None and first.find("th") is not None and first.find("td") is None:
            for cell in first.find_all(["th", "td"], recursive=False):
                out.append(ctx.lower_inline(cell.children))

    bodies = tag.find_all(["tbody", "tfoot"], recursive=False) or [tag]
    for body in bodies:
        rows_iter = body.find_all("tr", recursive=False) or body.find_all("tr")
        for tr in rows_iter:
            role = coerce_attr(tr.get(TableAttr.ROLE))
            if role == "header":
                continue
            # A header row sitting in <tbody> (already consumed above when it is
            # the table's first <tr>) must not be collected twice.
            if thead is None and tr is tag.find("tr") and tr.find("td") is None:
                continue
            if role == "separator":
                continue
            for cell in tr.find_all(["th", "td"], recursive=False):
                out.append(ctx.lower_inline(cell.children))

    return tuple(out)


def _build_table_model(tag: Tag) -> tbl.Table | None:
    """Reconstruct a tables-schema ``Table`` from an HTML ``<table>``.

    Reads the header row(s) for column names and alignment, then each body row
    as a positional :class:`~texsmith.extensions.tables.schema.DataRow`. The
    schema validator requires at least two columns; ``None`` signals a table
    too narrow to model.
    """
    header_cells = _header_cells(tag)
    body_rows = _body_rows(tag)

    n_cols = _column_count(header_cells, body_rows)
    if n_cols < 2:
        return None

    columns: list[tbl.Column] = []
    for index in range(n_cols):
        name = header_cells[index]["text"] if index < len(header_cells) else None
        align = header_cells[index]["align"] if index < len(header_cells) else None
        # ``model_validate`` runs the schema's ``align`` before-validator, which
        # accepts the normalised one-letter form produced by ``_cell_align``.
        columns.append(tbl.LeafColumn.model_validate({"name": name or None, "align": align}))

    rows: list[tbl.Row] = []
    for row in body_rows:
        if row is None:
            rows.append(tbl.Separator(separator=True))
            continue
        # First cell becomes the row label; the remainder are data cells.
        label = row[0] if row else ""
        cells = list(row[1:])
        rows.append(tbl.DataRow(label=label, cells=cells, source="positional"))

    try:
        return tbl.Table(columns=columns, rows=rows)
    except Exception:  # pragma: no cover - defensive; falls back to Div
        return None


def _build_rich_table_model(tag: Tag) -> tbl.Table | None:
    """Reconstruct the full rich ``schema.Table`` from a ``data-ts-table`` HTML.

    The HTML is the exact output of
    :func:`texsmith.extensions.tables.html.render_table_html`, so this is its
    structural inverse: the ``<thead>`` levels rebuild the column hierarchy
    (groups + leaves), and each ``<tbody>`` / ``<tfoot>`` row rebuilds a
    :class:`~texsmith.extensions.tables.schema.DataRow` (with ``RichCell`` spans
    for ``colspan`` / ``rowspan`` / per-cell alignment) or a
    :class:`~texsmith.extensions.tables.schema.Separator` (carrying its label
    and double-rule flag).

    The reconstructed model validates through ``build_matrix`` (run by the
    schema's ``@model_validator``), so any inconsistency surfaces as a parse
    failure → ``None`` → lossless ``Div`` fallback upstream.
    """
    columns = _rich_columns(tag)
    if columns is None or len(columns) < 2:
        return None

    # Leaf span of each *data* column (the first column is the row-label column,
    # excluded). Needed to repackage flat HTML leaf cells back into the schema's
    # top-level-column-positional rows (a group column takes a list of leaves).
    data_leaf_spans = [tbl.leaf_count(col) for col in columns[1:]]
    total_data_leaves = sum(data_leaf_spans)

    body_rows = _rich_section_rows(tag.find("tbody"), data_leaf_spans, total_data_leaves)
    if body_rows is None:
        return None
    footer_rows = _rich_section_rows(tag.find("tfoot"), data_leaf_spans, total_data_leaves)
    if footer_rows is None:
        return None

    try:
        return tbl.Table(columns=columns, rows=body_rows, footer=footer_rows)
    except Exception:  # pragma: no cover - defensive; falls back to Div
        return None


def _rich_columns(tag: Tag) -> list[tbl.Column] | None:
    """Rebuild the column tree (groups + leaves) from the ``<thead>`` levels.

    Each ``<thead> <tr data-ts-role="header">`` is one level of the hierarchy.
    A cell with ``colspan > 1`` heads a :class:`ColumnGroup` whose children come
    from the next level; a cell with ``colspan == 1`` is a leaf (its
    ``rowspan`` lets it skip the lower levels). Leaf alignment / width are not
    encoded per column in the HTML (they live in the table-level colspec, which
    the IR carries verbatim), so leaves are rebuilt name-only — enough to
    regenerate the identical header matrix and ``\\cmidrule`` grouping.

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
        cells = tr.find_all(["th", "td"], recursive=False)
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
    best = 0
    for section in (tag.find("tbody"), tag.find("tfoot")):
        if section is None:
            continue
        for tr in section.find_all("tr", recursive=False):
            if coerce_attr(tr.get(TableAttr.ROLE)) == "separator":
                continue
            cells = tr.find_all(["th", "td"], recursive=False)
            slots = sum(int(coerce_attr(c.get("colspan")) or 1) for c in cells)
            best = max(best, slots)
    return best


def _rich_section_rows(
    section: Tag | None,
    data_leaf_spans: list[int],
    total_data_leaves: int,
) -> list[tbl.Row] | None:
    """Rebuild ``DataRow`` / ``Separator`` rows from a ``<tbody>`` / ``<tfoot>``.

    The HTML lists data cells flat at *leaf* granularity, with absorbed multirow
    positions omitted. The schema, however, wants cells at *top-level-column*
    granularity (a column group takes a list of its leaf cells). This walks the
    flat ``<td>`` stream against the per-column leaf spans, tracks active
    multirow carry-over (so absorbed leaves below an origin cell are skipped just
    as ``build_matrix`` expects), and re-groups leaves into the positional cell
    list the schema validates. ``None`` signals an inconsistency → ``Div``
    fallback upstream.
    """
    rows: list[tbl.Row] = []
    if section is None:
        return rows
    # active[leaf_pos] -> remaining rows the multirow span still absorbs.
    active: dict[int, int] = {}
    for tr in section.find_all("tr", recursive=False):
        if coerce_attr(tr.get(TableAttr.ROLE)) == "separator":
            label = coerce_attr(tr.get(TableAttr.SEP_LABEL))
            double = coerce_attr(tr.get(TableAttr.RULE)) == "double"
            payload: dict[str, object] = {"separator": True, "double-rule": double}
            if label:
                payload["label"] = label
            rows.append(tbl.Separator.model_validate(payload))
            continue

        cells = tr.find_all(["th", "td"], recursive=False)
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


def _body_rows(tag: Tag) -> list[list[str] | None]:
    rows: list[list[str] | None] = []
    bodies = tag.find_all("tbody") or [tag]
    seen_header = tag.find("thead") is not None
    for body in bodies:
        for row in body.find_all("tr", recursive=False) or body.find_all("tr"):
            if coerce_attr(row.get(TableAttr.ROLE)) == "header":
                continue
            if not seen_header and row.find("th") is not None and row.find("td") is None:
                seen_header = True
                continue
            if coerce_attr(row.get(TableAttr.ROLE)) == "separator":
                rows.append(None)
                continue
            values = [cell.get_text().strip() for cell in row.find_all(["th", "td"])]
            rows.append(values)
    return rows


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


def _extract_rows(tag: Tag) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in tag.find_all("tr"):
        rows.append([cell.get_text().strip() for cell in row.find_all(["th", "td"])])
    return rows


__all__ = [
    "read_admonition",
    "read_blockquote_callout",
    "read_details_callout",
    "read_marginnote",
    "read_progressbar",
    "read_table",
]
