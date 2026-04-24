"""Resolve the final fragment list for a template render.

Front matter may declare fragments in one of three shapes:

1. ``None`` — use the template defaults unchanged.
2. A ``list`` — replace the template defaults entirely.
3. A ``dict`` with optional ``append`` / ``prepend`` / ``disable`` keys —
   modify the template defaults without enumerating every entry.

This module separates the front-matter *parsing* (:func:`parse_modifiers`)
from the pure merge semantics (:func:`merge_fragments`) so callers that
already hold a parsed override can skip the dict/list dispatch, and so the
merge can be unit-tested without a template runtime.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class FragmentModifiers:
    """Parsed ``fragments: {append, prepend, disable}`` front-matter payload.

    Each list is already deduplicated and stripped of blanks at parse time,
    so consumers can treat them as ordered sets.
    """

    append: list[str] = field(default_factory=list)
    prepend: list[str] = field(default_factory=list)
    disable: list[str] = field(default_factory=list)


def _clean(values: Any) -> list[str]:
    """Coerce ``values`` into a deduplicated list of stripped strings.

    Accepts ``None``, a single string (treated as a one-element list), or any
    iterable. Entries are ``str()``-coerced, stripped and filtered to keep
    only the first occurrence.
    """
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    seen: set[str] = set()
    cleaned: list[str] = []
    for entry in values:
        name = str(entry).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return cleaned


def parse_modifiers(raw: Any) -> FragmentModifiers | list[str] | None:
    """Interpret a front-matter ``fragments`` value.

    Returns:
    - ``None`` when ``raw`` is ``None`` or any unrecognised shape —
      template defaults apply unchanged.
    - a ``list[str]`` when ``raw`` is a list — replaces the defaults entirely.
    - a :class:`FragmentModifiers` when ``raw`` is a dict of modifiers.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return FragmentModifiers(
            append=_clean(raw.get("append")),
            prepend=_clean(raw.get("prepend")),
            disable=_clean(raw.get("disable")),
        )
    if isinstance(raw, list):
        return _clean(raw)
    return None


def merge_fragments(
    defaults: Sequence[str],
    override: FragmentModifiers | Sequence[str] | None,
    *,
    cli_enable: Sequence[str] = (),
    cli_disable: Sequence[str] = (),
) -> list[str]:
    """Compute the final fragment list from defaults, override and CLI flags.

    Order of operations when ``override`` is a :class:`FragmentModifiers`:
    the front-matter ``disable`` drops entries first, then ``prepend`` adds
    to the head, then ``append`` adds to the tail. CLI flags apply on top:
    ``cli_disable`` drops entries and ``cli_enable`` appends any that are
    still missing. No entry appears twice in the result.

    When ``override`` is a list the defaults are discarded entirely; when
    it is ``None`` the defaults are used as-is.
    """
    cleaned_defaults = _clean(defaults)

    if override is None:
        base = cleaned_defaults
    elif isinstance(override, FragmentModifiers):
        base = [entry for entry in cleaned_defaults if entry not in override.disable]
        base = [entry for entry in override.prepend if entry not in base] + base
        for entry in override.append:
            if entry not in base:
                base.append(entry)
    else:
        base = _clean(override)

    cli_disable_list = _clean(cli_disable)
    cli_enable_list = _clean(cli_enable)

    if not base and not cli_enable_list and not cli_disable_list:
        return []

    result = [entry for entry in base if entry not in cli_disable_list]
    for entry in cli_enable_list:
        if entry not in result:
            result.append(entry)
    return result


__all__ = ["FragmentModifiers", "merge_fragments", "parse_modifiers"]
