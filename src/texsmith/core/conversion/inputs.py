"""Slot selectors and input classification for the conversion pipeline.

The inline bibliography this module used to validate — 300 of its 469 lines —
lives in :mod:`texsmith.core.bibliography.inline`, which is where a reader
looks for it. ``DOCUMENT_SELECTOR_SENTINEL``/``SlotOptions`` moved to
:mod:`texsmith.core.options` (a leaf module ``passes/slots.py`` can import
without reaching into this package, which imports ``texsmith.passes`` at
module level); re-exported here for existing callers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from texsmith.core.coerce import coerce_bool
from texsmith.core.options import DOCUMENT_SELECTOR_SENTINEL, SlotOptions


class UnsupportedInputError(Exception):
    """Raised when a CLI input argument cannot be processed."""


def _coerce_bool_option(value: Any) -> bool:
    """A slot option is off unless it spells ``True``."""
    return coerce_bool(value) or False


def _extract_slot_options(payload: Any) -> SlotOptions:
    if isinstance(payload, Mapping):
        return SlotOptions(flatten=_coerce_bool_option(payload.get("flatten")))
    return SlotOptions()


def coerce_slot_selector(payload: Any) -> str | None:
    """Normalise a selector definition coming from front matter."""
    if isinstance(payload, str):
        candidate = payload.strip()
        return candidate or None
    if isinstance(payload, Mapping):
        for key in ("label", "title", "section"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def parse_slot_mapping(
    raw: Any,
) -> tuple[dict[str, str], dict[str, SlotOptions]]:
    """Parse slot mappings together with their per-slot options.

    Accepts the three front-matter shapes ``{name: selector}``,
    ``[{target/slot: ..., label: ...}]`` and the bare ``"name:selector"``
    string form. Returns a ``(selectors, options)`` tuple where ``options``
    only contains entries whose values differ from the ``SlotOptions``
    defaults, so callers can ignore it when they don't care.
    """
    overrides: dict[str, str] = {}
    options: dict[str, SlotOptions] = {}
    if not raw:
        return overrides, options

    def _record(name: str, selector: str, option_payload: Any) -> None:
        key = name.strip()
        if not key or not selector:
            return
        overrides[key] = selector
        slot_options = _extract_slot_options(option_payload)
        if slot_options != SlotOptions():
            options[key] = slot_options

    if isinstance(raw, Mapping):
        for slot_name, payload in raw.items():
            if not isinstance(slot_name, str):
                continue
            selector = coerce_slot_selector(payload)
            if selector:
                _record(slot_name, selector, payload)
        return overrides, options

    if isinstance(raw, Iterable) and not isinstance(raw, str | bytes):
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            slot_name = entry.get("target") or entry.get("slot")
            if not isinstance(slot_name, str):
                continue
            selector = entry.get("label") or entry.get("title") or entry.get("section")
            selector_value = coerce_slot_selector(selector)
            if not selector_value:
                selector_value = coerce_slot_selector(entry)
            if selector_value:
                _record(slot_name, selector_value, entry)
        return overrides, options

    if isinstance(raw, str):
        entry = raw.strip()
        if entry and ":" in entry:
            name, selector = entry.split(":", 1)
            selector = selector.strip()
            if selector:
                _record(name, selector, None)
        return overrides, options

    return overrides, options


def extract_front_matter_slots(
    front_matter: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, SlotOptions]]:
    """Return front-matter slot selectors alongside their per-slot options."""
    root_slots = front_matter.get("slots") or front_matter.get("entrypoints")
    return parse_slot_mapping(root_slots)


__all__ = [
    "DOCUMENT_SELECTOR_SENTINEL",
    "SlotOptions",
    "UnsupportedInputError",
    "coerce_slot_selector",
    "extract_front_matter_slots",
    "parse_slot_mapping",
]
