"""Optional handlers for MkDocs Material specific constructs."""

from __future__ import annotations

from typing import Any

from bs4.element import NavigableString, Tag

from texsmith.core.context import RenderContext
from texsmith.core.rules import RenderPhase, renders

from ..handlers import admonitions as base_admonitions
from ..handlers._helpers import coerce_attribute, gather_classes, mark_processed


EXERCISE_IGNORED_CLASSES = {
    "admonition",
    "annotate",
    "inline",
    "end",
    "left",
    "right",
    "checkbox",
    "fill-in-the-blank",
}


def _gather_solutions(container: Tag) -> list[str]:
    solutions: list[str] = []
    for details in container.find_all("details", class_="solution"):
        if summary := details.find("summary"):
            summary.decompose()
        solutions.append(details.get_text(strip=False).strip())
        details.decompose()
    return solutions


def _render_exercise(
    element: Tag, context: RenderContext, *, classes: list[str], title: str
) -> None:
    callout_classes = [cls for cls in classes if cls not in EXERCISE_IGNORED_CLASSES]
    callout_type = callout_classes[0] if callout_classes else "exercise"

    solutions = _gather_solutions(element)
    answers: list[str] = []

    for gap in element.find_all("input", class_="text-with-gap"):
        correct_value = (
            coerce_attribute(gap.get("answer")) or coerce_attribute(gap.get("value")) or ""
        )
        size_hint = coerce_attribute(gap.get("size"))
        try:
            width = max(int(size_hint), 3) if size_hint is not None else max(len(correct_value), 3)
        except ValueError:
            width = max(len(correct_value), 3)
        gap.replace_with(mark_processed(NavigableString(f"\\rule{{{width}ex}}{{0.4pt}}")))
        if correct_value:
            answers.append(correct_value)

    if note := element.find("p", class_="align--right"):
        note_text = note.get_text(strip=True)
        if note_text:
            answers.append(note_text)
        note.decompose()

    with base_admonitions._use_tcolorbox_figures(context):  # noqa: SLF001
        content = element.get_text(strip=False).strip()

    if solutions or answers:
        exercise_index = context.state.next_exercise()
        exercise_label = f"ex:{exercise_index}"
        solution_label = f"sol:{exercise_index}"

        solution_parts = [f"\\label{{{solution_label}}}"]
        solution_parts.extend(solutions)
        if answers:
            label = "Réponse" if len(answers) == 1 else "Réponses"
            solution_parts.append(f"{label}: {', '.join(answers)}")

        context.state.add_solution(
            {
                "index": exercise_index,
                "title": title,
                "label": exercise_label,
                "solution": "\n".join(part for part in solution_parts if part),
            }
        )

        title = f"\\hyperref[{solution_label}]{{{title}}}"
        content = f"\\label{{{exercise_label}}}\n{content}"

    latex = context.formatter.callout(content, title=title, type=callout_type)
    element.replace_with(mark_processed(NavigableString(latex)))


@renders(
    "div",
    phase=RenderPhase.POST,
    priority=51,
    name="material_exercise_admonition",
    nestable=False,
)
def render_exercise_div(element: Tag, context: RenderContext) -> None:
    """Render Material exercise admonitions into LaTeX callouts."""
    classes = gather_classes(element.get("class"))
    if "admonition" not in classes or "exercise" not in classes:
        return

    title = base_admonitions._extract_title(  # noqa: SLF001
        element.find("p", class_="admonition-title")
    )
    _render_exercise(element, context, classes=classes, title=title)


@renders(
    "details",
    phase=RenderPhase.POST,
    priority=56,
    name="material_exercise_details",
    nestable=False,
)
def render_exercise_details(element: Tag, context: RenderContext) -> None:
    """Render exercise blocks authored using <details> markup."""
    classes = gather_classes(element.get("class"))
    if "exercise" not in classes:
        return

    title = ""
    if summary := element.find("summary"):
        title = summary.get_text(strip=True)
        summary.decompose()

    _render_exercise(element, context, classes=classes, title=title or "")


@renders(
    "blockquote",
    phase=RenderPhase.POST,
    priority=10,
    name="material_epigraphs",
    auto_mark=False,
)
def render_epigraph(element: Tag, context: RenderContext) -> None:
    """Render Material epigraph blockquotes using the LaTeX epigraph macro."""
    classes = gather_classes(element.get("class"))
    if "epigraph" not in classes:
        return

    source = None
    if footer := element.find("footer"):
        source = footer.get_text(strip=True)
        footer.decompose()

    text = element.get_text(strip=False)
    latex = context.formatter.epigraph(text=text, source=source)
    node = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


def register(renderer: Any) -> None:
    """Register Material-specific exercise and epigraph handlers."""
    renderer.register(render_exercise_div)
    renderer.register(render_exercise_details)
    renderer.register(render_epigraph)


__all__ = [
    "register",
    "render_epigraph",
    "render_exercise_details",
    "render_exercise_div",
]
