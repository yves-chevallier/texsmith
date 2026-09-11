"""Small attribute helpers shared by the HTML lowerings.

A handful of pure BeautifulSoup utilities the readers need, kept local to
``readers/`` so the readers carry no dependency on the writer-side helpers.
They contain no LaTeX and no soup mutation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast

from texsmith.ir import model


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
    """Build the sorted ``attrs`` tuple used by the legacy ``Div`` / ``Span`` nodes."""
    return tuple(sorted(extra.items()))


def make_attrs(
    *,
    id: str | None = None,  # noqa: A002 - mirrors ``Attrs.id``
    classes: Iterable[str] = (),
    kv: Mapping[str, str | None] | Iterable[tuple[str, str | None]] = (),
) -> model.Attrs:
    """Build a generated :class:`~texsmith.ir.model.Attrs`; empty values are left out."""
    pairs = kv.items() if isinstance(kv, Mapping) else kv
    return model.Attrs(
        classes=tuple(cls for cls in classes if cls),
        id=id or None,
        kv=tuple((key, value) for key, value in pairs if value),
    )


__all__ = ["attrs_tuple", "classes", "coerce_attr", "make_attrs"]
