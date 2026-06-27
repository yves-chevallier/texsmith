"""Small attribute helpers shared by the HTML lowerings.

A handful of pure BeautifulSoup utilities the reader needs, kept local to
``readers/`` so the reader carries no dependency on the writer-side helpers.
They contain no LaTeX and no soup mutation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast


def coerce_attr(value: Any) -> str | None:
    """Normalise a BeautifulSoup attribute value to a single string or ``None``."""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(value, Iterable):
        for item in value:
            if isinstance(item, str):
                return item
    return None


def classes(value: Any) -> list[str]:
    """Return the class list from a BeautifulSoup ``class`` attribute value."""
    if isinstance(value, str):
        return value.split()
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return [cast(str, item) for item in value if isinstance(item, str)]
    return []


def attrs_tuple(extra: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Build the sorted ``attrs`` tuple used by generic ``Div`` / ``Span`` nodes."""
    return tuple(sorted(extra.items()))


__all__ = ["attrs_tuple", "classes", "coerce_attr"]
