"""LaTeX escaping and text-transform machinery (backend responsibility).

The writer owns escaping. This module moves :func:`escape_latex_chars` out of
``adapters/latex/utils.py`` (where it was a shared utility) into the LaTeX
backend, and gathers the unicode → LaTeX text transforms (dashes, smart
quotes, sub/superscript runs, emoji segmentation, math-payload protection)
that the legacy ``adapters/handlers/inline.py`` PRE phase applied to plain
text nodes. The IR carries raw text in :class:`~texsmith.ir.Str`; the writer
escapes it here exactly as the old pipeline did, so the produced LaTeX is
byte-identical.
"""

from __future__ import annotations

from collections.abc import Callable
import re
import unicodedata

import emoji as _emoji
from pylatexenc.latexencode import unicode_to_latex


_BASIC_LATEX_ESCAPE_MAP = {
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "$": r"\$",
    "_": r"\_",
    "^": r"\^",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "\\": r"\textbackslash{}",
}

_COMMON_SYMBOL_MAP = {
    "→": r"\(\rightarrow\)",
    "←": r"\(\leftarrow\)",
    "⇒": r"\(\Rightarrow\)",
    "⇐": r"\(\Leftarrow\)",
    "≥": r"\(\geq\)",
    "≤": r"\(\leq\)",
    "≠": r"\(\neq\)",
    "≈": r"\(\approx\)",
    "±": r"\(\pm\)",
    "×": r"\(\times\)",  # noqa: RUF001
    "÷": r"\(\div\)",
    "∞": r"\(\infty\)",
}

_ACCENT_NEEDS_BRACES_PATTERN = re.compile(
    r"\\([" + re.escape("`'^\"~=\\.Hrvuck") + r"])\s*([A-Za-z])(?!\{)"
)
_ACCENT_CONTROL_TARGET_PATTERN = re.compile(
    r"\\([" + re.escape("`'^\"~=\\.Hrvuck") + r"])\s*(\\[ij])"
)


def _wrap_latex_output(payload: str) -> str:
    """Ensure accent macros wrap their payload in braces."""

    def _repl(match: re.Match[str]) -> str:
        command, char = match.groups()
        return f"\\{command}{{{char}}}"

    payload = _ACCENT_NEEDS_BRACES_PATTERN.sub(_repl, payload)

    def _repl_control(match: re.Match[str]) -> str:
        command, control = match.groups()
        return f"\\{command}{{{control}}}"

    return _ACCENT_CONTROL_TARGET_PATTERN.sub(_repl_control, payload)


def escape_latex_chars(text: str, *, legacy_accents: bool = False) -> str:
    """Escape LaTeX special characters leveraging pylatexenc."""
    if not text:
        return text
    parts: list[str] = []
    buffer: list[str] = []

    def _encode_chunk(chunk: str) -> str:
        escaped = "".join(_BASIC_LATEX_ESCAPE_MAP.get(char, char) for char in chunk)
        if legacy_accents:
            encoded = unicode_to_latex(escaped, non_ascii_only=True, unknown_char_warning=False)
            return _wrap_latex_output(encoded)
        return escaped

    def _should_skip_encoding(char: str) -> bool:
        try:
            name = unicodedata.name(char)
        except ValueError:
            return False
        if "SUPERSCRIPT" in name or "SUBSCRIPT" in name:
            return True
        return "MODIFIER LETTER" in name and ("SMALL" in name or "CAPITAL" in name)

    for char in text:
        replacement = _COMMON_SYMBOL_MAP.get(char)
        if replacement is not None:
            if buffer:
                parts.append(_encode_chunk("".join(buffer)))
                buffer.clear()
            parts.append(replacement)
            continue
        if _should_skip_encoding(char):
            if buffer:
                parts.append(_encode_chunk("".join(buffer)))
                buffer.clear()
            parts.append(char)
        else:
            buffer.append(char)

    if buffer:
        parts.append(_encode_chunk("".join(buffer)))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Unicode → LaTeX text transforms (legacy inline.py PRE phase)
# ---------------------------------------------------------------------------

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
    return _replace_unicode_scripts(text, _SUPERSCRIPT_PATTERN, _SUPERSCRIPT_MAP, "textsuperscript")


def _replace_unicode_subscripts(text: str) -> str:
    return _replace_unicode_scripts(text, _SUBSCRIPT_PATTERN, _SUBSCRIPT_MAP, "textsubscript")


def _replace_unicode_dashes(text: str) -> str:
    if not text:
        return text
    return _UNICODE_DASH_PATTERN.sub(lambda match: _UNICODE_DASH_MAP.get(match.group(0), "-"), text)


def _replace_unicode_punctuation(text: str) -> str:
    if not text:
        return text
    return _UNICODE_PUNCT_PATTERN.sub(
        lambda match: _UNICODE_PUNCT_MAP.get(match.group(0), ""), text
    )


def prepare_plain_text(text: str, *, legacy_accents: bool = False) -> str:
    """Escape and apply the unicode text transforms for a plain-text run.

    Mirrors ``adapters/handlers/inline.py:_prepare_plain_text``: smart quotes
    and dashes are normalised first, the text is escaped, then unicode
    sub/superscript runs become ``\\textsubscript`` / ``\\textsuperscript``.
    """
    text = _replace_unicode_punctuation(text)
    text = _replace_unicode_dashes(text)
    escaped = escape_latex_chars(text, legacy_accents=legacy_accents)
    escaped = _replace_unicode_superscripts(escaped)
    return _replace_unicode_subscripts(escaped)


def _segment_text_with_emoji(text: str) -> list[tuple[str, str]]:
    """Split text into plain fragments and emoji clusters."""
    if not text:
        return []
    if text.isascii():
        return [("text", text)]
    entries = _emoji.emoji_list(text)
    if not entries:
        return [("text", text)]
    segments: list[tuple[str, str]] = []
    cursor = 0
    for entry in entries:
        start = entry["match_start"]
        end = entry["match_end"]
        if start > cursor:
            segments.append(("text", text[cursor:start]))
        segments.append(("emoji", text[start:end]))
        cursor = end
    if cursor < len(text):
        segments.append(("text", text[cursor:]))
    return segments


def escape_text_segment(
    text: str,
    *,
    legacy_accents: bool = False,
    emoji_renderer: Callable[[str], str] | None = None,
) -> str:
    """Escape a plain-text run, splitting out emoji clusters.

    Mirrors ``adapters/handlers/inline.py:_escape_text_segment``. Plain
    fragments go through :func:`prepare_plain_text`; emoji clusters are handed
    to ``emoji_renderer`` (font command or artifact image). When no renderer is
    supplied, emoji are escaped as ordinary text.
    """
    chunks: list[str] = []
    for kind, payload in _segment_text_with_emoji(text):
        if kind == "text":
            if payload:
                chunks.append(prepare_plain_text(payload, legacy_accents=legacy_accents))
        elif emoji_renderer is not None:
            chunks.append(emoji_renderer(payload))
        else:
            chunks.append(prepare_plain_text(payload, legacy_accents=legacy_accents))
    return "".join(chunks)


__all__ = [
    "_MATH_PAYLOAD_PATTERN",
    "escape_latex_chars",
    "escape_text_segment",
    "prepare_plain_text",
]
