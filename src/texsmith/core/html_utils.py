"""Cross-cutting HTML helpers shared by handlers and conversion layers.

These utilities operate on BeautifulSoup trees and encapsulate one-liner
transforms that would otherwise be open-coded in multiple places, trading a
tiny module for a single source of truth.
"""

from __future__ import annotations

from bs4.element import Comment, Tag


def strip_html_comments(root: Tag) -> None:
    """Remove every HTML comment node from ``root`` in place.

    HTML comments that survive into the LaTeX pipeline either leak as literal
    text (fragment serialisation) or interfere with downstream text scans,
    so we drop them as early as possible. The pass is idempotent: calling it
    twice is a no-op.
    """
    for comment in root.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


__all__ = ["strip_html_comments"]
