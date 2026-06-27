"""LaTeX formatting helpers for index entries, used by the LaTeX writer."""

from __future__ import annotations

from pathlib import Path
import re

from texsmith.adapters.latex.utils import escape_latex_chars


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
INDEX_TEMPLATE = TEMPLATE_DIR / "index.tex"


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


def _apply_style(fragment: str, style: str) -> str:
    if style == "b":
        return f"\\textbf{{{fragment}}}"
    if style == "i":
        return f"\\textit{{{fragment}}}"
    if style == "bi":
        return f"\\textbf{{\\textit{{{fragment}}}}}"
    return fragment
