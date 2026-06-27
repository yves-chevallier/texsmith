"""Block lowerings: structural HTML into block IR.

Each ``@reads(..., level=BLOCK)`` callable turns one block-level HTML tag into
a block IR node (or sequence), recursing into children via ``ctx.lower_blocks``
or ``ctx.lower_inline``. No LaTeX is produced. Backend-only concerns (asset
hashing, shell-escape detection, pygments style collection, font fallback) are
*not* the reader's job — they are derived later from the IR by the writer
(see the transverse-state map in ``ir/nodes.py``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from bs4.element import PageElement, Tag

from texsmith.adapters.transformers.mermaid_detect import (
    looks_like_mermaid as _looks_like_mermaid,
)
from texsmith.ir import nodes as ir

from ._helpers import attrs_tuple, classes, coerce_attr
from .registry import NotHandled, ReadLevel, reads


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .context import ReadContext
    from .registry import _NotHandledType


# ---------------------------------------------------------------------------
# Headings, paragraphs, rules
# ---------------------------------------------------------------------------


@reads("h1", "h2", "h3", "h4", "h5", "h6", level=ReadLevel.BLOCK, name="heading")
def read_heading(tag: Tag, ctx: ReadContext) -> ir.Header:
    level = int((tag.name or "h1")[1:])
    identifier = coerce_attr(tag.get("id")) or ""
    # Anchor links inside a heading (``headerlink``) are navigational chrome;
    # drop them and keep the textual content only.
    content = ctx.lower_inline(_without_header_anchors(tag))
    return ir.Header(level=level, content=content, identifier=identifier)


def _without_header_anchors(tag: Tag) -> list[PageElement]:
    kept: list[PageElement] = []
    for child in tag.children:
        if (
            isinstance(child, Tag)
            and child.name == "a"
            and "headerlink" in classes(child.get("class"))
        ):
            continue
        kept.append(child)
    return kept


@reads("p", level=ReadLevel.BLOCK, name="paragraph")
def read_paragraph(tag: Tag, ctx: ReadContext) -> ir.Block | None:
    cls = classes(tag.get("class"))

    # Raw LaTeX payload hidden in a paragraph (latex_raw extension).
    if "latex-raw" in cls:
        return ir.RawBlock(format="latex", text=tag.get_text())

    # data-script grouped paragraph.
    slug = coerce_attr(tag.get("data-script"))
    if slug:
        return ir.Div(
            content=(ir.Para(content=ctx.lower_inline(tag.children)),),
            attrs=attrs_tuple({"role": "script", "script": slug}),
        )

    content = _strip_edge_space(ctx.lower_inline(tag.children))
    if not content:
        return None
    return ir.Para(content=content)


def _strip_edge_space(inlines: tuple[ir.Inline, ...]) -> tuple[ir.Inline, ...]:
    """Drop leading/trailing inter-word ``Space`` from a paragraph's content."""

    def _edge(node: ir.Inline) -> bool:
        if isinstance(node, (ir.Space, ir.SoftBreak)):
            return True
        return isinstance(node, ir.Str) and not node.text.strip()

    start, end = 0, len(inlines)
    while start < end and _edge(inlines[start]):
        start += 1
    while end > start and _edge(inlines[end - 1]):
        end -= 1
    return inlines[start:end]


@reads("hr", level=ReadLevel.BLOCK, name="horizontal_rule")
def read_horizontal_rule(_tag: Tag, _ctx: ReadContext) -> ir.HorizontalRule:
    return ir.HorizontalRule()


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


@reads("ul", level=ReadLevel.BLOCK, name="bullet_list")
def read_bullet_list(tag: Tag, ctx: ReadContext) -> ir.Block:
    cls = classes(tag.get("class"))
    items = _list_items(tag, ctx)
    if "two-column-list" in cls or "three-column-list" in cls:
        columns = "2" if "two-column-list" in cls else "3"
        return ir.Div(
            content=(ir.BulletList(items=items),),
            attrs=attrs_tuple({"role": "multicolumn", "columns": columns}),
        )
    return ir.BulletList(items=items)


@reads("ol", level=ReadLevel.BLOCK, name="ordered_list")
def read_ordered_list(tag: Tag, ctx: ReadContext) -> ir.OrderedList:
    start_attr = coerce_attr(tag.get("start"))
    start = int(start_attr) if start_attr and start_attr.isdigit() else 1
    style = _ordered_style(coerce_attr(tag.get("type")))
    return ir.OrderedList(items=_list_items(tag, ctx), start=start, style=style)


