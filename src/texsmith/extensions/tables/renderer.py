"""Render HTML ``<table data-ts-table="1">`` nodes into LaTeX.

Consumes the HTML shape produced by :mod:`texsmith.extensions.tables.html`
and emits a LaTeX ``tabular`` / ``tabularx`` / ``longtable`` via the
``yaml_table`` partial. All spans, separators and ``\\cmidrule`` placements
are resolved here; the partial only stitches the preamble around the
pre-assembled body.
"""

from __future__ import annotations

from bs4 import Tag

from texsmith.adapters.html_utils import coerce_attribute

from .constants import TableAttr


# ---------------------------------------------------------------------------
# Cell content
# ---------------------------------------------------------------------------


def _cell_content(cell: Tag) -> str:
    """Extract the cell's already-escaped text content."""
    # The ``escape_plain_text`` PRE-phase handler has already run on every
    # text node in the tree by the time we fire at priority 35 in POST, so
    # we simply read the text as-is and strip surrounding whitespace.
    return cell.get_text(strip=False).strip()


def _align_char(value: str | None) -> str:
    if value in {"l", "c", "r"}:
        return value
    return "c"


# ---------------------------------------------------------------------------
# Header rendering (supports \cmidrule for grouped columns)
# ---------------------------------------------------------------------------


def _render_header(thead: Tag, total_cols: int) -> str:
    rows = thead.find_all("tr", attrs={TableAttr.ROLE: "header"}, recursive=False)
    if not rows:
        rows = thead.find_all("tr", recursive=False)

    lines: list[str] = []
    active_spans: dict[int, tuple[int, int]] = {}

    for level, row in enumerate(rows):
        rendered, active_spans, group_spans = _render_generic_row(
            row, total_cols, active_spans, is_header=True
        )
        lines.append(rendered)

        if level < len(rows) - 1 and group_spans:
            rules = [rf"\cmidrule(lr){{{start + 1}-{start + cols}}}" for start, cols in group_spans]
            lines.append(" ".join(rules))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Data row rendering
# ---------------------------------------------------------------------------


def _render_generic_row(
    row: Tag,
    total_cols: int,
    active_spans: dict[int, tuple[int, int]],
    *,
    is_header: bool,
) -> tuple[str, dict[int, tuple[int, int]], list[tuple[int, int]]]:
    """Render one ``<tr>`` to LaTeX, threading active-rowspan state.

    Returns the LaTeX line, the updated active-rowspan map, and the list of
    ``(cursor_start, colspan)`` tuples for cells that span more than one
    column — used by the header stage to place ``\\cmidrule`` commands.
    """
    children = row.find_all(["th", "td"], recursive=False)
    cell_iter = iter(children)

    parts: list[str] = []
    cursor = 0
    new_active: dict[int, tuple[int, int]] = dict(active_spans)
    group_spans: list[tuple[int, int]] = []

    while cursor < total_cols:
        if cursor in new_active:
            rows_remaining, cols = new_active.pop(cursor)
            if cols > 1:
                parts.append(rf"\multicolumn{{{cols}}}{{c}}{{}}")
            else:
                parts.append("")
            if rows_remaining > 1:
                new_active[cursor] = (rows_remaining - 1, cols)
            cursor += cols
            continue

        try:
            cell = next(cell_iter)
        except StopIteration:
            parts.append("")
            cursor += 1
            continue

        rowspan = int(coerce_attribute(cell.get("rowspan")) or 1)
        colspan = int(coerce_attribute(cell.get("colspan")) or 1)
        align = coerce_attribute(cell.get(TableAttr.ALIGN))
        content = _cell_content(cell)

        tex = content
        if rowspan > 1:
            tex = rf"\multirow{{{rowspan}}}{{*}}{{{tex}}}"
        if colspan > 1:
            tex = rf"\multicolumn{{{colspan}}}{{{_align_char(align)}}}{{{tex}}}"
            if rowspan == 1:
                group_spans.append((cursor, colspan))
        elif is_header and align:
            # Preserve a user-provided alignment for a single-column header.
            tex = rf"\multicolumn{{1}}{{{_align_char(align)}}}{{{tex}}}"

        parts.append(tex)

        if rowspan > 1:
            new_active[cursor] = (rowspan - 1, colspan)
        cursor += colspan

    return " & ".join(parts) + r" \\", new_active, group_spans


# ---------------------------------------------------------------------------
# Body / footer rendering
# ---------------------------------------------------------------------------


def _render_section(
    section: Tag | None,
    total_cols: int,
) -> str:
    if section is None:
        return ""
    lines: list[str] = []
    active_spans: dict[int, tuple[int, int]] = {}

    for tr in section.find_all("tr", recursive=False):
        role = coerce_attribute(tr.get(TableAttr.ROLE))
        if role == "separator":
            if active_spans:
                # Defensive: the schema validator forbids this upstream.
                active_spans = {}
            lines.append(_render_separator(tr, total_cols))
            continue
        rendered, active_spans, _groups = _render_generic_row(
            tr, total_cols, active_spans, is_header=False
        )
        lines.append(rendered)

    return "\n".join(lines)


def _render_separator(tr: Tag, total_cols: int) -> str:
    rule = coerce_attribute(tr.get(TableAttr.RULE))
    midrule = r"\midrule[\heavyrulewidth]" if rule == "double" else r"\midrule"

    # Read the label from the separator cell's text so it picks up the LaTeX
    # escaping applied by ``escape_plain_text`` in the PRE phase.
    cell = tr.find(["td", "th"])
    label = cell.get_text(strip=False).strip() if cell is not None else ""
    if not label:
        return midrule

    content = rf"\multicolumn{{{total_cols}}}{{l}}{{\textit{{{label}}}}} \\"
    return f"{midrule}\n\\addlinespace\n{content}\n\\addlinespace"


# ---------------------------------------------------------------------------
# Column-spec parsing
# ---------------------------------------------------------------------------


def _count_colspec_slots(colspec: str) -> int:
    """Count the number of columns declared in a LaTeX colspec string."""
    count = 0
    i = 0
    length = len(colspec)
    while i < length:
        ch = colspec[i]
        if ch in {"l", "c", "r", "X", "j"}:
            count += 1
            i += 1
            continue
        if ch == "p":
            count += 1
            # skip the {...} argument
            if i + 1 < length and colspec[i + 1] == "{":
                depth = 1
                j = i + 2
                while j < length and depth > 0:
                    if colspec[j] == "{":
                        depth += 1
                    elif colspec[j] == "}":
                        depth -= 1
                    j += 1
                i = j
            else:
                i += 1
            continue
        if ch == ">":
            # skip >{...} prefix
            if i + 1 < length and colspec[i + 1] == "{":
                depth = 1
                j = i + 2
                while j < length and depth > 0:
                    if colspec[j] == "{":
                        depth += 1
                    elif colspec[j] == "}":
                        depth -= 1
                    j += 1
                i = j
            else:
                i += 1
            continue
        i += 1  # unknown characters are skipped
    return count


__all__ = ["_count_colspec_slots", "_render_header", "_render_section"]
