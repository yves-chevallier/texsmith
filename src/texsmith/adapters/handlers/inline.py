"""Advanced inline handlers ported from the legacy renderer."""

from __future__ import annotations

from collections.abc import Iterable
import hashlib
import re
import warnings

from bs4.element import NavigableString, Tag
import emoji
from requests.utils import requote_uri as requote_url

from texsmith.core.context import RenderContext
from texsmith.core.exceptions import InvalidNodeError, TransformerExecutionError
from texsmith.core.rules import RenderPhase, renders
from texsmith.fonts.scripts import record_script_usage_for_slug, render_moving_text

from ..latex.utils import escape_latex_chars
from ..transformers import fetch_image, svg2pdf
from ._helpers import coerce_attribute, gather_classes, is_valid_url, mark_processed
from .code import _resolve_code_engine


_MATH_PAYLOAD_PATTERN = re.compile(
    r"""
    (?:\$\$.*?\$\$)                                 # display math $$...$$
    |(?:\\\[.*?\\\])                                # display math \[...\]
    |(?:\\\(.*?\\\))                                # inline math \(...\)
    |(?:\\begin\{[a-zA-Z*]+\}.*?\\end\{[a-zA-Z*]+\})# LaTeX environments
    |(?<!\\)\$(?!\$)(?!\s)(?:\\.|[^$])*?(?<!\\)\$   # inline math $...$
    """,
    re.DOTALL | re.VERBOSE,
)

_SUPERSCRIPT_MAP = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
    "⁺": "+",
    "⁻": "-",
    "⁼": "=",
    "⁽": "(",
    "⁾": ")",
    "ⁿ": "n",
    "ⁱ": "i",
    "ᵃ": "a",
    "ᵇ": "b",
    "ᶜ": "c",
    "ᵈ": "d",
    "ᵉ": "e",
    "ᶠ": "f",
    "ᵍ": "g",
    "ʰ": "h",
    "ᶦ": "i",
    "ʲ": "j",
    "ᵏ": "k",
    "ˡ": "l",
    "ᵐ": "m",
    "ᶰ": "n",
    "ᵒ": "o",
    "ᵖ": "p",
    "ʳ": "r",
    "ˢ": "s",
    "ᵗ": "t",
    "ᵘ": "u",
    "ᵛ": "v",
    "ʷ": "w",
    "ˣ": "x",
    "ʸ": "y",
    "ᶻ": "z",
    "ᴬ": "A",
    "ᴮ": "B",
    "ᴰ": "D",
    "ᴱ": "E",
    "ᴳ": "G",
    "ᴴ": "H",
    "ᴵ": "I",
    "ᴶ": "J",
    "ᴷ": "K",
    "ᴸ": "L",
    "ᴹ": "M",
    "ᴺ": "N",
    "ᴼ": "O",
    "ᴾ": "P",
    "ᴿ": "R",
    "ᵀ": "T",
    "ᵁ": "U",
    "ⱽ": "V",
    "ᵂ": "W",
}

_SUPERSCRIPT_PATTERN = re.compile(f"([{''.join(re.escape(char) for char in _SUPERSCRIPT_MAP)}]+)")

_SUBSCRIPT_MAP = {
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "₃": "3",
    "₄": "4",
    "₅": "5",
    "₆": "6",
    "₇": "7",
    "₈": "8",
    "₉": "9",
    "₊": "+",
    "₋": "-",
    "₌": "=",
    "₍": "(",
    "₎": ")",
    "ₐ": "a",
    "ₑ": "e",
    "ₒ": "o",
    "ₔ": "ə",
    "ₓ": "x",
    "ₕ": "h",
    "ₖ": "k",
    "ₗ": "l",
    "ₘ": "m",
    "ₙ": "n",
    "ₚ": "p",
    "ₛ": "s",
    "ₜ": "t",
    "ᵢ": "i",
    "ᵣ": "r",
    "ᵤ": "u",
    "ᵥ": "v",
    "ᵦ": r"\beta",
    "ᵧ": r"\gamma",
    "ᵨ": r"\rho",
    "ᵩ": r"\phi",
    "ᵪ": r"\chi",
}

