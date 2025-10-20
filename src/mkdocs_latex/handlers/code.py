"""Code-related handlers for the LaTeX renderer."""

from __future__ import annotations

from bs4 import Tag
from bs4.element import NavigableString

from ..context import RenderContext
from ..exceptions import InvalidNodeError
from ..rules import RenderPhase, renders


MERMAID_KEYWORDS = {
    "graph ",
    "graph\t",
    "flowchart ",
    "flowchart\t",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "gantt",
    "erDiagram",
    "journey",
}


def _looks_like_mermaid(diagram: str) -> bool:
    lower = diagram.lstrip().lower()
    return any(keyword in lower for keyword in MERMAID_KEYWORDS)


def _extract_language(element: Tag) -> str:
    classes = element.get("class") or []
    for cls in classes:
        if cls.startswith("language-"):
            return cls[len("language-") :] or "text"
    if "highlight" in classes:
        return "text"
    return "text"


def _is_ascii_art(payload: str) -> bool:
    return any(
        char in payload
        for char in ("┌", "┬", "─", "┐", "│", "├", "┼", "┤", "└", "┴", "┘")
    )


@renders("div", phase=RenderPhase.PRE, priority=40, name="code_blocks", nestable=False)
def render_code_blocks(element: Tag, context: RenderContext) -> None:
    """Render MkDocs-highlighted code blocks."""

    classes = element.get("class") or []
    if "highlight" not in classes:
        return
    if "mermaid" in classes:
        return

    code_element = element.find("code")
    if code_element is None:
        raise InvalidNodeError("Missing <code> element inside highlighted block")
    code_classes = code_element.get("class") or []
    if any(cls in {"language-mermaid", "mermaid"} for cls in code_classes):
        return

    if _looks_like_mermaid(code_element.get_text(strip=False)):
        return

    language = _extract_language(code_element)
    lineno = element.find(class_="linenos") is not None

    filename = None
    if filename_el := element.find(class_="filename"):
        filename = filename_el.get_text(strip=True)

    listing: list[str] = []
    highlight: list[int] = []

    spans = code_element.find_all(
        "span", id=lambda value: bool(value and value.startswith("__"))
    )
    if spans:
        for index, span in enumerate(spans, start=1):
            highlight_span = span.find("span", class_="hll")
            current = highlight_span or span
            if highlight_span is not None:
                highlight.append(index)
            listing.append(current.get_text(strip=False))
        code_text = "".join(listing)
    else:
        code_text = code_element.get_text(strip=False)

    baselinestretch = 0.5 if _is_ascii_art(code_text) else None
    code_text = code_text.replace("{", r"\{").replace("}", r"\}")

    latex = context.formatter.codeblock(
        code=code_text,
        language=language,
        lineno=lineno,
        filename=filename,
        highlight=highlight,
        baselinestretch=baselinestretch,
    )

    node = NavigableString(latex)
    setattr(node, "processed", True)
    element.replace_with(node)
