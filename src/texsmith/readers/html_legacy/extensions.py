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

from texsmith.extensions.tables.constants import TableAttr
from texsmith.ir import nodes as ir
from texsmith.readers.html import tables
from texsmith.readers.html._helpers import attrs_tuple, classes, coerce_attr
from texsmith.readers.html.registry import NotHandled, ReadLevel, reads


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import Tag

    from texsmith.readers.html.registry import _NotHandledType

    from .context import ReadContext


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

    The structure (column groups, ``RichCell`` spans, separators) is rebuilt
    by :func:`texsmith.readers.html.tables.build_schema_table`; a rich table
    (``data-ts-table``) also carries its precomputed layout directive (``env``
    / ``colspec`` / ``width`` / ``placement``) verbatim from the ``data-ts-*``
    attributes, because the per-column widths and group preamble wrappers
    folded into the colspec are not recoverable from cell text alone. A plain
    GFM table leaves the layout fields empty so the writer takes the plain
    ``table.tex`` path.

    Per the IR contract, cell content is scalar text on the model; the inline
    runs of every cell travel on ``cells`` in HTML document order.
    """
    caption_el = tag.find("caption")
    caption: tuple[ir.Inline, ...] = ()
    if caption_el is not None:
        for span in list(caption_el.find_all("span")):
            if {"caption-prefix", "figure-prefix"}.intersection(classes(span.get("class"))):
                span.extract()
        caption = ctx.lower_inline(caption_el.children)
    label = coerce_attr(tag.get("id")) or ""

    model = tables.build_schema_table(tag)
    if model is None:
        # Degenerate table (e.g. a single column): keep it lossless as a Div
        # carrying the rendered cell text, and report the limitation.
        ctx.warn(
            "HtmlReader: table with fewer than 2 columns is not representable "
            "by the tables schema; preserved as a generic Div."
        )
        blocks = tuple(
            ir.Para(content=(ir.Str(" | ".join(cell for cell in row)),))
            for row in tables.extract_rows(tag)
            if row
        )
        return ir.Div(content=blocks, attrs=attrs_tuple({"role": "table-fallback"}))

    cells = _collect_cell_content(tag, ctx)

    if tables.is_rich(tag):
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
            for cell in tables.cell_tags(tr):
                out.append(ctx.lower_inline(cell.children))
    else:
        # Plain GFM tables may keep the header row directly under the table.
        first = tag.find("tr")
        if first is not None and first.find("th") is not None and first.find("td") is None:
            for cell in tables.cell_tags(first):
                out.append(ctx.lower_inline(cell.children))

    body, footer = tables.section_rows(tag)
    for tr in (*body, *footer):
        if tables.is_separator(tr):
            continue
        for cell in tables.cell_tags(tr):
            out.append(ctx.lower_inline(cell.children))

    return tuple(out)


__all__ = [
    "read_admonition",
    "read_blockquote_callout",
    "read_details_callout",
    "read_marginnote",
    "read_progressbar",
    "read_table",
]
