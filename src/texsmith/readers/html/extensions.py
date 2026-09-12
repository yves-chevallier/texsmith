"""Extension lowerings: TeXSmith / Material constructs into the generated models.

These mirror the HTML→semantic half of ``extensions/*/renderer.py`` and the
Material plugin handlers, returning the nodes ``tmark.parse`` gives the same
constructs:

* admonitions / callouts — ``div.admonition``, ``<details>`` callouts (the
  ``collapsed`` attribute), and ``> [!TYPE]`` blockquote callouts →
  :class:`~texsmith.ir.model.Admonition`;
* margin notes — ``<ts-marginnote data-side>`` → :class:`~texsmith.ir.model.Aside`;
* progress bars — ``div.progress`` → a paragraph holding the inline
  :class:`~texsmith.ir.model.ProgressBar`;
* snippet fences — ``.snippet`` blocks → a ``CodeBlock{lang=snippet}`` for
  the ``snippet`` pass;
* tables — ``<table>`` (yaml ``data-ts-*`` or plain GFM) →
  :class:`~texsmith.ir.model.Table` with its :class:`~texsmith.ir.model.TableModel`
  (:mod:`.tables`), followed by the ``Table:`` caption when there is one.

(Index, TeX logos and keystrokes are inline constructs handled in
:mod:`.inline` because they originate from ``<span>``.)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from texsmith.ir import model
from texsmith.ir.walk import plain_text

from . import tables
from ._helpers import classes, coerce_attr, make_attrs
from .blocks import strip_caption_prefix
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
def read_snippet(tag: Tag, _ctx: ReadContext) -> model.CodeBlock | _NotHandledType:
    """A ``.snippet`` code fence (file-inclusion preview).

    The snippet block is the snippet plugin's own format (a fenced YAML/markup
    payload describing documents to render into an embedded preview). It is
    kept as the fence it came from — ``CodeBlock{lang=snippet}`` with the
    block's ``data-*`` attributes as options — for the ``snippet`` pass.
    """
    pre = tag.find("pre")
    code = tag.find("code")
    cls = set(classes(tag.get("class")))
    cls.update(classes(pre.get("class") if pre is not None else None))
    cls.update(classes(code.get("class") if code is not None else None))
    if "snippet" not in cls:
        return NotHandled
    options: dict[str, str | None] = {}
    for host in (tag, pre, code):
        if host is None:
            continue
        for key, value in host.attrs.items():
            if key.startswith("data-"):
                options.setdefault(key[len("data-") :], coerce_attr(value))
    text = code.get_text() if code is not None else tag.get_text()
    return model.CodeBlock(text=text, lang="snippet", options=make_attrs(kv=options))


# ---------------------------------------------------------------------------
# Admonitions / callouts
# ---------------------------------------------------------------------------


@reads("div", level=ReadLevel.BLOCK, name="admonition", priority=100)
def read_admonition(tag: Tag, ctx: ReadContext) -> model.Admonition | _NotHandledType:
    cls = classes(tag.get("class"))
    if "admonition" not in cls:
        return NotHandled
    title_el = tag.find("p", class_="admonition-title")
    title: tuple[model.Inline, ...] | None = None
    body_children = list(tag.children)
    if title_el is not None:
        title = ctx.inline_content(title_el)
        body_children = [c for c in body_children if c is not title_el]
    return model.Admonition(
        kind=_admonition_kind(cls),
        title=title,
        content=ctx.lower_blocks(body_children),
        attrs=make_attrs(id=coerce_attr(tag.get("id"))),
    )


@reads("details", level=ReadLevel.BLOCK, name="details_callout", priority=100)
def read_details_callout(tag: Tag, ctx: ReadContext) -> model.Admonition:
    """A ``<details>`` block: a callout with the ``collapsed`` attribute."""
    cls = classes(tag.get("class"))
    summary = tag.find("summary")
    title: tuple[model.Inline, ...] | None = None
    body_children = list(tag.children)
    if summary is not None:
        title = ctx.inline_content(summary)
        body_children = [c for c in body_children if c is not summary]
    collapsed = "false" if tag.has_attr("open") else "true"
    return model.Admonition(
        kind=_admonition_kind(cls),
        title=title,
        content=ctx.lower_blocks(body_children),
        attrs=make_attrs(id=coerce_attr(tag.get("id")), kv={"collapsed": collapsed}),
    )


@reads("blockquote", level=ReadLevel.BLOCK, name="blockquote_callout", priority=50)
def read_blockquote_callout(tag: Tag, ctx: ReadContext) -> model.Admonition | _NotHandledType:
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
    content: list[model.Block] = []
    if len(lines) > 1:
        content.append(model.Para(content=(model.Str(" ".join(lines[1:])),)))
    body_children = [c for c in tag.children if c is not first_p]
    content.extend(ctx.lower_blocks(body_children))
    return model.Admonition(
        kind=kind,
        title=(model.Str(title_text),) if title_text else None,
        content=tuple(content),
    )


def _admonition_kind(cls: list[str]) -> str:
    candidates = [c for c in cls if c not in _ADMONITION_NOISE]
    return candidates[0] if candidates else "note"


# ---------------------------------------------------------------------------
# Margin notes (asides)
# ---------------------------------------------------------------------------


_SIDES = {
    "l": model.Side.LEFT,
    "left": model.Side.LEFT,
    "r": model.Side.RIGHT,
    "right": model.Side.RIGHT,
    "i": model.Side.INNER,
    "inner": model.Side.INNER,
    "o": model.Side.OUTER,
    "outer": model.Side.OUTER,
}


@reads("ts-marginnote", level=ReadLevel.ANY, name="marginnote")
def read_marginnote(tag: Tag, ctx: ReadContext) -> model.Aside:
    side = _SIDES.get((coerce_attr(tag.get("data-side")) or "").strip().lower())
    # Aside bodies are inline-flavoured; wrap them in a Plain block so the
    # contract (``Aside.content`` is a block tuple) is honoured.
    inline = ctx.inline_content(tag)
    return model.Aside(content=(model.Plain(content=inline),) if inline else (), side=side)


# ---------------------------------------------------------------------------
# Progress bars
# ---------------------------------------------------------------------------


@reads("div", level=ReadLevel.BLOCK, name="progressbar", priority=90)
def read_progressbar(tag: Tag, ctx: ReadContext) -> model.Para | _NotHandledType:
    cls = classes(tag.get("class"))
    if "progress" not in cls:
        return NotHandled
    bar = tag.find("div", class_="progress-bar")
    if bar is None:
        return NotHandled
    label_el = bar.find("p", class_="progress-label")
    label = plain_text(ctx.inline_content(label_el)).strip() if label_el is not None else ""
    thin = "thin" in cls or "progress-thin" in cls
    extra = [c for c in cls if c != "thin" and not c.startswith("progress")]
    node = model.ProgressBar(
        value=max(0.0, min(100.0, _progress_percent(tag, bar))),
        attrs=make_attrs(classes=(*(["thin"] if thin else []), *extra)),
        label=label or None,
    )
    return model.Para(content=(node,))


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
def read_table(tag: Tag, ctx: ReadContext) -> tuple[model.Block, ...]:
    """Lower a ``<table>`` into a ``Table`` followed by its ``Caption``.

    The structure (column groups, spans, separators, settings) is rebuilt by
    :func:`~.tables.build_schema_table` and expanded into the leaf matrix
    :class:`~texsmith.ir.model.TableModel` holds, cell content lowered to
    inline nodes. A ``<caption>`` becomes the ``Table:`` caption line after
    the table and carries the anchor, as in tmark; without a caption the
    anchor stays on the table. A table the schema cannot model (fewer than two
    columns) is kept lossless as a ``Div`` with a ``reader-unsupported``
    diagnostic.
    """
    caption_el = tag.find("caption")
    identifier = coerce_attr(tag.get("id"))

    schema_table = tables.build_schema_table(tag)
    if schema_table is None:
        ctx.warn(
            "table with fewer than 2 columns is not representable by the tables "
            "schema; preserved as a generic Div"
        )
        rows = tuple(
            model.Para(content=(model.Str(" | ".join(row)),))
            for row in tables.extract_rows(tag)
            if row
        )
        return (
            model.Div(
                name="div",
                attrs=make_attrs(id=identifier, kv={"role": "table-fallback"}),
                content=rows,
            ),
        )

    caption: model.Caption | None = None
    if caption_el is not None:
        strip_caption_prefix(caption_el)
        caption = model.Caption(
            kind=model.CaptionKind.TABLE,
            attrs=make_attrs(id=identifier),
            content=ctx.inline_content(caption_el),
        )
        caption_el.extract()

    table = model.Table(
        attrs=make_attrs(id=identifier if caption is None else None),
        model=tables.to_model(schema_table, tag, ctx.inline_content),
    )
    return (table, caption) if caption is not None else (table,)


__all__ = [
    "read_admonition",
    "read_blockquote_callout",
    "read_details_callout",
    "read_marginnote",
    "read_progressbar",
    "read_snippet",
    "read_table",
]
