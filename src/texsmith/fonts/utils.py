"""Shared helpers for font handling."""

from __future__ import annotations

from collections.abc import Iterable


def normalize_family(name: str) -> str:
    """Return a normalised font family key suitable for lookups."""
    return "".join(ch for ch in name.casefold() if ch not in {" ", "-", "_"})


def parse_unicode_range(range_value: str) -> tuple[str, str]:
    """
    Split a range string like ``U+0700..U+074F`` into (start, end) hex parts.

    If the range is a single codepoint, ``start`` and ``end`` will be identical.
    """
    if isinstance(range_value, (tuple, list)) and len(range_value) == 2:
        start, end = range_value
        return (str(start).upper(), str(end).upper())

    cleaned = range_value.replace("U+", "").replace("\\u", "").replace("u+", "")
    if ".." in cleaned:
        start, end = cleaned.split("..", 1)
    elif "-" in cleaned:
        start, end = cleaned.split("-", 1)
    else:
        start = end = cleaned
    return (start.upper(), end.upper())


def unicode_class_ranges(ranges: Iterable[str]) -> list[tuple[str, str]]:
    """Convert ``U+`` ranges into ``(start, end)`` tuples ready for ucharclasses."""
    return [parse_unicode_range(item) for item in ranges]


__all__ = ["normalize_family", "parse_unicode_range", "unicode_class_ranges"]
