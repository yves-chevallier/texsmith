"""Utilities to collect Unicode characters from template payloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .matcher import FontMatchResult, match_text


def _collect_characters(payload: Any, *, seen: set[int]) -> set[str]:
    characters: set[str] = set()

    if isinstance(payload, str):
        characters.update(payload)
        return characters

    if isinstance(payload, Mapping):
        identifier = id(payload)
        if identifier in seen:
            return characters
        seen.add(identifier)
        for value in payload.values():
            characters.update(_collect_characters(value, seen=seen))
        return characters

    if isinstance(payload, Iterable) and not isinstance(payload, (bytes, bytearray, memoryview)):
        identifier = id(payload)
        if identifier in seen:
            return characters
        seen.add(identifier)
        for value in payload:
            characters.update(_collect_characters(value, seen=seen))
    return characters


def collate_character_set(*payloads: Any) -> str:
    """Return a compact string containing unique characters from nested payloads."""
    seen: set[int] = set()
    characters: set[str] = set()
    for payload in payloads:
        characters.update(_collect_characters(payload, seen=seen))
    return "".join(sorted(characters))


def analyse_font_requirements(
    *,
    slot_outputs: Mapping[str, str] | None,
    context: Mapping[str, Any] | None,
    fonts_yaml: Path | None = None,
    check_system: bool = True,
) -> FontMatchResult | None:
    """Inspect the slot output and context to determine the required fallback fonts."""
    character_source = collate_character_set(
        slot_outputs or {},
        context or {},
    )
    if not character_source:
        return None
    return match_text(
        character_source,
        fonts_yaml=fonts_yaml,
        check_system=check_system,
    )


__all__ = ["analyse_font_requirements", "collate_character_set"]
