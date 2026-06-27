"""HTML heading-analysis parsers used by :mod:`texsmith.core.documents`.

Two small :class:`~html.parser.HTMLParser` subclasses that scan a rendered HTML
body for heading structure: the minimum heading level present, and the first
heading's level / text (for title promotion). Kept out of ``documents`` so the
``Document`` model stays focused on its data and slot logic.
"""

from __future__ import annotations

from html.parser import HTMLParser


class HeadingLevelScanner(HTMLParser):
    """Record the smallest ``<h1>`` to ``<h6>`` level seen in a fragment."""

    __slots__ = ("minimum_level",)

    def __init__(self) -> None:
        super().__init__()
        self.minimum_level: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not tag:
            return
        name = tag.lower()
        if not name.startswith("h") or len(name) < 2 or not name[1].isdigit():
            return
        try:
            level = int(name[1])
        except ValueError:
            return
        if not 1 <= level <= 6:
            return
        if self.minimum_level is None or level < self.minimum_level:
            self.minimum_level = level


class HeadingInspector(HTMLParser):
    """Capture the first heading's level, per-level counts and its text."""

    __slots__ = ("_depth", "_resolved", "first_level", "level_counts", "parts")

    def __init__(self) -> None:
        super().__init__()
        self._depth = 0
        self._resolved = False
        self.first_level: int | None = None
        self.level_counts: dict[int, int] = {}
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if not name.startswith("h") or len(name) < 2 or not name[1].isdigit():
            if self._depth:
                self._depth += 1
            return

        try:
            level = int(name[1])
        except ValueError:
            if self._depth:
                self._depth += 1
            return

        if not 1 <= level <= 6:
            if self._depth:
                self._depth += 1
            return

        self.level_counts[level] = self.level_counts.get(level, 0) + 1
        if self._resolved:
            return

        if self.first_level is None:
            self.first_level = level
            self._depth = 1
            return

        if self._depth:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._depth:
            return
        self._depth -= 1
        if self._depth == 0:
            self._resolved = True

    def handle_data(self, data: str) -> None:
        if self._depth and not self._resolved:
            self.parts.append(data)


__all__ = ["HeadingInspector", "HeadingLevelScanner"]
