"""Standalone Typst document assembly.

The LaTeX backend wraps its body in a full template/fragment/preamble system.
The Typst backend's covered subset has no such machinery yet; this module
produces a minimal but *valid* standalone ``.typ`` document — a small preamble
(page/text defaults and an optional title) followed by the writer body — so a
single Markdown/HTML source can be compiled to PDF with the ``typst`` binary.
"""

from __future__ import annotations


def render_document(body: str, *, title: str = "", uses_mitex: bool = False) -> str:
    """Wrap a Typst writer ``body`` into a standalone, compilable document."""
    lines: list[str] = []
    if uses_mitex:
        lines.append('#import "@preview/mitex:0.2.6": mi, mitex')
    lines += [
        "#set page(margin: 2.5cm)",
        '#set text(font: "New Computer Modern", size: 11pt)',
        "#set par(justify: true)",
    ]
    if title.strip():
        lines.append("")
        lines.append(f'#align(center)[#text(size: 1.6em, weight: "bold")[{title.strip()}]]')
        lines.append("#v(1em)")
    preamble = "\n".join(lines)
    return f"{preamble}\n\n{body.strip()}\n"


__all__ = ["render_document"]