def _ordered_style(type_attr: str | None) -> ir.ListStyle:
    return {
        "a": ir.ListStyle.LOWER_ALPHA,
        "A": ir.ListStyle.UPPER_ALPHA,
        "i": ir.ListStyle.LOWER_ROMAN,
        "I": ir.ListStyle.UPPER_ROMAN,
        "1": ir.ListStyle.DECIMAL,
    }.get(type_attr or "", ir.ListStyle.DECIMAL)


def _list_items(tag: Tag, ctx: ReadContext) -> tuple[tuple[ir.Block, ...], ...]:
    items: list[tuple[ir.Block, ...]] = []
    for li in tag.find_all("li", recursive=False):
        items.append(_list_item(li, ctx))
    return tuple(items)


def _list_item(li: Tag, ctx: ReadContext) -> tuple[ir.Block, ...]:
    # Task-list checkbox (pymdownx.tasklist): record it as a leading marker so
    # the writer can render a checked/unchecked box.
    checkbox = li.find("input", attrs={"type": "checkbox"})
    prefix: tuple[ir.Block, ...] = ()
    if checkbox is not None:
        checked = checkbox.has_attr("checked")
        # Represent the task marker as an empty Div hint; the writer turns it
        # into a checkbox glyph. Kept minimal to honour the IR (no LaTeX here).
        prefix = (
            ir.Div(
                content=(),
                attrs=attrs_tuple(
                    {"role": "task-marker", "checked": "true" if checked else "false"}
                ),
            ),
        )
        checkbox.extract()
    children = list(li.children)
    # A tight list item (no block-level child element) carries loose inline
    # content; represent it as a single Plain rather than a Para.
    if not _has_block_child(children):
        inline = ctx.lower_inline(children)
        body: tuple[ir.Block, ...] = (ir.Plain(content=inline),) if inline else ()
    else:
        body = ctx.lower_blocks(children)
    return (*prefix, *body)


def _has_block_child(children: list[PageElement]) -> bool:
    block_names = {
        "p",
        "ul",
        "ol",
        "dl",
        "pre",
        "blockquote",
        "div",
        "table",
        "figure",
        "details",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
    }
    return any(getattr(c, "name", None) in block_names for c in children)


# ---------------------------------------------------------------------------
# Definition lists
# ---------------------------------------------------------------------------


@reads("dl", level=ReadLevel.BLOCK, name="definition_list")
def read_definition_list(tag: Tag, ctx: ReadContext) -> ir.Block | None:
    items: list[ir.DefinitionItem] = []
    current_term: tuple[ir.Inline, ...] | None = None
    definitions: list[tuple[ir.Block, ...]] = []

    def flush() -> None:
        nonlocal current_term, definitions
        if current_term is not None:
            non_empty_defs = tuple(d for d in definitions if d)
            term_has_text = any(
                not (isinstance(n, ir.Str) and not n.text.strip())
                and not isinstance(n, (ir.Space, ir.SoftBreak))
                for n in current_term
            )
            # Drop a wholly-empty entry (empty term and no real definition).
            if term_has_text or non_empty_defs:
                items.append(ir.DefinitionItem(term=current_term, definitions=tuple(definitions)))
        current_term = None
        definitions = []

    for child in tag.find_all(["dt", "dd"], recursive=False):
        if child.name == "dt":
            flush()
            current_term = ctx.lower_inline(child.children)
        else:  # dd
            definitions.append(ctx.lower_blocks(child.children))
    flush()

    if not items:
        ctx.warn("HtmlReader: empty <dl> definition list discarded.")
        return None
    return ir.DefinitionList(items=tuple(items))


# ---------------------------------------------------------------------------
# Blockquotes
# ---------------------------------------------------------------------------


@reads("blockquote", level=ReadLevel.BLOCK, name="blockquote", priority=0)
def read_blockquote(tag: Tag, ctx: ReadContext) -> ir.Block:
    cls = classes(tag.get("class"))
    if "epigraph" in cls:
        footer = tag.find("footer")
        attrs = {"role": "epigraph"}
        if footer is not None:
            attrs["source"] = footer.get_text(strip=True)
            footer.extract()
        return ir.Div(
            content=ctx.lower_blocks(tag.children),
            attrs=attrs_tuple(attrs),
        )
    return ir.BlockQuote(content=ctx.lower_blocks(tag.children))


# ---------------------------------------------------------------------------
# Code blocks
# ---------------------------------------------------------------------------

_LANGUAGE_TOKEN = re.compile(r"^[A-Za-z0-9_+\-#.]+$")