_SUBSCRIPT_PATTERN = re.compile(f"([{''.join(re.escape(char) for char in _SUBSCRIPT_MAP)}]+)")
_UNICODE_DASH_MAP = {
    "\N{EN DASH}": "--",
    "\N{FIGURE DASH}": "--",
    "\N{EM DASH}": "---",
    "\N{HORIZONTAL BAR}": "---",
}
_UNICODE_DASH_PATTERN = re.compile("[" + "".join(re.escape(k) for k in _UNICODE_DASH_MAP) + "]")

_UNICODE_PUNCT_MAP = {
    "\N{RIGHT SINGLE QUOTATION MARK}": "'",
    "\N{LEFT SINGLE QUOTATION MARK}": "`",
    "\N{SINGLE LOW-9 QUOTATION MARK}": ",",
    "\N{SINGLE HIGH-REVERSED-9 QUOTATION MARK}": "'",
    "\N{LEFT DOUBLE QUOTATION MARK}": "``",
    "\N{RIGHT DOUBLE QUOTATION MARK}": "''",
    "\N{DOUBLE LOW-9 QUOTATION MARK}": ",,",
    "\N{DOUBLE HIGH-REVERSED-9 QUOTATION MARK}": "''",
    "\N{HORIZONTAL ELLIPSIS}": "...",
}
_UNICODE_PUNCT_PATTERN = re.compile("[" + "".join(re.escape(k) for k in _UNICODE_PUNCT_MAP) + "]")
_MINTINLINE_DELIMITERS: tuple[str, ...] = (
    "|",
    "!",
    ";",
    ":",
    "+",
    "/",
    "-",
    "=",
    "~",
    "*",
    "#",
    "?",
)


def _replace_unicode_scripts(
    text: str, pattern: re.Pattern[str], mapping: dict[str, str], command: str
) -> str:
    if not text:
        return text

    def _normalize(match: re.Match[str]) -> str:
        payload = match.group(0)
        normalized = "".join(mapping.get(char, char) for char in payload)
        return f"\\{command}{{{normalized}}}"

    return pattern.sub(_normalize, text)


def _replace_unicode_superscripts(text: str) -> str:
    """Convert sequences of Unicode superscript characters to LaTeX text macros."""
    return _replace_unicode_scripts(text, _SUPERSCRIPT_PATTERN, _SUPERSCRIPT_MAP, "textsuperscript")


def _replace_unicode_subscripts(text: str) -> str:
    """Convert sequences of Unicode subscript characters to LaTeX text macros."""
    return _replace_unicode_scripts(text, _SUBSCRIPT_PATTERN, _SUBSCRIPT_MAP, "textsubscript")


def _replace_unicode_dashes(text: str) -> str:
    """Convert Unicode dash characters to LaTeX-friendly representations."""
    if not text:
        return text
    return _UNICODE_DASH_PATTERN.sub(lambda match: _UNICODE_DASH_MAP.get(match.group(0), "-"), text)


def _replace_unicode_punctuation(text: str) -> str:
    """Replace curly quotes and ellipsis with LaTeX-friendly sequences."""
    if not text:
        return text
    return _UNICODE_PUNCT_PATTERN.sub(
        lambda match: _UNICODE_PUNCT_MAP.get(match.group(0), ""), text
    )


def _get_emoji_mode(context: RenderContext) -> str:
    value = context.runtime.get("emoji_mode")
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate
    return "black"


def _get_emoji_command(context: RenderContext) -> str:
    value = context.runtime.get("emoji_command")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return r"\texsmithEmoji"


def _has_ancestor(node: NavigableString, *names: str) -> bool:
    parent = node.parent
    while parent is not None:
        if getattr(parent, "name", None) in names:
            return True
        parent = getattr(parent, "parent", None)
    return False


