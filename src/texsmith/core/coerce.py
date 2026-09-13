"""The one reading of a boolean written as text.

Front matter, fence attributes, template attributes and CLI overrides all
carry booleans as strings, and every consumer used to spell the accepted
words itself — ten times, with sets that had drifted apart. This module is
the single spelling; a caller that also accepts a domain word (``dogear``,
``border``) resolves it before asking, and a caller that must reject an
unknown value checks for :data:`None`.
"""

from __future__ import annotations

from typing import Any


__all__ = ["FALSE_WORDS", "TRUE_WORDS", "coerce_bool"]

#: The spellings of ``True``. An empty string is not one of them: it means
#: "unset", which is the caller's default, not ``False``.
TRUE_WORDS = frozenset({"true", "yes", "on", "1"})

#: The spellings of ``False``.
FALSE_WORDS = frozenset({"false", "no", "off", "0"})


def coerce_bool(value: Any) -> bool | None:
    """``True``/``False`` for a value that spells one, ``None`` for anything else.

    ``None`` covers both "absent" and "not a boolean": the caller decides
    whether that is a default or an error.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in TRUE_WORDS:
            return True
        if token in FALSE_WORDS:
            return False
    return None