@reads("pre", level=ReadLevel.BLOCK, name="preformatted")
def read_pre(tag: Tag, _ctx: ReadContext) -> ir.Block:
    code = tag.find("code")
    target = code if code is not None else tag
    source_hint = coerce_attr(tag.get("data-mermaid-source"))
    if (
        "mermaid" in classes(tag.get("class"))
        or _looks_like_mermaid(target.get_text())
        or source_hint
    ):
        # Diagram source: kept as a code block with the mermaid language so the
        # backend (a writer/diagram concern) can recognise it. Lossless, no
        # LaTeX produced here. A ``width`` attribute (``{ width=20% }``) and a
        # ``data-mermaid-source`` hint are carried on a wrapping diagram Div.
        block = ir.CodeBlock(text=_ensure_newline(target.get_text()), lang="mermaid")
        width = coerce_attr(tag.get("width"))
        if width or source_hint:
            hint = {"role": "diagram"}
            if width:
                hint["width"] = width
            if source_hint:
                hint["source"] = source_hint
            return ir.Div(content=(block,), attrs=attrs_tuple(hint))
        return block
    lang = _language(target)
    text = _code_listing_text(target if code is not None else tag)
    return ir.CodeBlock(text=_ensure_newline(text), lang=lang)


@reads("div", level=ReadLevel.BLOCK, name="code_block_div", priority=40)
def read_code_block_div(tag: Tag, _ctx: ReadContext) -> ir.CodeBlock | _NotHandledType:
    cls = classes(tag.get("class"))
    if "highlight" not in cls and "codehilite" not in cls:
        return NotHandled
    code = tag.find("code")
    if code is None:
        return NotHandled
    code_cls = classes(code.get("class"))
    if (
        "mermaid" in cls
        or {"language-mermaid", "mermaid"}.intersection(code_cls)
        or _looks_like_mermaid(code.get_text())
    ):
        return ir.CodeBlock(text=_ensure_newline(code.get_text()), lang="mermaid")
    lang = _language(code)
    if lang == "text":
        lang = _language(tag)
    lineno = tag.find(class_="linenos") is not None
    filename = ""
    if filename_el := tag.find(class_="filename"):
        filename = filename_el.get_text(strip=True)
    text, highlight = _code_listing(code)
    return ir.CodeBlock(
        text=_ensure_newline(text),
        lang=lang,
        highlight=tuple(highlight),
        lineno=lineno,
        filename=filename,
    )


def _language(tag: Tag) -> str:
    for cls in classes(tag.get("class")):
        if cls.startswith("language-"):
            return cls[len("language-") :] or "text"
    if "highlight" in classes(tag.get("class")):
        return "text"
    return "text"


def _code_listing(code: Tag) -> tuple[str, list[int]]:
    spans = code.find_all("span", id=lambda v: bool(v and v.startswith("__")))
    if not spans:
        return code.get_text(), []
    lines: list[str] = []
    highlight: list[int] = []
    for index, span in enumerate(spans, start=1):
        hll = span.find("span", class_="hll")
        if hll is not None:
            highlight.append(index)
            lines.append(hll.get_text())
        else:
            lines.append(span.get_text())
    return "".join(lines), highlight


def _code_listing_text(tag: Tag) -> str:
    text, _ = _code_listing(tag)
    return text


def _ensure_newline(text: str) -> str:
    if text and not text.endswith("\n"):
        return text + "\n"
    return text


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


@reads("figure", level=ReadLevel.BLOCK, name="figure")
def read_figure(tag: Tag, ctx: ReadContext) -> ir.Block:
    caption_el = tag.find("figcaption")
    caption: tuple[ir.Inline, ...] = ()
    if caption_el is not None:
        _strip_caption_prefix(caption_el)
        caption = ctx.lower_inline(_caption_inline_children(caption_el))
    identifier = coerce_attr(tag.get("id")) or ""
    body_children = [c for c in tag.children if getattr(c, "name", None) != "figcaption"]
    content = ctx.lower_blocks(body_children)
    if not content:
        # A figure wrapping a bare inline image: lift the image into a block.
        inline = ctx.lower_inline(body_children)
        content = (ir.Plain(content=inline),) if inline else ()
    return ir.Figure(content=content, caption=caption, identifier=identifier)


def _caption_inline_children(caption_el: Tag) -> list[PageElement]:
    """Flatten a caption's children, unwrapping a sole wrapping ``<p>``."""
    children = list(caption_el.children)
    tags = [c for c in children if isinstance(c, Tag)]
    if len(tags) == 1 and tags[0].name == "p":
        return list(tags[0].children)
    return children


def _strip_caption_prefix(node: Tag) -> None:
    for span in list(node.find_all("span")):
        if {"caption-prefix", "figure-prefix"}.intersection(classes(span.get("class"))):
            span.extract()


