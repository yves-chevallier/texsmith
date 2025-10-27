"""Handlers for generic admonition and callout markup."""

from __future__ import annotations

from contextlib import contextmanager
import re

from bs4.element import NavigableString, Tag

from ..context import RenderContext
from ..rules import RenderPhase, renders
from ._helpers import gather_classes, mark_processed


IGNORED_CLASSES = {
    "admonition",
    "annotate",
    "inline",
    "end",
    "left",
    "right",
    "checkbox",
}


def _trim_paragraph_prefix(paragraph: Tag, length: int) -> None:
    """Remove the first ``length`` characters from a paragraph in-place."""
    remaining = length
    for node in list(paragraph.descendants):
        if not isinstance(node, NavigableString):
            continue
        text = str(node)
        if remaining >= len(text):
            remaining -= len(text)
            node.extract()
            if remaining == 0:
                break
            continue
        node.replace_with(NavigableString(text[remaining:]))
        remaining = 0
        break


@contextmanager
def _use_tcolorbox_figures(context: RenderContext):
    """Render nested figures inside callouts with the tcolorbox template."""
    previous = context.runtime.get("figure_template")
    context.runtime["figure_template"] = "figure_tcolorbox"
    try:
        yield
    finally:
        if previous is None:
            context.runtime.pop("figure_template", None)
        else:
            context.runtime["figure_template"] = previous


def _extract_title(node: Tag | None) -> str:
    """Extract and remove the title paragraph produced by MkDocs Material."""
    if node is None:
        return ""
    if label := node.find("span", class_="exercise-label"):
        label.decompose()
    title = node.get_text(strip=True)
    node.decompose()
    return title


def _render_admonition(
    element: Tag, context: RenderContext, *, classes: list[str], title: str
) -> None:
    """Convert a generic admonition container into a LaTeX callout."""
    admonition_classes = [cls for cls in classes if cls not in IGNORED_CLASSES]
    admonition_type = admonition_classes[0] if admonition_classes else "note"

    with _use_tcolorbox_figures(context):
        content = element.get_text(strip=False).strip()

    latex = context.formatter.callout(content, title=title, type=admonition_type)
    parent = element.parent
    replacement = mark_processed(NavigableString(latex))
    if parent is None:
        element.decompose()
        context.document.append(replacement)
    else:
        element.replace_with(replacement)


@renders(
    "div",
    phase=RenderPhase.POST,
    priority=50,
    name="admonitions",
    nestable=False,
    auto_mark=False,
)
def render_div_admonitions(element: Tag, context: RenderContext) -> None:
    """Handle MkDocs Material admonition blocks."""
    classes = gather_classes(element.get("class"))
    if "admonition" not in classes:
        return
    if "exercise" in classes:
        return

    title = _extract_title(element.find("p", class_="admonition-title"))
    _render_admonition(element, context, classes=classes, title=title)


@renders(
    "blockquote",
    phase=RenderPhase.POST,
    priority=15,
    name="blockquote_callouts",
    nestable=False,
    auto_mark=False,
)
def render_blockquote_callouts(element: Tag, context: RenderContext) -> None:
    """Handle Obsidian/Docusaurus style blockquote callouts."""
    first_paragraph = element.find("p")
    if first_paragraph is None:
        return

    first_text_node = next(
        (child for child in first_paragraph.contents if isinstance(child, NavigableString)),
        None,
    )
    if first_text_node is None:
        return

    raw_text = str(first_text_node)
    stripped = raw_text.lstrip()
    offset = len(raw_text) - len(stripped)
    match = CALLOUT_PATTERN.match(stripped)
    if not match:
        return

    callout_type = match.group("kind").lower()
    remainder = match.group("content") or ""
    remainder = remainder.lstrip()

    first_text_node.replace_with(NavigableString(raw_text[:offset] + remainder))

    lines_with_endings = remainder.splitlines(keepends=True)
    lines = [line.strip() for line in remainder.splitlines() if line.strip()]
    title = lines[0] if lines else callout_type.capitalize()

    if len(lines_with_endings) > 1:
        prefix_length = len(raw_text[:offset]) + len(lines_with_endings[0])
        _trim_paragraph_prefix(first_paragraph, prefix_length)
        first_text = next(
            (child for child in first_paragraph.contents if isinstance(child, NavigableString)),
            None,
        )
        if first_text is not None:
            first_text.replace_with(NavigableString(str(first_text).lstrip()))
    else:
        first_paragraph.decompose()

    _render_admonition(element, context, classes=[callout_type], title=title)
    context.mark_processed(element, phase=RenderPhase.POST)


@renders(
    "details",
    phase=RenderPhase.POST,
    priority=55,
    name="details_admonitions",
    nestable=False,
    auto_mark=False,
)
def render_details_admonitions(element: Tag, context: RenderContext) -> None:
    """Handle collapsible callouts converted from MkDocs Material's details blocks."""
    classes = gather_classes(element.get("class"))
    if "exercise" in classes:
        return

    title = ""
    if summary := element.find("summary"):
        title = summary.get_text(strip=True)
        summary.decompose()

    _render_admonition(element, context, classes=classes, title=title or "")


__all__ = [
    "_extract_title",
    "_use_tcolorbox_figures",
    "render_blockquote_callouts",
    "render_details_admonitions",
    "render_div_admonitions",
]
CALLOUT_PATTERN = re.compile(r"^\s*\[!(?P<kind>[A-Za-z0-9_-]+)\]\s*(?P<content>.*)$", re.DOTALL)
