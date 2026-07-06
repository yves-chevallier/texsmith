"""Markdown extension providing the ``@[label]`` cross-reference shorthand.

TeXSmith documents label their targets with ``{#sec:intro}`` attribute lists
(headings), ``Table: caption {#tbl:data}`` caption lines or ``\\label{}`` in
math. This extension turns the companion reference syntax into an internal
link that the writers already understand (``<a href="#label"></a>`` becomes
``\\ref{label}`` in LaTeX and ``#ref(<label>)`` in Typst):

* ``@[sec:intro]`` — bracketed form, any label;
* ``@sec:intro`` — bare form when the label is a single word made of
  ``[A-Za-z0-9_:.-]`` characters (trailing sentence punctuation such as
  ``.`` or ``,`` is left out of the label).

A literal ``@`` can be kept with ``\\@``. E-mail addresses and ``@`` embedded
in words or URLs are not matched.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor


# ``@`` must not be glued to a preceding word (e-mail addresses) nor follow
# ``/``, ``.`` or ``:`` (URL paths such as ``https://social/@user``). The bare
# form allows ``:.-`` inside the label but must end on an alphanumeric so the
# sentence punctuation after ``en @sec:intro.`` stays out of the label.
_REFERENCE_PATTERN = (
    r"(?<![\w@/.:])@"
    r"(?:\[(?P<bracketed>[^\[\]]+)\]"
    r"|(?P<bare>[A-Za-z0-9_](?:[A-Za-z0-9_:.-]*[A-Za-z0-9_])?))"
)


class _ReferenceInlineProcessor(InlineProcessor):
    """Convert ``@[label]`` / ``@label`` into ``<a href="#label"></a>``."""

    def handleMatch(  # type: ignore[override]  # noqa: N802 - Markdown API requires camelCase
        self,
        match,  # noqa: ANN001
        data: str,
    ) -> tuple[ElementTree.Element | None, int | None, int | None]:
        label = match.group("bracketed") or match.group("bare") or ""
        label = label.strip()
        if not label:
            return None, None, None

        element = ElementTree.Element("a", {"href": f"#{label}"})
        return element, match.start(0), match.end(0)


class SmartReferenceExtension(Extension):
    """Register the ``@[label]`` cross-reference inline processor."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        # Allow ``\@`` to produce a literal ``@`` without triggering the
        # reference syntax. Assign a copy so the class-level default list of
        # ``markdown.Markdown`` is left untouched.
        if "@" not in md.ESCAPED_CHARS:
            md.ESCAPED_CHARS = [*md.ESCAPED_CHARS, "@"]
        processor = _ReferenceInlineProcessor(_REFERENCE_PATTERN, md)
        # Above ``reference`` (170) so ``@[label]`` is not parsed as a
        # reference-style link, below ``escape`` (180) so ``\@`` wins.
        md.inlinePatterns.register(processor, "texsmith_references", 175)


def makeExtension(  # noqa: N802
    **_: object,
) -> SmartReferenceExtension:  # pragma: no cover - API hook
    return SmartReferenceExtension()


__all__ = ["SmartReferenceExtension", "makeExtension"]
