"""Pygments integration helpers for LaTeX rendering."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
import re

from pygments import highlight
from pygments.formatters import LatexFormatter
from pygments.lexers import ClassNotFound, TextLexer, get_lexer_by_name


try:  # pragma: no cover - depends on the installed Pygments layout
    from pygments.formatters.latex import escape_tex as _escape_tex
except ImportError:  # pragma: no cover - fallback for exotic Pygments builds
    _PYGMENTS_ESCAPES = {
        "\\": "Zbs",
        "{": "Zob",
        "}": "Zcb",
        "^": "Zca",
        "_": "Zus",
        "&": "Zam",
        "<": "Zlt",
        ">": "Zgt",
        "#": "Zsh",
        "%": "Zpc",
        "$": "Zdl",
        "-": "Zhy",
        '"': "Zdq",
        "~": "Zti",
    }

    def _escape_tex(text: str, commandprefix: str) -> str:
        return "".join(
            f"\\{commandprefix}{_PYGMENTS_ESCAPES[char]}{{}}" if char in _PYGMENTS_ESCAPES else char
            for char in text
        )


ALLOW_BREAK = r"\allowbreak{}"


@lru_cache(maxsize=32)
def _break_pattern(chars: str, commandprefix: str) -> re.Pattern[str] | None:
    """Return a pattern matching the escaped form of every break character."""
    forms = {_escape_tex(char, commandprefix) for char in chars if char}
    if not forms:
        return None
    ordered = sorted(forms, key=len, reverse=True)
    return re.compile("|".join(re.escape(form) for form in ordered))


@lru_cache(maxsize=8)
def _command_pattern(commandprefix: str) -> re.Pattern[str]:
    r"""Return a pattern isolating ``\PY{token}`` markers from their payload."""
    return re.compile(r"(\\" + re.escape(commandprefix) + r"\{[^{}]*\})")


class PygmentsLatexHighlighter:
    """Convert source code to LaTeX using Pygments."""

    def __init__(
        self,
        *,
        commandprefix: str = "PY",
        style: str = "bw",
        verboptions: str | None = None,
    ) -> None:
        self.commandprefix = commandprefix
        self.style = style
        self.verboptions = verboptions or r"breaklines, breakanywhere, commandchars=\\\{\}"

    @property
    def style_key(self) -> str:
        """Identifier that groups style definitions."""
        return f"{self.style}:{self.commandprefix}"

    def render(
        self,
        code: str,
        language: str,
        *,
        linenos: bool,
        highlight_lines: Iterable[int] | None = None,
    ) -> tuple[str, str]:
        """Return the LaTeX code and style definitions for a payload."""
        try:
            lexer = get_lexer_by_name(language or "text")
        except ClassNotFound:
            lexer = TextLexer()

        def _format_ranges(values: Iterable[int]) -> str:
            sorted_vals = sorted(set(values))
            if not sorted_vals:
                return ""
            ranges: list[str] = []
            start = end = sorted_vals[0]
            for num in sorted_vals[1:]:
                if num == end + 1:
                    end = num
                else:
                    ranges.append(f"{start}-{end}" if start != end else str(start))
                    start = end = num
            ranges.append(f"{start}-{end}" if start != end else str(start))
            return ",".join(ranges)

        verb_options = self.verboptions
        formatted_highlight = _format_ranges(highlight_lines or [])
        if formatted_highlight:
            verb_options = f"{verb_options},highlightlines={{{formatted_highlight}}}"

        formatter = LatexFormatter(
            full=False,
            linenos=linenos,
            style=self.style,
            commandprefix=self.commandprefix,
            linenostart=1,
            linenostep=1,
            verboptions=verb_options,
            hl_lines=list(highlight_lines or []),
        )
        latex_code = highlight(code, lexer, formatter)
        style_defs = formatter.get_style_defs()
        return latex_code, style_defs

    def render_inline(self, code: str, language: str) -> tuple[str, str]:
        """Return inline LaTeX macros for a code snippet (no Verbatim env)."""
        try:
            lexer = get_lexer_by_name(language or "text")
        except ClassNotFound:
            lexer = TextLexer()

        formatter = LatexFormatter(
            full=False,
            linenos=False,
            style=self.style,
            commandprefix=self.commandprefix,
            nowrap=True,
        )
        latex_code = highlight(code, lexer, formatter)
        style_defs = formatter.get_style_defs()
        return latex_code, style_defs

    def add_break_points(self, latex: str, chars: str) -> str:
        """Insert ``\\allowbreak`` after each break character of ``latex``.

        Highlighted output interleaves ``\\PY{token}`` markers with escaped
        source text; the markers are left untouched so a token name is never
        rewritten, and only the payload between them gains break opportunities.
        """
        if not latex or not chars:
            return latex
        pattern = _break_pattern(chars, self.commandprefix)
        if pattern is None:
            return latex

        def _insert(match: re.Match[str]) -> str:
            return match.group(0) + ALLOW_BREAK

        segments = _command_pattern(self.commandprefix).split(latex)
        for index, segment in enumerate(segments):
            if index % 2 == 0 and segment:
                segments[index] = pattern.sub(_insert, segment)
        return "".join(segments)


__all__ = ["PygmentsLatexHighlighter"]
