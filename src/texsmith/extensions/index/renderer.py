"""TeXSmith renderer hooks converting hashtag spans into LaTeX index entries."""

from __future__ import annotations

from pathlib import Path
import re

from bs4 import NavigableString, Tag

from texsmith.adapters.handlers._helpers import (
    coerce_attribute,
    gather_classes,
    mark_processed,
)
from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.context import RenderContext
from texsmith.core.rules import RenderPhase, renders

from .registry import get_registry


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
INDEX_TEMPLATE = TEMPLATE_DIR / "index.tex"


def _collect_tags(element: Tag) -> list[str]:
    tags: list[str] = []
    index = 0
    while True:
        key = "data-tag" if index == 0 else f"data-tag{index}"
        value = coerce_attribute(element.get(key))
        if not value:
            break
        cleaned = str(value).strip()
        if cleaned:
            tags.append(cleaned)
        index += 1
    return tags


def _strip_formatting(text: str) -> str:
    """Remove markdown formatting from text."""
    text = re.sub(r"\*\*\*(.*?)\*\*\*|___(.*?)___", r"\1\2", text)
    text = re.sub(r"\*\*(.*?)\*\*|__(.*?)__", r"\1\2", text)
    text = re.sub(r"\*(.*?)\*|_(.*?)_", r"\1\2", text)
    return text


def _format_tag(text: str, legacy: bool) -> str:
    """Convert markdown formatting to LaTeX."""
    parts = re.split(r"(\*\*\*.*?\*\*\*)", text)
    processed = []
    for part in parts:
        if part.startswith("***") and part.endswith("***"):
            content = part[3:-3]
            processed.append(
                f"\\textbf{{\\textit{{{escape_latex_chars(content, legacy_accents=legacy)}}}}}"
            )
        else:
            subparts = re.split(r"(\*\*.*?\*\*)", part)
            for subpart in subparts:
                if subpart.startswith("**") and subpart.endswith("**"):
                    content = subpart[2:-2]
                    processed.append(
                        f"\\textbf{{{escape_latex_chars(content, legacy_accents=legacy)}}}"
                    )
                else:
                    subsubparts = re.split(r"(\*.*?\*)", subpart)
                    for subsubpart in subsubparts:
                        if subsubpart.startswith("*") and subsubpart.endswith("*"):
                            content = subsubpart[1:-1]
                            processed.append(
                                f"\\textit{{{escape_latex_chars(content, legacy_accents=legacy)}}}"
                            )
                        else:
                            processed.append(escape_latex_chars(subsubpart, legacy_accents=legacy))
    return "".join(processed)


def _normalise_style(value: str | None) -> str:
    if not value:
        return ""
    cleaned = str(value).strip().lower()
    if cleaned == "ib":
        cleaned = "bi"
    if cleaned in {"b", "i", "bi"}:
        return cleaned
    return ""


def _apply_style(fragment: str, style: str) -> str:
    if style == "b":
        return f"\\textbf{{{fragment}}}"
    if style == "i":
        return f"\\textit{{{fragment}}}"
    if style == "bi":
        return f"\\textbf{{\\textit{{{fragment}}}}}"
    return fragment


_REGISTER_ATTR = "_texsmith_index_registered"


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=44,
    name="texsmith_index",
    nestable=False,
    auto_mark=False,
)
def render_index(element: Tag, context: RenderContext) -> None:
    """Convert ``<span class="ts-hashtag">`` elements into LaTeX index commands."""
    classes = gather_classes(element.get("class"))
    if "ts-hashtag" not in classes and "ts-index" not in classes:
        return

    tags = _collect_tags(element)
    if not tags:
        return

    registry_name = coerce_attribute(element.get("data-registry"))
    style_value = _normalise_style(coerce_attribute(element.get("data-style")))
    legacy = getattr(context.config, "legacy_latex_accents", False)

    formatted_tags = [_format_tag(tag, legacy=legacy) for tag in tags]
    if style_value and formatted_tags:
        formatted_tags[-1] = _apply_style(formatted_tags[-1], style_value)

    sort_tags = [_strip_formatting(tag) for tag in tags]

    entries = []
    for f_tag, s_tag in zip(formatted_tags, sort_tags, strict=True):
        escaped_s_tag = escape_latex_chars(s_tag, legacy_accents=legacy)
        if f_tag == escaped_s_tag:
            entries.append(f_tag)
        else:
            entries.append(f"{escaped_s_tag}@{f_tag}")

    entry_str = "!".join(entries)

    visible_text = element.get_text(strip=False) or ""

    latex = context.formatter.index(
        visible_text,
        entry=entry_str,
        style="",
        styled_entry=None,
        registry=registry_name,
    )

    registry = get_registry()
    registry.add(tuple(sort_tags))

    state = context.state
    state.has_index_entries = True
    index_entries = getattr(state, "index_entries", None)
    if isinstance(index_entries, list):
        index_entries.append(tuple(sort_tags))

    node = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


def register(renderer: object) -> None:
    """Register the index renderer on the provided TeXSmith renderer."""
    register_callable = getattr(renderer, "register", None)
    if not callable(register_callable):
        raise TypeError("Renderer does not expose a 'register' method.")
    if getattr(renderer, _REGISTER_ATTR, False):
        return
    register_callable(render_index)

    formatter = getattr(renderer, "formatter", None)
    override_template = getattr(formatter, "override_template", None)
    if callable(override_template):
        override_template("index", INDEX_TEMPLATE)
    setattr(renderer, _REGISTER_ATTR, True)


__all__ = ["register", "render_index"]
