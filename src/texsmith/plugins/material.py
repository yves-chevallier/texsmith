"""Optional handlers for MkDocs Material specific constructs."""

from __future__ import annotations

from bs4 import Tag
from bs4.element import NavigableString

from ..context import RenderContext
from ..handlers import admonitions as base_admonitions
from ..rules import RenderPhase, renders

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
        correct_value = gap.get("answer") or gap.get("value") or ""
        size_hint = gap.get("size")
        try:
            width = (
                max(int(size_hint), 3)
                if size_hint is not None
                else max(len(correct_value), 3)
            )
        except ValueError:
            width = max(len(correct_value), 3)
        gap.replace_with(NavigableString(f"\\rule{{{width}ex}}{{0.4pt}}"))
        if correct_value:
            answers.append(str(correct_value))

    if note := element.find("p", class_="align--right"):
        note_text = note.get_text(strip=True)
        if note_text:
            answers.append(note_text)
        note.decompose()

    with base_admonitions._use_tcolorbox_figures(context):
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
    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)


@renders(
    "div",
    phase=RenderPhase.POST,
    priority=51,
    name="material_exercise_admonition",
    nestable=False,
)
def render_exercise_div(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "admonition" not in classes or "exercise" not in classes:
        return

    title = base_admonitions._extract_title(
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
    classes = element.get("class") or []
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
    nestable=False,
    auto_mark=False,
)
def render_epigraph(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "epigraph" not in classes:
        return

    source = None
    if footer := element.find("footer"):
        source = footer.get_text(strip=True)
        footer.decompose()

    text = element.get_text(strip=False)
    latex = context.formatter.epigraph(text=text, source=source)
    node = NavigableString(latex)
    node.processed = True
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


def register(renderer) -> None:
    """Register Material-specific exercise and epigraph handlers."""

    renderer.register(render_exercise_div)
    renderer.register(render_exercise_details)
    renderer.register(render_epigraph)


__all__ = [
    "register",
    "render_exercise_div",
    "render_exercise_details",
    "render_epigraph",
]
