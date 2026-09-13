"""BeautifulSoup attribute helpers for the snippet HTML rewriter.

The only consumer left is :mod:`texsmith.adapters.plugins.snippet`, which
rewrites ``.snippet`` fences in the HTML MkDocs renders. Both helpers are pure
queries over a bs4 attribute value.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast


__all__ = ["coerce_attribute", "gather_classes"]


def coerce_attribute(value: Any) -> str | None:
    """Normalise a BeautifulSoup attribute value to a string when possible."""
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


def gather_classes(value: Any) -> list[str]:
    """Return a list of classes extracted from a BeautifulSoup attribute."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return [cast(str, item) for item in value if isinstance(item, str)]
    return []