def _allow_hyphenation(text: str) -> str:
    """Allow hyphenation in long words.

    TODO: This function is bad. Instead we should look into a dictionary
    based hyphenation solution.
    """
    return text  # Temporary disable hyphenation handling

    if len(text) < 50:
        return text
    return re.sub(r"(\b[^\W\d_]{2,}-)([^\W\d_]{7,})\b", r"\1\\allowhyphens \2", text)


def _prepare_plain_text(text: str, *, legacy_latex_accents: bool) -> str:
    text = _replace_unicode_punctuation(text)
    text = _replace_unicode_dashes(text)
    escaped = escape_latex_chars(text, legacy_accents=legacy_latex_accents)
    escaped = _allow_hyphenation(escaped)
    escaped = _replace_unicode_superscripts(escaped)
    return _replace_unicode_subscripts(escaped)


def _segment_text_with_emoji(text: str) -> list[tuple[str, str]]:
    """Split text into plain fragments and emoji clusters."""
    if not text:
        return []
    if text.isascii():
        return [("text", text)]
    entries = emoji.emoji_list(text)
    if not entries:
        return [("text", text)]

    segments: list[tuple[str, str]] = []
    cursor = 0
    for entry in entries:
        start = entry["match_start"]
        end = entry["match_end"]
        if start > cursor:
            segments.append(("text", text[cursor:start]))
        token = text[start:end]
        segments.append(("emoji", token))
        cursor = end
    if cursor < len(text):
        segments.append(("text", text[cursor:]))
    return segments


def _emoji_twemoji_url(token: str) -> str:
    codepoints = "-".join(f"{ord(char):x}" for char in token)
    return f"https://twemoji.maxcdn.com/v/latest/svg/{codepoints}.svg"


def _render_emoji(token: str, context: RenderContext) -> str:
    url = _emoji_twemoji_url(token)
    try:
        artefact = fetch_image(url, output_dir=context.assets.output_root)
    except TransformerExecutionError as exc:
        warnings.warn(f"Failed to fetch emoji '{token}': {exc}", stacklevel=2)
        legacy = getattr(context.config, "legacy_latex_accents", False)
        return _prepare_plain_text(token, legacy_latex_accents=legacy)

    stored_path = context.assets.register(url, artefact)
    asset_path = context.assets.latex_path(stored_path)
    return context.formatter.icon(asset_path)


def _render_font_emoji(token: str, command: str) -> str:
    if not token:
        return ""
    return f"{command}{{{token}}}"


def _escape_text_segment(text: str, context: RenderContext, *, legacy_latex_accents: bool) -> str:
    chunks: list[str] = []
    emoji_mode = _get_emoji_mode(context)
    emoji_command = _get_emoji_command(context)
    for kind, payload in _segment_text_with_emoji(text):
        if kind == "text":
            if payload:
                chunks.append(
                    _prepare_plain_text(payload, legacy_latex_accents=legacy_latex_accents)
                )
        else:
            if emoji_mode == "artifact":
                chunks.append(_render_emoji(payload, context))
            else:
                chunks.append(_render_font_emoji(payload, emoji_command))
    return "".join(chunks)


