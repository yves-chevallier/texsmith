"""Pygments integration helpers for LaTeX rendering."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pygments import highlight
from pygments.formatters import LatexFormatter
from pygments.lexers import ClassNotFound, TextLexer, get_lexer_by_name


class PygmentsLatexHighlighter:
    """Convert source code to LaTeX using Pygments."""

    def __init__(
        self,
        *,
        commandprefix: str = "PY",
        style: str = "default",
        verboptions: str | None = None,
    ) -> None:
        self.commandprefix = commandprefix
        self.style = style
        self.verboptions = (
            verboptions
            or r"breaklines, breakanywhere, commandchars=\\\{\}"
        )

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

        formatter = LatexFormatter(
            full=False,
            linenos=linenos,
            style=self.style,
            commandprefix=self.commandprefix,
            linenostart=1,
            linenostep=1,
            verboptions=self.verboptions,
            hl_lines=list(highlight_lines or []),
        )
        latex_code = highlight(code, lexer, formatter)
        style_defs = formatter.get_style_defs()
        return latex_code, style_defs


__all__ = ["PygmentsLatexHighlighter"]
