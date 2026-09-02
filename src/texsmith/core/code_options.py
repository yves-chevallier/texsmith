"""Normalisation helpers for the ``code`` front-matter section.

The section drives both the listing engine used for fenced blocks and the way
*inline* code spans are typeset. Inline spans live inside a justified
paragraph, so unlike a code block — which ``fvextra`` already wraps with
``breaklines``/``breakanywhere`` — they need explicit break opportunities or a
long identifier runs straight into the margin. ``code.inline`` declares those
opportunities and, optionally, drops the syntax colouring so inline code is
plain typewriter text again.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


CODE_ENGINES = {"minted", "listings", "verbatim", "pygments"}

#: Break characters applied when ``code.inline.breaks`` is not declared. Only
#: the hyphen, which is what TeXSmith has always broken on.
DEFAULT_INLINE_BREAKS = "-"

#: Break characters used when ``code.inline.breaks`` is ``all`` (or ``true``).
ALL_INLINE_BREAKS = "-_./\\:;,|@+=&#%"

_BREAKS_ALL_ALIASES = {"all", "any", "true", "yes", "on"}
_BREAKS_NONE_ALIASES = {"none", "off", "false", "no"}
_BREAKS_DEFAULT_ALIASES = {"default", "auto"}

_TRUE_ALIASES = {"true", "yes", "on", "1"}
_FALSE_ALIASES = {"false", "no", "off", "0"}


def _filter_break_chars(chars: str) -> str:
    """Keep the punctuation of ``chars``, deduplicated and order-preserving.

    Letters, digits and whitespace are dropped: breaking inside a word makes
    the span harder to read, and a letter could collide with the
    ``\\allowbreak{}`` macro inserted after each break opportunity.
    """
    kept: list[str] = []
    for char in chars:
        if char.isalnum() or char.isspace() or not char.isprintable():
            continue
        if char not in kept:
            kept.append(char)
    return "".join(kept)


def normalise_inline_breaks(value: Any, fallback: str = DEFAULT_INLINE_BREAKS) -> str:
    """Return the break characters declared by ``value``."""
    if value is None:
        return fallback
    if isinstance(value, bool):
        return ALL_INLINE_BREAKS if value else ""
    if isinstance(value, str):
        candidate = value.strip()
        lowered = candidate.lower()
        if lowered in _BREAKS_ALL_ALIASES:
            return ALL_INLINE_BREAKS
        if lowered in _BREAKS_NONE_ALIASES or not candidate:
            return ""
        if lowered in _BREAKS_DEFAULT_ALIASES:
            return DEFAULT_INLINE_BREAKS
        return _filter_break_chars(candidate)
    if isinstance(value, Sequence):
        joined = "".join(str(item) for item in value if item is not None)
        return _filter_break_chars(joined)
    return fallback


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in _TRUE_ALIASES:
            return True
        if candidate in _FALSE_ALIASES:
            return False
    return fallback


def normalise_inline_options(value: Any, fallback: Any = None) -> dict[str, Any]:
    """Return the inline code options as ``{"plain": bool, "breaks": str}``.

    ``value`` accepts the canonical mapping (``{plain: true, breaks: "_./"}``)
    as well as two shorthands: a boolean sets ``plain``, and a bare string is
    read as ``breaks``.
    """
    plain = False
    breaks = DEFAULT_INLINE_BREAKS
    if isinstance(fallback, Mapping):
        plain = _coerce_bool(fallback.get("plain"), plain)
        breaks = normalise_inline_breaks(fallback.get("breaks"), breaks)

    if value is None:
        return {"plain": plain, "breaks": breaks}
    if isinstance(value, bool):
        return {"plain": value, "breaks": breaks}
    if isinstance(value, str):
        return {"plain": plain, "breaks": normalise_inline_breaks(value, breaks)}
    if isinstance(value, Mapping):
        return {
            "plain": _coerce_bool(value.get("plain"), plain),
            "breaks": normalise_inline_breaks(value.get("breaks"), breaks),
        }
    return {"plain": plain, "breaks": breaks}


__all__ = [
    "ALL_INLINE_BREAKS",
    "CODE_ENGINES",
    "DEFAULT_INLINE_BREAKS",
    "normalise_inline_breaks",
    "normalise_inline_options",
]