@renders(phase=RenderPhase.PRE, name="escape_plain_text", auto_mark=False)
def escape_plain_text(root: Tag, context: RenderContext) -> None:
    """Escape LaTeX characters on plain text nodes outside code blocks."""
    legacy_latex_accents = getattr(context.config, "legacy_latex_accents", False)
    for node in list(root.find_all(string=True)):
        if getattr(node, "processed", False):
            continue
        if _has_ancestor(node, "code", "script"):
            continue
        ancestor = getattr(node, "parent", None)
        skip_plain_text = False
        while ancestor is not None:
            classes = gather_classes(getattr(ancestor, "get", lambda *_: None)("class"))
            if "latex-raw" in classes or "arithmatex" in classes:
                skip_plain_text = True
                break
            ancestor = getattr(ancestor, "parent", None)
        if skip_plain_text:
            continue
        text = str(node)
        if not text:
            continue
        if "\\keystroke{" in text or "\\keystrokes{" in text:
            node.replace_with(mark_processed(NavigableString(text)))
            continue
        matches = list(_MATH_PAYLOAD_PATTERN.finditer(text))
        if not matches:
            escaped = _escape_text_segment(text, context, legacy_latex_accents=legacy_latex_accents)
            if escaped != text:
                node.replace_with(mark_processed(NavigableString(escaped)))
            continue

        parts: list[str] = []
        cursor = 0
        for match in matches:
            if match.start() > cursor:
                segment = text[cursor : match.start()]
                if segment:
                    escaped = _escape_text_segment(
                        segment,
                        context,
                        legacy_latex_accents=legacy_latex_accents,
                    )
                    parts.append(escaped)
            parts.append(match.group(0))
            cursor = match.end()
        if cursor < len(text):
            tail = text[cursor:]
            if tail:
                escaped = _escape_text_segment(
                    tail,
                    context,
                    legacy_latex_accents=legacy_latex_accents,
                )
                parts.append(escaped)

        replacement = mark_processed(NavigableString("".join(parts)))
        node.replace_with(replacement)


@renders("a", phase=RenderPhase.PRE, priority=80, name="unicode_links", nestable=False)
def render_unicode_link(element: Tag, context: RenderContext) -> None:
    """Render Unicode helper links."""
    classes = gather_classes(element.get("class"))
    if "ycr-unicode" not in classes:
        return

    code = element.get_text(strip=True)
    href = coerce_attribute(element.get("href")) or ""
    latex = context.formatter.href(text=f"U+{code}", url=requote_url(href))
    element.replace_with(mark_processed(NavigableString(latex)))


@renders("a", phase=RenderPhase.PRE, priority=70, name="regex_links", nestable=False)
def render_regex_link(element: Tag, context: RenderContext) -> None:
    """Render custom regex helper links."""
    classes = gather_classes(element.get("class"))
    if "ycr-regex" not in classes:
        return

    code = element.get_text(strip=False)
    if code_tag := element.find("code"):
        code = code_tag.get_text(strip=False)
    code = code.replace("&", "\\&").replace("#", "\\#")

    href = coerce_attribute(element.get("href")) or ""
    latex = context.formatter.regex(code, url=requote_url(href))
    element.replace_with(mark_processed(NavigableString(latex)))


def _extract_code_text(element: Tag) -> str:
    classes = gather_classes(element.get("class"))
    if any(cls.startswith("language-") for cls in classes) or "highlight" in classes:
        return "".join(child.get_text(strip=False) for child in element.find_all("span"))
    return element.get_text(strip=False)


def _pick_mintinline_delimiter(text: str) -> str | None:
    for delimiter in _MINTINLINE_DELIMITERS:
        if delimiter not in text:
            return delimiter
    return None


@renders("code", phase=RenderPhase.PRE, priority=50, name="inline_code", nestable=False)
def render_inline_code(element: Tag, context: RenderContext) -> None:
    """Render inline code elements using the formatter."""
    if element.find_parent("pre"):
        return

    classes = gather_classes(element.get("class"))
    code = _extract_code_text(element)
    if "\n" in code:
        return

    engine = _resolve_code_engine(context)
    language_hint = None
    if code.startswith("#!"):
        shebang_parts = code[2:].strip().split(None, 1)
        if shebang_parts:
            language_hint = shebang_parts[0]
            code = shebang_parts[1] if len(shebang_parts) > 1 else ""

    has_language = any(cls.startswith("language-") for cls in classes)
    language = None
    if has_language or "highlight" in classes:
        language = next(
            (cls[len("language-") :] or "text" for cls in classes if cls.startswith("language-")),
            "text",
        )
    if language_hint and not language:
        language = language_hint

    if language:
        delimiter = _pick_mintinline_delimiter(code)
        if delimiter and engine == "minted":
            context.state.requires_shell_escape = (
                context.state.requires_shell_escape or engine == "minted"
            )
            latex = context.formatter.codeinline(
                language=language or "text",
                text=code,
                engine=engine,
            )
            element.replace_with(mark_processed(NavigableString(latex)))
            return
        latex = context.formatter.codeinline(
            language=language or "text",
            text=code,
            engine=engine,
            state=context.state,
        )
        element.replace_with(mark_processed(NavigableString(latex)))
        return

    latex = context.formatter.codeinlinett(code)
    element.replace_with(mark_processed(NavigableString(latex)))


