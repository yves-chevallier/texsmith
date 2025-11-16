"""TeXSmith renderer hooks converting hashtag spans into LaTeX index entries."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

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


VALID_STYLES = {"", "i", "b", "bi"}


def _collect_tags(element: Tag) -> list[str]:
    tags: list[str] = []
    for index in range(3):
        key = "data-tag" if index == 0 else f"data-tag{index}"
        value = coerce_attribute(element.get(key))
        if not value:
            continue
        cleaned = str(value).strip()
        if cleaned:
            tags.append(cleaned)
    return tags


def _normalise_style(value: str | None) -> str:
    if not value:
        return ""
    cleaned = str(value).strip().lower()
    if cleaned in {"ib", "bi"}:
        cleaned = "bi"
    if cleaned not in VALID_STYLES:
        return ""
    return cleaned


def _escape_fragments(values: Iterable[str], *, legacy: bool) -> list[str]:
    return [escape_latex_chars(fragment, legacy_accents=legacy) for fragment in values if fragment]


def _apply_style(fragment: str, style: str) -> str:
    if style == "b":
        return f"\\textbf{{{fragment}}}"
    if style == "i":
        return f"\\textit{{{fragment}}}"
    if style == "bi":
        return f"\\textbf{{\\textit{{{fragment}}}}}"
    return fragment


def _build_styled_entry(fragments: list[str], style: str) -> str | None:
    if not fragments:
        return None
    styled_tail = _apply_style(fragments[-1], style)
    if len(fragments) == 1:
        return f"{fragments[0]}@{styled_tail}"
    if len(fragments) == 2:
        return f"{fragments[0]}!{fragments[1]}@{styled_tail}"
    styled_parts = list(fragments[:-1])
    styled_parts[-1] = f"{styled_parts[-1]}@{styled_tail}"
    return "!".join(styled_parts)


_REGISTER_ATTR = "_texsmith_index_registered"


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=44,
    name="texsmith_index_hashtag",
    nestable=False,
    auto_mark=False,
)
def render_hashtag(element: Tag, context: RenderContext) -> None:
    """Convert ``<span class="ts-hashtag">`` elements into LaTeX index commands."""
    classes = gather_classes(element.get("class"))
    if "ts-hashtag" not in classes:
        return

    tags = _collect_tags(element)
    if not tags:
        return

    legacy = getattr(context.config, "legacy_latex_accents", False)
    escaped_fragments = _escape_fragments(tags, legacy=legacy)
    escaped_entry = "!".join(escaped_fragments)

    style = _normalise_style(coerce_attribute(element.get("data-style")))

    display_text = element.get_text(strip=False) or tags[0]
    escaped_text = escape_latex_chars(display_text, legacy_accents=legacy)
    styled_entry = _build_styled_entry(escaped_fragments, style) if style else None

    latex = context.formatter.index(
        escaped_text,
        entry=escaped_entry,
        style=style,
        styled_entry=styled_entry,
    )

    registry = get_registry()
    registry.add(tags)

    state = context.state
    state.has_index_entries = True
    index_entries = getattr(state, "index_entries", None)
    if isinstance(index_entries, list):
        index_entries.append(tuple(tags))

    node = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


def register(renderer: object) -> None:
    """Register the hashtag renderer on the provided TeXSmith renderer."""
    register_callable = getattr(renderer, "register", None)
    if not callable(register_callable):
        raise TypeError("Renderer does not expose a 'register' method.")
    if getattr(renderer, _REGISTER_ATTR, False):
        return
    register_callable(render_hashtag)

    formatter = getattr(renderer, "formatter", None)
    override_template = getattr(formatter, "override_template", None)
    if callable(override_template):
        override_template("index", INDEX_TEMPLATE)
    setattr(renderer, _REGISTER_ATTR, True)


__all__ = ["register", "render_hashtag"]
