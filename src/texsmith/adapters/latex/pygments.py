"""Pygments integration helpers for LaTeX rendering."""

from __future__ import annotations

from collections.abc import Iterable

from pygments import highlight
from pygments.formatters import LatexFormatter
from pygments.lexers import ClassNotFound, TextLexer, get_lexer_by_name


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


__all__ = ["PygmentsLatexHighlighter"]