@renders(
    "span",
    phase=RenderPhase.PRE,
    priority=60,
    name="inline_math",
    auto_mark=False,
)
def render_math_inline(element: Tag, _context: RenderContext) -> None:
    """Preserve inline math payloads untouched."""
    classes = gather_classes(element.get("class"))
    if "arithmatex" not in classes:
        return
    text = element.get_text(strip=False)
    element.replace_with(mark_processed(NavigableString(text)))


@renders(
    "div",
    phase=RenderPhase.PRE,
    priority=30,
    name="math_block",
    auto_mark=False,
)
def render_math_block(element: Tag, _context: RenderContext) -> None:
    """Preserve block math payloads."""
    classes = gather_classes(element.get("class"))
    if "arithmatex" not in classes:
        return
    text = element.get_text(strip=False)
    stripped = text.strip()

    match = _DISPLAY_MATH_PATTERN.match(stripped)
    if match:
        inner = match.group(1)
        if _payload_is_block_environment(inner):
            # align/equation environments already provide display math.
            latex = f"\n{inner.strip()}\n"
            element.replace_with(mark_processed(NavigableString(latex)))
            return

    element.replace_with(mark_processed(NavigableString(f"\n{text}\n")))


@renders(
    "script",
    phase=RenderPhase.PRE,
    priority=65,
    name="math_script",
    nestable=False,
    auto_mark=False,
)
def render_math_script(element: Tag, _context: RenderContext) -> None:
    """Preserve math payloads generated via script tags (e.g. mdx_math)."""
    type_attr = coerce_attribute(element.get("type"))
    if type_attr is None:
        return
    if not type_attr.startswith("math/tex"):
        return

    payload = element.get_text(strip=False)
    if payload is None:
        payload = ""
    payload = payload.strip()
    is_display = "mode=display" in type_attr

    if not payload:
        node = NavigableString("")
    elif is_display:
        if _payload_is_block_environment(payload):
            node = NavigableString(f"\n{payload}\n")
        else:
            node = NavigableString(f"\n$$\n{payload}\n$$\n")
    else:
        node = NavigableString(f"${payload}$")

    element.replace_with(mark_processed(node))


@renders("abbr", phase=RenderPhase.INLINE, priority=30, name="abbreviation", nestable=False)
def render_abbreviation(element: Tag, context: RenderContext) -> None:
    """Register and render abbreviations."""
    title_attr = element.get("title")
    description = title_attr.strip() if isinstance(title_attr, str) else ""
    term = element.get_text(strip=True)

    if not term:
        return

    if not description:
        legacy_latex_accents = getattr(context.config, "legacy_latex_accents", False)
        latex_text = escape_latex_chars(term, legacy_accents=legacy_latex_accents)
        element.replace_with(mark_processed(NavigableString(latex_text)))
        return

    key = context.state.remember_abbreviation(term, description)
    if not key:
        key = term

    latex = f"\\acrshort{{{key}}}"
    element.replace_with(mark_processed(NavigableString(latex)))


