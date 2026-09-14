"""Small option types shared by ``passes`` and ``core.conversion``.

Both packages need these: a pass reads them while walking the IR, and
``core.conversion`` reads front matter/template overrides into them. Keeping
them here — a leaf module under ``core`` with no dependency on
``core.conversion`` — lets a pass import them without reaching into the
orchestrator that runs the passes (``core.conversion.pipeline``/``typst``
import ``texsmith.passes`` at module level, so the reverse import would be
circular). ``core.conversion.inputs``/``settings`` re-export these names for
their existing callers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


DOCUMENT_SELECTOR_SENTINEL = "@document"

_EMOJI_SPECIAL_MODES = {"artifact", "symbola", "color", "black", "twemoji"}


@dataclass(slots=True, frozen=True)
class SlotOptions:
    """Per-slot rendering flags parsed from front matter."""

    flatten: bool = False


def coerce_emoji_mode(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    return lowered if lowered in _EMOJI_SPECIAL_MODES else candidate


def extract_emoji_mode(mapping: Mapping[str, Any] | None) -> str | None:
    """The resolved ``emoji`` mode: ``emoji``, ``fonts.emoji``, ``press.emoji``,
    ``press.fonts.emoji`` of ``mapping``, in that order.
    """
    if not isinstance(mapping, Mapping):
        return None
    direct = coerce_emoji_mode(mapping.get("emoji"))
    if direct:
        return direct
    fonts_section = mapping.get("fonts")
    if isinstance(fonts_section, Mapping):
        direct_fonts = coerce_emoji_mode(fonts_section.get("emoji"))
        if direct_fonts:
            return direct_fonts
    press = mapping.get("press")
    if isinstance(press, Mapping):
        press_direct = coerce_emoji_mode(press.get("emoji"))
        if press_direct:
            return press_direct
        press_fonts = press.get("fonts")
        if isinstance(press_fonts, Mapping):
            return coerce_emoji_mode(press_fonts.get("emoji"))
    return None


__all__ = [
    "DOCUMENT_SELECTOR_SENTINEL",
    "SlotOptions",
    "coerce_emoji_mode",
    "extract_emoji_mode",
]
