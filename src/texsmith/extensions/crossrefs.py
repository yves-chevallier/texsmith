"""Markdown extension resolving ``@alias:key`` cross-document references.

``@fw:watchdog`` names an item of the document being converted; ``@fwrev:fw:watchdog``
names one published by *another* document, through the inventory declared under
the ``fwrev`` alias in the front matter (see :mod:`texsmith.core.crossrefs`).

Both spellings reach this extension as the same empty ``<a href="#…">`` anchor
produced by the cross-reference shorthand. A resolved external citation renders
as **text**, not as a link: its target lives in a different PDF, so a local
``\\hyperref`` would be a dead link dressed up as a live one.
"""

from __future__ import annotations

import logging
from xml.etree import ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from texsmith.core.crossrefs import CrossRefResolver


logger = logging.getLogger(__name__)


def _resolver(md: Markdown | None) -> CrossRefResolver | None:
    resolver = getattr(md, "texsmith_crossrefs", None)
    return resolver if isinstance(resolver, CrossRefResolver) else None


class _CrossRefTreeprocessor(Treeprocessor):
    """Replace external citations with their published label."""

    def run(self, root: ElementTree.Element) -> None:  # type: ignore[override]
        """Resolve every ``@alias:key`` anchor against its inventory."""
        resolver = _resolver(self.md)
        if resolver is None or not resolver.sources:
            return

        for element in root.iter("a"):
            href = element.get("href") or ""
            if not href.startswith("#"):
                continue
            alias, separator, key = href[1:].partition(":")
            if not separator or not key or not resolver.knows(alias):
                continue

            rendered = resolver.resolve(alias, key)
            # An unresolved citation stays visible in the output: a silently
            # dropped reference is how a contractual document ships a hole.
            element.text = rendered if rendered is not None else f"[?{alias}:{key}]"
            del element.attrib["href"]


class CrossRefsExtension(Extension):
    """Register the cross-document reference treeprocessor."""

    def __init__(self, **kwargs: object) -> None:
        self.config = {
            "resolver": [
                None,
                "CrossRefResolver holding the inventories declared by the document.",
            ],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802 - markdown hook
        """Wire the treeprocessor and seed the per-conversion resolver slot."""
        configured = self.getConfig("resolver")
        if isinstance(configured, CrossRefResolver):
            md.texsmith_crossrefs = configured  # type: ignore[attr-defined]
        elif not hasattr(md, "texsmith_crossrefs"):
            md.texsmith_crossrefs = None  # type: ignore[attr-defined]

        # Below the counter treeprocessor (4): a local counter always wins, and
        # aliases can never shadow the document's own series.
        md.treeprocessors.register(_CrossRefTreeprocessor(md), "texsmith_crossrefs", 3)


def makeExtension(**kwargs: object) -> CrossRefsExtension:  # noqa: N802 - Markdown API hook; pragma: no cover
    return CrossRefsExtension(**kwargs)


__all__ = ["CrossRefsExtension", "makeExtension"]