@renders("span", phase=RenderPhase.INLINE, priority=40, name="keystrokes", nestable=False)
def render_keystrokes(element: Tag, context: RenderContext) -> None:
    """Render keyboard shortcut markup."""
    classes = gather_classes(element.get("class"))
    if "keys" not in classes:
        return

    keys: list[str] = []
    for key in element.find_all("kbd"):
        key_classes = gather_classes(key.get("class"))
        matched: Iterable[str] = (cls[4:] for cls in key_classes if cls.startswith("key-"))
        value = next(matched, None)
        if value:
            keys.append(value)
        else:
            keys.append(key.get_text(strip=True))

    latex = context.formatter.keystroke(keys)
    node = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=30,
    name="script_spans",
    nestable=False,
    auto_mark=False,
)
def render_script_spans(element: Tag, context: RenderContext) -> None:
    """Render spans tagged with data-script into explicit text commands."""
    slug = coerce_attribute(element.get("data-script"))
    if not slug:
        return

    raw_text = element.get_text(strip=False)
    if not raw_text:
        element.decompose()
        return

    record_script_usage_for_slug(slug, raw_text, context)
    legacy_accents = getattr(context.config, "legacy_latex_accents", False)
    payload = escape_latex_chars(raw_text, legacy_accents=legacy_accents)
    latex = f"\\text{slug}{{{payload}}}"
    parent = element.parent
    if parent is not None and getattr(parent, "attrs", None) is not None:
        parent.attrs["data-texsmith-latex"] = "true"
    context.mark_processed(element)
    element.replace_with(mark_processed(NavigableString(latex)))


@renders(
    "span",
    phase=RenderPhase.INLINE,
    priority=30,
    name="latex_text",
    nestable=False,
    auto_mark=False,
)
def render_latex_text_span(element: Tag, context: RenderContext) -> None:
    """Render the custom ``latex-text`` span into canonical LaTeX."""
    classes = gather_classes(element.get("class"))
    if "latex-text" not in classes:
        return

    latex = mark_processed(NavigableString(r"\LaTeX{}"))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(latex)


def _extract_emoji_token(element: Tag) -> str:
    for attr in ("alt", "data-emoji"):
        candidate = coerce_attribute(element.get(attr))
        if candidate:
            return candidate
    fallback = coerce_attribute(element.get("title"))
    return fallback or ""


@renders("img", phase=RenderPhase.INLINE, priority=20, name="twemoji_images", nestable=False)
def render_twemoji_image(element: Tag, context: RenderContext) -> None:
    """Render Twitter emoji images as inline icons."""
    classes = gather_classes(element.get("class"))
    if not {"twemoji", "emojione"}.intersection(classes):
        return
    emoji_mode = _get_emoji_mode(context)
    if emoji_mode != "artifact":
        token = _extract_emoji_token(element)
        latex = _render_font_emoji(token, _get_emoji_command(context))
        element.replace_with(mark_processed(NavigableString(latex)))
        return
    if not context.runtime.get("copy_assets", True):
        placeholder = (
            coerce_attribute(element.get("alt")) or coerce_attribute(element.get("title")) or ""
        )
        element.replace_with(mark_processed(NavigableString(placeholder)))
        return

    src = coerce_attribute(element.get("src"))
    if not src:
        raise InvalidNodeError("Twemoji image without 'src' attribute")
    if not is_valid_url(src):
        raise InvalidNodeError("Twemoji images must reference remote assets")

    artefact = fetch_image(src, output_dir=context.assets.output_root)
    stored_path = context.assets.register(src, artefact)
    asset_path = context.assets.latex_path(stored_path)

    latex = context.formatter.icon(asset_path)
    element.replace_with(mark_processed(NavigableString(latex)))


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
    classes = gather_classes(element.get("class"))
    if "twemoji" not in classes:
        return
    emoji_mode = _get_emoji_mode(context)
    if emoji_mode != "artifact":
        token = _extract_emoji_token(element)
        latex = _render_font_emoji(token, _get_emoji_command(context))
        element.replace_with(mark_processed(NavigableString(latex)))
        return
    if not context.runtime.get("copy_assets", True):
        placeholder = coerce_attribute(element.get("title")) or element.get_text(strip=True) or ""
        element.replace_with(mark_processed(NavigableString(placeholder)))
        return

    svg = element.find("svg")
    if svg is None:
        raise InvalidNodeError("Expected inline SVG inside span.twemoji")

    svg_payload = str(svg)
    artefact = svg2pdf(svg_payload, output_dir=context.assets.output_root)
    digest = hashlib.sha256(svg_payload.encode("utf-8")).hexdigest()
    stored_path = context.assets.register(f"twemoji::{digest}", artefact)
    asset_path = context.assets.latex_path(stored_path)

    latex = context.formatter.icon(asset_path)
    node = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


