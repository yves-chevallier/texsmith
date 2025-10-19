"""Advanced inline handlers ported from the legacy renderer."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from bs4 import NavigableString, Tag

from ..context import RenderContext
from ..exceptions import InvalidNodeError
from ..rules import RenderPhase, renders
from ..transformers import fetch_image, svg2pdf
from ..utils import escape_latex_chars, is_valid_url, safe_quote


def _has_ancestor(node: NavigableString, *names: str) -> bool:
    parent = node.parent
    while parent is not None:
        if getattr(parent, "name", None) in names:
            return True
        parent = getattr(parent, "parent", None)
    return False


def _allow_hyphenation(text: str) -> str:
    if len(text) < 50:
        return text
    return re.sub(r"(\b[^\W\d_]{2,}-)([^\W\d_]{7,})\b", r"\1\\allowhyphens \2", text)


@renders(phase=RenderPhase.PRE, name="escape_plain_text", auto_mark=False)
def escape_plain_text(root: Tag, context: RenderContext) -> None:
    """Escape LaTeX characters on plain text nodes outside code blocks."""

    for node in list(root.find_all(string=True)):
        if getattr(node, "processed", False):
            continue
        if _has_ancestor(node, "code"):
            continue
        text = str(node)
        if not text:
            continue
        escaped = escape_latex_chars(text)
        escaped = _allow_hyphenation(escaped)
        if escaped != text:
            replacement = NavigableString(escaped)
            setattr(replacement, "processed", True)
            node.replace_with(replacement)


@renders("a", phase=RenderPhase.PRE, priority=80, name="unicode_links", nestable=False)
def render_unicode_link(element: Tag, context: RenderContext) -> None:
    """Render Unicode helper links."""

    classes = element.get("class") or []
    if "ycr-unicode" not in classes:
        return

    code = element.get_text(strip=True)
    href = element.get("href", "")
    latex = context.formatter.href(text=f"U+{code}", url=safe_quote(href))
    node = NavigableString(latex)
    setattr(node, "processed", True)
    element.replace_with(node)


@renders("a", phase=RenderPhase.PRE, priority=70, name="regex_links", nestable=False)
def render_regex_link(element: Tag, context: RenderContext) -> None:
    """Render custom regex helper links."""

    classes = element.get("class") or []
    if "ycr-regex" not in classes:
        return

    code = element.get_text(strip=False)
    if code_tag := element.find("code"):
        code = code_tag.get_text(strip=False)
    code = code.replace("&", "\\&").replace("#", "\\#")

    href = element.get("href", "")
    latex = context.formatter.regex(code, url=safe_quote(href))
    node = NavigableString(latex)
    setattr(node, "processed", True)
    element.replace_with(node)


def _extract_code_text(element: Tag) -> str:
    classes = element.get("class") or []
    if any(cls.startswith("language-") for cls in classes) or "highlight" in classes:
        return "".join(child.get_text(strip=False) for child in element.find_all("span"))
    return element.get_text(strip=False)


@renders("code", phase=RenderPhase.PRE, priority=50, name="inline_code", nestable=False)
def render_inline_code(element: Tag, context: RenderContext) -> None:
    """Render inline code elements using the formatter."""

    if element.find_parent("pre", class_="mermaid"):
        return

    code = _extract_code_text(element)
    code = escape_latex_chars(code).replace(" ", "~")

    latex = context.formatter.codeinlinett(code)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    element.replace_with(node)


@renders("span", phase=RenderPhase.PRE, priority=60, name="inline_math", nestable=False)
def render_math_inline(element: Tag, context: RenderContext) -> None:
    """Preserve inline math payloads untouched."""

    classes = element.get("class") or []
    if "arithmatex" not in classes:
        return
    text = element.get_text(strip=False)
    node = NavigableString(text)
    setattr(node, "processed", True)
    element.replace_with(node)


@renders("div", phase=RenderPhase.PRE, priority=70, name="math_block", nestable=False)
def render_math_block(element: Tag, context: RenderContext) -> None:
    """Preserve block math payloads."""

    classes = element.get("class") or []
    if "arithmatex" not in classes:
        return
    text = element.get_text(strip=False)
    node = NavigableString(f"\n{text}\n")
    setattr(node, "processed", True)
    element.replace_with(node)


@renders("abbr", phase=RenderPhase.INLINE, priority=30, name="abbreviation", nestable=False)
def render_abbreviation(element: Tag, context: RenderContext) -> None:
    """Register and render abbreviations."""

    title = element.get("title", "")
    short = element.get_text(strip=True)
    tag = "acr:" + re.sub(r"[^a-zA-Z0-9]", "", short).lower()

    context.state.remember_acronym(tag, short, escape_latex_chars(title))
    latex = context.formatter.acronym(tag)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    element.replace_with(node)


@renders("span", phase=RenderPhase.INLINE, priority=40, name="keystrokes", nestable=False)
def render_keystrokes(element: Tag, context: RenderContext) -> None:
    """Render keyboard shortcut markup."""

    classes = element.get("class") or []
    if "keys" not in classes:
        return

    keys: list[str] = []
    for key in element.find_all("kbd"):
        key_classes = key.get("class") or []
        matched: Iterable[str] = (
            cls[4:] for cls in key_classes if cls.startswith("key-")
        )
        value = next(matched, None)
        if value:
            keys.append(value)
        else:
            keys.append(key.get_text(strip=True))

    latex = context.formatter.keystroke(keys)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders("img", phase=RenderPhase.INLINE, priority=20, name="twemoji_images", nestable=False)
def render_twemoji_image(element: Tag, context: RenderContext) -> None:
    """Render Twitter emoji images as inline icons."""

    classes = element.get("class") or []
    if not {"twemoji", "emojione"}.intersection(classes):
        return

    src = element.get("src")
    if not src:
        raise InvalidNodeError("Twemoji image without 'src' attribute")
    if not is_valid_url(src):
        raise InvalidNodeError("Twemoji images must reference remote assets")

    artefact = fetch_image(src, output_dir=context.assets.output_root)
    stored_path = context.assets.register(src, artefact)

    latex = context.formatter.icon(stored_path.name)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    element.replace_with(node)


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=25,
    name="twemoji_svg",
    nestable=False,
    auto_mark=False,
)
def render_twemoji_span(element: Tag, context: RenderContext) -> None:
    """Render inline SVG emoji payloads."""

    classes = element.get("class") or []
    if "twemoji" not in classes:
        return

    svg = element.find("svg")
    if svg is None:
        raise InvalidNodeError("Expected inline SVG inside span.twemoji")

    svg_payload = str(svg)
    artefact = svg2pdf(svg_payload, output_dir=context.assets.output_root)
    digest = hashlib.sha256(svg_payload.encode("utf-8")).hexdigest()
    stored_path = context.assets.register(f"twemoji::{digest}", artefact)

    latex = context.formatter.icon(stored_path.name)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=45,
    name="index_entries",
    nestable=False,
    auto_mark=False,
)
def render_index_entry(element: Tag, context: RenderContext) -> None:
    """Render MkDocs index entries."""

    classes = element.get("class") or []
    if "ycr-hashtag" not in classes:
        return

    tag = element.get("data-tag")
    if not tag:
        raise InvalidNodeError("Index entry missing data-tag attribute")

    text = element.get_text(strip=True)
    entry = element.get("data-index-entry", text or tag)
    entry = escape_latex_chars(entry)

    latex = context.formatter.index(text or tag, tag=tag, entry=entry)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders(
    "del",
    phase=RenderPhase.INLINE,
    priority=35,
    name="critic_deletions",
    auto_mark=False,
)
def render_critic_deletions(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "critic" not in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.deletion(text=text)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders(
    "ins",
    phase=RenderPhase.INLINE,
    priority=35,
    name="critic_additions",
    auto_mark=False,
)
def render_critic_additions(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "critic" not in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.addition(text=text)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=35,
    name="critic_comments",
    auto_mark=False,
)
def render_critic_comments(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "critic" not in classes or "comment" not in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.comment(text=text)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders(
    "mark",
    phase=RenderPhase.INLINE,
    priority=35,
    name="critic_highlight",
    auto_mark=False,
)
def render_critic_highlight(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "critic" not in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.highlight(text=text)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=-10,
    name="critic_substitution",
    auto_mark=False,
)
def render_critic_substitution(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "critic" not in classes or "subst" not in classes:
        return

    deleted = element.find("del")
    inserted = element.find("ins")
    if deleted is None or inserted is None:
        raise InvalidNodeError("Critic substitution requires both <del> and <ins> children")

    original = deleted.get_text(strip=False)
    replacement = inserted.get_text(strip=False)

    latex = context.formatter.substitution(original=original, replacement=replacement)
    node = NavigableString(latex)
    setattr(node, "processed", True)
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)
