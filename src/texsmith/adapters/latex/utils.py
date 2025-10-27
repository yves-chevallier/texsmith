"""Utility helpers specific to LaTeX rendering."""

from __future__ import annotations

import re
import unicodedata

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


__all__ = ["escape_latex_chars"]
