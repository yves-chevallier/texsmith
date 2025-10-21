"""Utility helpers shared by the LaTeX renderer."""

from __future__ import annotations

import codecs
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlparse


try:  # pragma: no cover - graceful degradation
    import latexcodec  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    latexcodec = None  # type: ignore[assignment]


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

_ACCENT_COMMANDS = {
    "\u0300": r"\`",  # grave
    "\u0301": r"\'",  # acute
    "\u0302": r"\^",  # circumflex
    "\u0303": r"\~",  # tilde
    "\u0304": r"\=",  # macron
    "\u0306": r"\u",  # breve
    "\u0307": r"\.",  # dot above
    "\u0308": r"\"",  # diaeresis
    "\u030a": r"\r",  # ring above
    "\u030b": r"\H",  # double acute
    "\u030c": r"\v",  # caron
    "\u0327": r"\c",  # cedilla
    "\u0328": r"\k",  # ogonek
}

_SYMBOL_LATEX_MAP = {
    "–": r"\textendash{}",
    "—": r"\textemdash{}",
    "―": r"\textemdash{}",
    "…": r"\ldots{}",
}

_SUPERSCRIPT_CHARS = set(
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏˡᵐᶰᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ"
)
_SUBSCRIPT_CHARS = set("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₔₓₕₖₗₘₙₚₛₜᵢᵣᵤᵥᵦᵧᵨᵩᵪ")


_ACCENT_NEEDS_BRACES_PATTERN = re.compile(
    r"\\([" + re.escape("`'^\"~=\\.Hrvuck") + r"])\s*([A-Za-z])(?![A-Za-z])"
)


def _wrap_latexcodec_output(payload: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        command, char = match.groups()
        return f"\\{command}{{{char}}}"

    return _ACCENT_NEEDS_BRACES_PATTERN.sub(_repl, payload)


def _escape_combining_character(char: str) -> str | None:
    normalized = unicodedata.normalize("NFD", char)
    if len(normalized) <= 1:
        return None

    base = normalized[0]
    combining = normalized[1:]
    latex = _BASIC_LATEX_ESCAPE_MAP.get(base, base)

    for mark in combining:
        command = _ACCENT_COMMANDS.get(mark)
        if command is None:
            return None
        latex = f"{command}{{{latex}}}"
    return latex


def _escape_character(char: str) -> str:
    if char in _BASIC_LATEX_ESCAPE_MAP:
        return _BASIC_LATEX_ESCAPE_MAP[char]

    if char in _SYMBOL_LATEX_MAP:
        return _SYMBOL_LATEX_MAP[char]

    escaped = _escape_combining_character(char)
    if escaped is not None:
        return escaped

    return char


def escape_latex_chars(text: str) -> str:
    """Escape LaTeX special characters leveraging latexcodec when available."""

    if not text:
        return text

    if latexcodec is not None:
        escaped_segments: list[str] = []
        for char in text:
            if char in _SYMBOL_LATEX_MAP:
                escaped_segments.append(_SYMBOL_LATEX_MAP[char])
                continue

            if char in _SUPERSCRIPT_CHARS or char in _SUBSCRIPT_CHARS:
                escaped_segments.append(char)
                continue

            try:
                encoded = codecs.encode(char, "latex")
            except Exception:  # pragma: no cover - fallback on unexpected errors
                escaped_segments.append(_escape_character(char))
                continue

            piece = (
                encoded.decode("utf-8") if isinstance(encoded, bytes) else str(encoded)
            )
            escaped_segments.append(_wrap_latexcodec_output(piece))

        return "".join(escaped_segments)

    return "".join(_escape_character(char) for char in text)


def points_to_mm(points: float) -> float:
    """Convert points to millimetres."""

    return points * 25.4 / 72


def resolve_asset_path(file_path: Path, path: str | Path) -> Path | None:
    """Resolve an asset path relative to a Markdown source file."""

    file_path = Path(file_path)
    if file_path.name == "index.md":
        file_path = file_path.parent
    target = (file_path / path).resolve()
    return target if target.exists() else None


def is_valid_url(url: str) -> bool:
    """Check whether a URL is valid."""

    try:
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except ValueError:
        return False
