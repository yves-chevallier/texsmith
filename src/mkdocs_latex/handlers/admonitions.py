"""Handlers for admonitions and exercises."""

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
    "fill-in-the-blank",
}


@contextmanager
def _use_tcolorbox_figures(context: RenderContext):
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
    if node is None:
        return ""
    if label := node.find("span", class_="exercise-label"):
        label.decompose()
    title = node.get_text(strip=True)
    node.decompose()
    return title


def _gather_solutions(container: Tag) -> list[str]:
    solutions: list[str] = []
    for details in container.find_all("details", class_="solution"):
        if summary := details.find("summary"):
            summary.decompose()
        solutions.append(details.get_text(strip=False).strip())
        details.decompose()
    return solutions


def _render_admonition(
    element: Tag, context: RenderContext, *, classes: list[str], title: str
) -> None:
    admonition_classes = [cls for cls in classes if cls not in IGNORED_CLASSES]
    admonition_type = admonition_classes[0] if admonition_classes else "note"

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

    with _use_tcolorbox_figures(context):
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

    latex = context.formatter.callout(content, title=title, type=admonition_type)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    element.replace_with(node)


@renders("div", phase=RenderPhase.POST, priority=50, name="admonitions", nestable=False)
def render_div_admonitions(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "admonition" not in classes:
        return

    title = _extract_title(element.find("p", class_="admonition-title"))
    _render_admonition(element, context, classes=classes, title=title)


@renders(
    "details",
    phase=RenderPhase.POST,
    priority=55,
    name="details_admonitions",
    nestable=False,
)
def render_details_admonitions(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    title = ""
    if summary := element.find("summary"):
        title = summary.get_text(strip=True)
        summary.decompose()

    _render_admonition(element, context, classes=classes, title=title or "")
