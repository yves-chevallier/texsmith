"""Handlers for generic admonition and callout markup."""

from __future__ import annotations

from contextlib import contextmanager

from bs4 import Tag
from bs4.element import NavigableString

from ..context import RenderContext
from ..rules import RenderPhase, renders


IGNORED_CLASSES = {
    "admonition",
    "annotate",
    "inline",
    "end",
    "left",
    "right",
    "checkbox",
}


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
    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)


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

    classes = element.get("class") or []
    if "admonition" not in classes:
        return
    if "exercise" in classes:
        return

    title = _extract_title(element.find("p", class_="admonition-title"))
    _render_admonition(element, context, classes=classes, title=title)


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

    classes = element.get("class") or []
    if "exercise" in classes:
        return

    title = ""
    if summary := element.find("summary"):
        title = summary.get_text(strip=True)
        summary.decompose()

    _render_admonition(element, context, classes=classes, title=title or "")


__all__ = [
    "render_div_admonitions",
    "render_details_admonitions",
    "_extract_title",
    "_use_tcolorbox_figures",
]