# ---------------------------------------------------------------------------
# Generic divs (math block, grid-cards, tabbed, multicolumn, footnotes, …)
# ---------------------------------------------------------------------------


@reads("div", level=ReadLevel.BLOCK, name="div", priority=0)
def read_div(tag: Tag, ctx: ReadContext) -> ir.Block | list[ir.Block] | None:
    cls = classes(tag.get("class"))

    # Block math payload (arithmatex / mdx_math): keep raw TeX source.
    if "arithmatex" in cls:
        return _block_math(tag)

    # Footnote definitions container: preserve each definition's identifier so
    # the writer (which owns the footnote/citation registries) can resolve
    # ``footnote-ref`` sites against the bodies. Back-ref anchors are dropped by
    # ``read_link``; the ``<li id>`` ids are carried on per-definition Divs.
    if "footnote" in cls:
        return ir.Div(
            content=_footnote_defs(tag, ctx),
            attrs=attrs_tuple({"role": "footnotes"}),
        )

    # Containers that are pure layout wrappers: unwrap transparently.
    if {"grid-cards", "latex-ignore"}.intersection(cls):
        if "latex-ignore" in cls:
            return None
        return list(ctx.lower_blocks(tag.children))

    if "tabbed-set" in cls:
        return _tabbed_set(tag, ctx)

    if "two-column-list" in cls or "three-column-list" in cls:
        columns = "2" if "two-column-list" in cls else "3"
        return ir.Div(
            content=ctx.lower_blocks(tag.children),
            attrs=attrs_tuple({"role": "multicolumn", "columns": columns}),
        )

    # Generic div: preserve its classes as a hint.
    attrs = {"class": " ".join(cls)} if cls else {}
    return ir.Div(content=ctx.lower_blocks(tag.children), attrs=attrs_tuple(attrs))


def _footnote_defs(tag: Tag, ctx: ReadContext) -> tuple[ir.Block, ...]:
    """Lower each ``<li id="fn:…">`` body into an id-tagged ``Div``."""
    defs: list[ir.Block] = []
    for li in tag.find_all("li", id=True):
        identifier = coerce_attr(li.get("id")) or ""
        defs.append(
            ir.Div(
                content=ctx.lower_blocks(li.children),
                attrs=attrs_tuple({"role": "footnote-def", "id": identifier}),
            )
        )
    return tuple(defs)


def _block_math(tag: Tag) -> ir.Plain:
    """Wrap a display-math payload in a Plain block (Math is an Inline node)."""
    return ir.Plain(content=(ir.Math(text=_strip_block_math(tag.get_text()), display=True),))


def _strip_block_math(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith(r"\[") and stripped.endswith(r"\]"):
        return stripped[2:-2].strip()
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return stripped[2:-2].strip()
    return stripped


def _tabbed_set(tag: Tag, ctx: ReadContext) -> ir.Div:
    """Lower a Material tabbed-set into a Div carrying labelled tab blocks."""
    labels: list[str] = []
    label_box = tag.find("div", class_="tabbed-labels")
    if label_box is not None:
        labels = [lbl.get_text(strip=True) for lbl in label_box.find_all("label")]
    else:
        # pymdownx.tabbed (legacy/alternate style) emits bare ``<label>`` and
        # ``<input>`` siblings rather than a ``tabbed-labels`` box.
        labels = [lbl.get_text(strip=True) for lbl in tag.find_all("label", recursive=False)]

    content_boxes = tag.find_all("div", class_="tabbed-content", recursive=False)
    if not content_boxes:
        candidate = tag.find("div", class_="tabbed-content")
        content_boxes = [candidate] if candidate is not None else []

    blocks: list[Tag] = []
    for box in content_boxes:
        inner = box.find_all("div", class_="tabbed-block", recursive=False)
        if inner:
            blocks.extend(inner)
        else:
            blocks.append(box)

    tab_blocks: list[ir.Block] = []
    for index, block in enumerate(blocks):
        title = labels[index] if index < len(labels) else ""
        tab_blocks.append(
            ir.Div(
                content=ctx.lower_blocks(block.children),
                attrs=attrs_tuple({"role": "tab", "title": title}),
            )
        )
    return ir.Div(content=tuple(tab_blocks), attrs=attrs_tuple({"role": "tabbed-set"}))


__all__ = [
    "read_blockquote",
    "read_bullet_list",
    "read_code_block_div",
    "read_definition_list",
    "read_div",
    "read_figure",
    "read_heading",
    "read_horizontal_rule",
    "read_ordered_list",
    "read_paragraph",
    "read_pre",
]
