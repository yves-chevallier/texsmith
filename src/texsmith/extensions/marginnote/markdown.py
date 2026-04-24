"""Markdown extension providing the ``{margin}[text]{side?}`` inline syntax.

The shorthand fits the unified ``{keyword}[content]`` family already used by
``{index}[term]`` and ``{latex}[payload]``. An optional single-letter suffix
forces the margin side:

- ``{margin}[note]``        → default (right/outer)
- ``{margin}[note]{l}``     → left (``\\reversemarginpar``)
- ``{margin}[note]{r}``     → right
- ``{margin}[note]{o}``     → outer (default in two-sided layouts)
- ``{margin}[note]{i}``     → inner (opposite of outer)

Inline Markdown inside the note (``**bold**``, ``*italic*``, ``` `code` ```,
links) is preserved — python-markdown's later inline passes run on the
element's text, so downstream TeXSmith handlers emit the expected LaTeX.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor


MARGIN_NOTE_TAG = "ts-marginnote"
"""Custom HTML tag name consumed by the LaTeX renderer.

A dedicated tag avoids collisions with the many generic ``<span>`` handlers
registered by the renderer (smallcaps, twemoji, keystrokes, index…) — those
all declare ``nestable=False`` which would otherwise suppress our node's
``after_children`` dispatch.
"""

# Same nesting rule as ``latex_raw``: allow one level of ``[...]`` inside the
# payload so authors can write LaTeX-ish content (``\\cite[prenote]{key}``)
# without the outer match being truncated at the first ``]``.
_PATTERN = (
    r"\{margin\}"
    r"\[(?P<content>(?:[^\[\]]|\[[^\[\]]*\])+)\]"
    r"(?:\{(?P<side>[lroiLROI])\})?"
)

_SIDE_ALIASES: dict[str, str] = {
    "l": "l",
    "i": "l",  # inner → left in single-side semantics
    "r": "r",
    "o": "r",  # outer → right in single-side semantics
}


class _MarginNoteInlineProcessor(InlineProcessor):
    """Turn ``{margin}[…]{side?}`` into a ``<ts-marginnote>`` custom element.

    The node's text is assigned as a plain ``str`` (not ``AtomicString``) so
    subsequent lower-priority inline patterns continue to process bold,
    italic, code, links, etc. inside the margin note.
    """

    def handleMatch(  # noqa: N802 - Markdown inline API requires camelCase
        self,
        match: re.Match[str],
        data: str,
    ) -> tuple[ElementTree.Element | None, int, int]:  # type: ignore[override]
        del data
        content = (match.group("content") or "").strip()
        if not content:
            return None, match.start(0), match.end(0)

        element = ElementTree.Element(MARGIN_NOTE_TAG)

        side_token = match.group("side")
        if side_token:
            normalised = _SIDE_ALIASES.get(side_token.lower())
            if normalised:
                element.set("data-side", normalised)

        element.text = content
        return element, match.start(0), match.end(0)


class MarginNoteExtension(Extension):
    """Register the margin-note inline processor on the Markdown pipeline."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        # Priority 181 matches the other ``{keyword}[payload]`` processors
        # (``latex_raw`` at 181, ``index`` at 180) and keeps the match above
        # core emphasis/link patterns so brace-wrapped content is consumed
        # first.
        processor = _MarginNoteInlineProcessor(_PATTERN, md)
        md.inlinePatterns.register(processor, "texsmith_marginnote", 181)


def makeExtension(  # noqa: N802 - Markdown entry point contract
    **kwargs: object,
) -> MarginNoteExtension:  # pragma: no cover - trivial factory
    return MarginNoteExtension(**kwargs)


__all__ = ["MARGIN_NOTE_TAG", "MarginNoteExtension", "makeExtension"]
