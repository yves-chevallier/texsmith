"""Built-in baseline handlers used by the renderer."""

from __future__ import annotations

from bs4 import NavigableString, Tag

from ..context import RenderContext
from ..rules import RenderPhase, renders


UNWANTED_NODES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("html", (), "unwrap"),
    ("head", (), "decompose"),
    ("body", (), "unwrap"),
    ("a", ("headerlink", "footnote-backref"), "extract"),
    ("a", ("glightbox",), "unwrap"),
    ("div", ("latex-ignore",), "extract"),
    ("span", ("exercise-title",), "unwrap"),
    ("div", ("exercise-checkbox",), "extract"),
    ("figure", ("mermaid-figure",), "extract"),
)


def _merge_strip_rules(
    context: RenderContext,
) -> list[tuple[str, tuple[str, ...], str]]:
    """Merge default strip rules with runtime overrides."""

    rules: dict[tuple[str, tuple[str, ...]], str] = {
        (tag, classes): mode for tag, classes, mode in UNWANTED_NODES
    }

    runtime_rules = context.runtime.get("strip_tags") or {}
    if isinstance(runtime_rules, dict):
        for tag_name, payload in runtime_rules.items():
            if isinstance(payload, str):
                mode = payload
                classes: tuple[str, ...] = ()
            elif isinstance(payload, dict):
                mode = payload.get("mode", "unwrap")
                classes_value = payload.get("classes", ())
                if isinstance(classes_value, str):
                    classes = (classes_value,)
                else:
                    classes = tuple(classes_value)
            else:
                continue
            if mode not in {"unwrap", "extract", "decompose"}:
                continue
            rules[(tag_name, classes)] = mode

    merged = [(tag, classes, rules[(tag, classes)]) for tag, classes in rules]
    return merged


@renders(phase=RenderPhase.PRE, auto_mark=False, name="discard_unwanted")
def discard_unwanted(root: Tag, context: RenderContext) -> None:
    """Discard or unwrap nodes that must not reach later phases."""

    for tag_name, classes, mode in _merge_strip_rules(context):
        kwargs: dict[str, object] = {}
        if classes:
            kwargs["class_"] = list(classes)
        for node in root.find_all(tag_name, **kwargs):
            if mode == "unwrap":
                node.unwrap()
            elif mode == "extract":
                node.extract()
            elif mode == "decompose":
                node.decompose()


@renders("hr", phase=RenderPhase.PRE, name="remove_horizontal_rules")
def remove_horizontal_rules(element: Tag, context: RenderContext) -> None:
    """Remove ``<hr>`` nodes early during preprocessing."""

    element.extract()


@renders("br", phase=RenderPhase.INLINE, name="line_breaks")
def replace_line_breaks(element: Tag, context: RenderContext) -> None:
    """Convert ``<br>`` tags into explicit LaTeX line breaks."""

    node = NavigableString("\\")
    node.processed = True
    element.replace_with(node)


@renders("ins", phase=RenderPhase.INLINE, name="inline_underline", after_children=True)
def render_inline_underline(element: Tag, context: RenderContext) -> None:
    """Render ``<ins>`` tags using the formatter."""

    text = element.get_text(strip=False)
    latex = context.formatter.underline(text=text)
    element.replace_with(NavigableString(latex))


@renders("strong", phase=RenderPhase.INLINE, name="inline_strong", after_children=True)
def render_inline_strong(element: Tag, context: RenderContext) -> None:
    """Render ``<strong>`` tags using bold template."""

    text = element.get_text(strip=False)
    latex = context.formatter.strong(text=text)
    element.replace_with(NavigableString(latex))


@renders("em", phase=RenderPhase.INLINE, name="inline_emphasis", after_children=True)
def render_inline_emphasis(element: Tag, context: RenderContext) -> None:
    """Render ``<em>`` tags using emphasis template."""

    text = element.get_text(strip=False)
    latex = context.formatter.italic(text=text)
    element.replace_with(NavigableString(latex))


@renders("del", phase=RenderPhase.INLINE, name="inline_deletion", after_children=True)
def render_inline_deletion(element: Tag, context: RenderContext) -> None:
    """Render ``<del>`` tags using strikethrough template."""

    text = element.get_text(strip=False)
    latex = context.formatter.strikethrough(text=text)
    element.replace_with(NavigableString(latex))


@renders("mark", phase=RenderPhase.INLINE, name="inline_mark", after_children=True)
def render_inline_mark(element: Tag, context: RenderContext) -> None:
    """Render ``<mark>`` tags using highlight template."""

    text = element.get_text(strip=False)
    latex = context.formatter.highlight(text=text)
    element.replace_with(NavigableString(latex))


@renders("sub", phase=RenderPhase.INLINE, name="inline_subscript", after_children=True)
def render_inline_subscript(element: Tag, context: RenderContext) -> None:
    """Render ``<sub>`` tags."""

    text = element.get_text(strip=False)
    latex = context.formatter.subscript(text=text)
    element.replace_with(NavigableString(latex))


@renders(
    "sup", phase=RenderPhase.INLINE, name="inline_superscript", after_children=True
)
def render_inline_superscript(element: Tag, context: RenderContext) -> None:
    """Render ``<sup>`` tags, skipping footnote references."""

    if element.get("id"):
        return

    text = element.get_text(strip=False)
    latex = context.formatter.superscript(text=text)
    element.replace_with(NavigableString(latex))


@renders("div", phase=RenderPhase.BLOCK, name="grid_cards", auto_mark=False)
def unwrap_grid_cards(element: Tag, context: RenderContext) -> None:
    """Unwrap ``div.grid-cards`` containers."""

    classes = element.get("class") or []
    if "grid-cards" in classes:
        element.unwrap()


@renders(
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    phase=RenderPhase.POST,
    name="render_headings",
)
def render_headings(element: Tag, context: RenderContext) -> None:
    """Convert HTML headings to LaTeX sectioning commands."""

    # Drop anchor tags within headings
    for anchor in element.find_all("a"):
        anchor.unwrap()

    drop_title = context.runtime.get("drop_title")
    if drop_title:
        context.runtime["drop_title"] = False
        latex = context.formatter.pagestyle(text="plain")
        node = NavigableString(latex)
        node.processed = True
        element.replace_with(node)
        return

    text = element.get_text(strip=False)
    plain_text = element.get_text(strip=True)
    level = int(element.name[1:])
    base_level = context.runtime.get("base_level", 0)
    rendered_level = level + base_level - 1
    ref = element.get("id")
    numbered = context.runtime.get("numbered", True)

    latex = context.formatter.heading(
        text=text,
        level=rendered_level,
        ref=ref,
        numbered=numbered,
    )

    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)

    context.state.add_heading(level=rendered_level, text=plain_text, ref=ref)