@renders(
    "span",
    "a",
    phase=RenderPhase.INLINE,
    priority=45,
    name="index_entries",
    nestable=False,
    auto_mark=False,
)
def render_index_entry(element: Tag, context: RenderContext) -> None:
    """Render inline index term annotations."""
    tag_name = coerce_attribute(element.get("data-tag-name"))
    if not tag_name:
        return

    raw_entry = str(tag_name)
    parts = [segment.strip() for segment in raw_entry.split(",") if segment.strip()]
    if not parts:
        return

    legacy_latex_accents = getattr(context.config, "legacy_latex_accents", False)
    escaped_fragments = [
        render_moving_text(part, context, legacy_accents=legacy_latex_accents, wrap_scripts=True)
        or ""
        for part in parts
    ]
    escaped_entry = "!".join(fragment for fragment in escaped_fragments if fragment)
    style_value = coerce_attribute(element.get("data-tag-style"))
    style_key = style_value.strip().lower() if style_value else ""
    if style_key not in {"b", "i", "bi"}:
        style_key = ""

    display_text = element.get_text(strip=False) or ""
    escaped_text = (
        render_moving_text(
            display_text, context, legacy_accents=legacy_latex_accents, wrap_scripts=True
        )
        or ""
    )

    latex = context.formatter.index(escaped_text, entry=escaped_entry, style=style_key)
    node = mark_processed(NavigableString(latex))
    context.state.has_index_entries = True
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
    """Convert critic-marked deletions into LaTeX review macros."""
    classes = gather_classes(element.get("class"))
    if "critic" not in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.deletion(text=text)
    node = mark_processed(NavigableString(latex))
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
    """Convert critic-marked insertions into LaTeX review macros."""
    classes = gather_classes(element.get("class"))
    if "critic" not in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.addition(text=text)
    node = mark_processed(NavigableString(latex))
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
    """Render critic comments as inline LaTeX annotations."""
    classes = gather_classes(element.get("class"))
    if "critic" not in classes or "comment" not in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.comment(text=text)
    node = mark_processed(NavigableString(latex))
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
    """Render critic highlights using the formatter highlighting helper."""
    classes = gather_classes(element.get("class"))
    if "critic" not in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.highlight(text=text)
    node = mark_processed(NavigableString(latex))
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
    """Render critic substitutions as paired deletion/addition markup."""
    classes = gather_classes(element.get("class"))
    if "critic" not in classes or "subst" not in classes:
        return

    deleted = element.find("del")
    inserted = element.find("ins")
    if deleted is None or inserted is None:
        raise InvalidNodeError("Critic substitution requires both <del> and <ins> children")

    original = deleted.get_text(strip=False)
    replacement = inserted.get_text(strip=False)

    latex = context.formatter.substitution(original=original, replacement=replacement)
    node = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


_BLOCK_MATH_ENVIRONMENTS = {
    "align",
    "align*",
    "equation",
    "equation*",
}


_DISPLAY_MATH_PATTERN = re.compile(r"^\\\[\s*(.*?)\s*\\\]\s*$", re.DOTALL)


def _payload_is_block_environment(payload: str) -> bool:
    stripped = payload.lstrip()
    match = re.match(r"\\begin\{([^}]+)\}", stripped)
    return bool(match and match.group(1).lower() in _BLOCK_MATH_ENVIRONMENTS)


@renders(phase=RenderPhase.POST, priority=5, name="inline_code_fallback", auto_mark=False)
def render_inline_code_fallback(root: Tag, context: RenderContext) -> None:
    """Convert lingering inline code nodes that escaped the PRE phase."""
    for code in list(root.find_all("code")):
        if code.find_parent("pre"):
            continue
        if context.is_processed(code):
            continue
        render_inline_code(code, context)
