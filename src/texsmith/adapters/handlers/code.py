"""Code-related handlers for the LaTeX renderer."""

from __future__ import annotations

import re

from bs4.element import NavigableString, Tag

from texsmith.core.context import RenderContext
from texsmith.core.exceptions import InvalidNodeError
from texsmith.core.rules import RenderPhase, renders
from ._helpers import gather_classes, mark_processed


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
    classes = gather_classes(element.get("class"))
    for cls in classes:
        if cls.startswith("language-"):
            return cls[len("language-") :] or "text"
    if "highlight" in classes:
        return "text"
    return "text"


def _is_ascii_art(payload: str) -> bool:
    return any(char in payload for char in ("┌", "┬", "─", "┐", "│", "├", "┼", "┤", "└", "┴", "┘"))


_LANGUAGE_TOKEN = re.compile(r"^[A-Za-z0-9_+\-#.]+$")


def _extract_language_hint(text: str) -> tuple[str | None, str]:
    lines = text.splitlines()
    if not lines:
        return None, text

    first = lines[0].strip()
    remaining = lines[1:]

    if first.startswith("```"):
        info = first[3:].strip()
        language = info.split()[0] if info else None
        if remaining and remaining[-1].strip().startswith("```"):
            remaining = remaining[:-1]
        payload = "\n".join(remaining)
        return language or None, payload

    if remaining and _LANGUAGE_TOKEN.match(first):
        payload = "\n".join(remaining)
        if payload.strip():
            return first, payload

    return None, text


def _is_only_meaningful_child(node: Tag) -> bool:
    parent = getattr(node, "parent", None)
    if parent is None:
        return False

    for sibling in list(parent.contents):
        if sibling is node:
            continue
        if isinstance(sibling, NavigableString):
            if str(sibling).strip():
                return False
            continue
        if getattr(sibling, "name", None):
            return False
        if str(sibling).strip():
            return False
    return True


@renders("pre", phase=RenderPhase.PRE, priority=45, name="preformatted_code", nestable=False)
def render_preformatted_code(element: Tag, context: RenderContext) -> None:
    """Render plain <pre> blocks that wrap a <code> element."""
    classes = gather_classes(element.get("class"))
    if "mermaid" in classes:
        return

    parent = element.parent
    parent_classes = gather_classes(getattr(parent, "get", lambda *_: None)("class"))
    if any(cls in {"highlight", "codehilite"} for cls in parent_classes):
        return

    code_element = element.find("code", recursive=False)
    code_classes = gather_classes(code_element.get("class")) if code_element else []
    if any(cls in {"language-mermaid", "mermaid"} for cls in code_classes):
        return

    if code_element is not None and _looks_like_mermaid(code_element.get_text(strip=False)):
        return

    language = _extract_language(code_element) if code_element else "text"
    code_text = (
        code_element.get_text(strip=False) if code_element else element.get_text(strip=False)
    )

    if not code_text.strip():
        return

    baselinestretch = 0.5 if _is_ascii_art(code_text) else None
    if not code_text.endswith("\n"):
        code_text += "\n"

    latex = context.formatter.codeblock(
        code=code_text,
        language=language,
        lineno=False,
        filename=None,
        highlight=[],
        baselinestretch=baselinestretch,
    )

    element.replace_with(mark_processed(NavigableString(latex)))


@renders("div", phase=RenderPhase.PRE, priority=40, name="code_blocks", nestable=False)
def render_code_blocks(element: Tag, context: RenderContext) -> None:
    """Render MkDocs-highlighted code blocks."""
    classes = gather_classes(element.get("class"))
    if "highlight" not in classes:
        return
    if "mermaid" in classes:
        return

    code_element = element.find("code")
    if code_element is None:
        raise InvalidNodeError("Missing <code> element inside highlighted block")
    code_classes = gather_classes(code_element.get("class"))
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

    spans = code_element.find_all("span", id=lambda value: bool(value and value.startswith("__")))
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
    if not code_text.endswith("\n"):
        code_text += "\n"

    latex = context.formatter.codeblock(
        code=code_text,
        language=language,
        lineno=lineno,
        filename=filename,
        highlight=highlight,
        baselinestretch=baselinestretch,
    )

    element.replace_with(mark_processed(NavigableString(latex)))


@renders(
    "code",
    phase=RenderPhase.PRE,
    priority=40,
    name="standalone_code_blocks",
    auto_mark=False,
)
def render_standalone_code_blocks(element: Tag, context: RenderContext) -> None:
    """Render <code> elements that include multiline content as block code."""
    if element.find_parent("pre"):
        return

    classes = element.get("class") or []
    if any(cls in {"language-mermaid", "mermaid"} for cls in classes):
        return

    code_text = element.get_text(strip=False)
    if "\n" not in code_text:
        return

    if _looks_like_mermaid(code_text):
        return

    language = _extract_language(element)
    if language == "text":
        hint, adjusted = _extract_language_hint(code_text)
        if hint:
            language = hint
            code_text = adjusted

    code_text = code_text.replace("{", r"\{").replace("}", r"\}")
    if not code_text.strip():
        return
    if not code_text.endswith("\n"):
        code_text += "\n"

    baselinestretch = 0.5 if _is_ascii_art(code_text) else None

    latex = context.formatter.codeblock(
        code=code_text,
        language=language,
        lineno=False,
        filename=None,
        highlight=[],
        baselinestretch=baselinestretch,
    )

    node = mark_processed(NavigableString(latex))

    if element.parent and element.parent.name == "p" and _is_only_meaningful_child(element):
        element.parent.replace_with(node)
        context.mark_processed(element.parent)
    else:
        element.replace_with(node)
    context.mark_processed(element)
    context.suppress_children(element)
