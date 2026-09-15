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

from collections.abc import Iterable, Mapping, Sequence
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


# Activation from a writer's ``Requires`` (fragment-contracts.md §2)

#: Context key carrying the fragments activated from ``Requires``. When it is
#: present, a contract fragment renders iff its name is listed; when it is
#: absent (the legacy Jinja path) the fragments keep their content sniffers.
ACTIVE_FRAGMENTS_KEY = "ts_active_fragments"

#: Context key carrying the packages ``ts-extra`` must load on the contract
#: path: ``Requires.packages`` merged with the packages implied by the active
#: rows.
REQUIRES_PACKAGES_KEY = "ts_requires_packages"

#: Fragments that are configuration, not contracts: always active.
_ALWAYS_ACTIVE = ("ts-fonts", "ts-extra")


def _clean_strings(values: Any) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        return [values]
    if isinstance(values, Mapping):
        return [str(key) for key in values]
    try:
        return [str(item) for item in values if item is not None]
    except TypeError:
        return []


def activate_from_requires(
    requires: Mapping[str, Any] | None,
    *,
    front_matter: Mapping[str, Any] | None = None,
) -> set[str]:
    """Map a writer's ``Requires`` onto the set of active fragments.

    Implements the activation table of ``fragment-contracts.md`` §2:

    - every row of ``FRAGMENTS`` named in ``requires["fragments"]``;
    - ``ts-index`` when ``requires["index"]`` lists a registry;
    - ``ts-bibliography`` when ``requires["bibliography"]`` is set or a
      citation was recorded;
    - ``ts-glossary`` when the writer emitted an acronym, or the front matter
      declares ``glossary`` / ``acronyms``;
    - ``ts-fonts`` and ``ts-extra`` always (configuration, not contracts).

    ``ts-geometry`` and ``ts-frame`` stay governed by their own configuration
    and are not part of the result.
    """
    payload: Mapping[str, Any] = requires or {}
    active: set[str] = set(_clean_strings(payload.get("fragments")))
    if _clean_strings(payload.get("index")):
        active.add("ts-index")
    if bool(payload.get("bibliography")) or _clean_strings(payload.get("citations")):
        active.add("ts-bibliography")
    if _clean_strings(payload.get("acronyms")):
        active.add("ts-glossary")
    if front_matter:
        press = front_matter.get("press")
        sections: list[Mapping[str, Any]] = [front_matter]
        if isinstance(press, Mapping):
            sections.append(press)
        for section in sections:
            if section.get("glossary") or section.get("acronyms"):
                active.add("ts-glossary")
                break
    active.update(_ALWAYS_ACTIVE)
    return active


def extra_packages_from_requires(
    requires: Mapping[str, Any] | None,
    active: Iterable[str] | None = None,
) -> list[str]:
    """What ``ts-extra`` must load: the packages the bodies named, less the ones
    an active contract already loads.

    A contract row declares the packages its ``.sty`` loads, and
    :data:`~texsmith.core.fragments.contracts.FRAGMENT_OWNED_PACKAGES` names
    the ones a fragment loads conditionally, which the table cannot express
    (``minted`` or ``listings`` depending on the engine). Either way
    ``ts-extra`` must stay out of it: the fragment loads them with options
    ``ts-extra`` does not know, and loading a package twice with different
    options is an option clash.

    The order is the writer's.
    """
    from texsmith.core.fragments.contracts import FRAGMENT_OWNED_PACKAGES, implied_packages

    payload: Mapping[str, Any] = requires or {}
    names = set(active) if active is not None else activate_from_requires(payload)
    provided = set(implied_packages(names)) | FRAGMENT_OWNED_PACKAGES
    ordered: dict[str, None] = {}
    for package in _clean_strings(payload.get("packages")):
        if package not in provided:
            ordered.setdefault(package, None)
    return list(ordered)


def contract_active(context: Mapping[str, Any], name: str) -> bool | None:
    """Whether ``name`` was activated from ``Requires`` in ``context``.

    Returns ``None`` when the context carries no activation set, so a fragment
    can fall back to its legacy detection.
    """
    active = context.get(ACTIVE_FRAGMENTS_KEY)
    if active is None:
        return None
    if isinstance(active, str):
        return active == name
    try:
        return name in set(active)
    except TypeError:
        return None


def inject_requires(
    context: dict[str, Any],
    requires: Mapping[str, Any] | None,
    *,
    front_matter: Mapping[str, Any] | None = None,
) -> set[str]:
    """Populate ``context`` with the activation set and the package list.

    Returns the active fragment names. The caller (the tmark reader path)
    still decides which fragments the template lists; this only settles
    which of the contract rows render and what ``ts-extra`` loads.
    """
    active = activate_from_requires(requires, front_matter=front_matter)
    context[ACTIVE_FRAGMENTS_KEY] = sorted(active)
    context[REQUIRES_PACKAGES_KEY] = extra_packages_from_requires(requires, active)
    payload: Mapping[str, Any] = requires or {}
    registries = [name for name in _clean_strings(payload.get("index")) if name]
    context.setdefault("index_registries", registries)
    if payload.get("shell_escape"):
        context["requires_shell_escape"] = True
    return active


__all__ = [
    "ACTIVE_FRAGMENTS_KEY",
    "REQUIRES_PACKAGES_KEY",
    "FragmentModifiers",
    "activate_from_requires",
    "contract_active",
    "extra_packages_from_requires",
    "inject_requires",
    "merge_fragments",
    "parse_modifiers",
]
