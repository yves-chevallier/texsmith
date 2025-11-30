"""Emoji font resolution and engine compatibility handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from texsmith.fonts.cache import ensure_font, materialize_font
from texsmith.fonts.registry import FontSourceSpec, sources_for_family


_BLACK_MODES = {"black", "openmoji-black", "openmoji black"}
_COLOR_MODES = {
    "color",
    "colour",
    "openmoji-color",
    "openmoji color",
    "noto color emoji",
}
_LEGACY_DISABLE = {"artifact", "off", "none"}


@dataclass(frozen=True, slots=True)
class EmojiPayload:
    """Outcome of resolving emoji preferences."""

    mode: str
    font_family: str | None
    font_path: Path | None
    color_enabled: bool
    warnings: tuple[str, ...] = ()


def _collect_candidate(
    context: Mapping[str, Any],
) -> tuple[str, str | None]:
    press = context.get("press")
    press_fonts = press.get("fonts") if isinstance(press, Mapping) else None
    fonts_map = context.get("fonts") if isinstance(context.get("fonts"), Mapping) else None
    runtime_mode = context.get("emoji_mode") if isinstance(context.get("emoji_mode"), str) else None
    emoji_pref = context.get("emoji") if isinstance(context.get("emoji"), str) else None
    if emoji_pref is None and isinstance(press_fonts, Mapping):
        value = press_fonts.get("emoji")
        emoji_pref = value if isinstance(value, str) else None
    if emoji_pref is None and runtime_mode:
        emoji_pref = runtime_mode
    elif emoji_pref is None and isinstance(fonts_map, Mapping):
        value = fonts_map.get("emoji")
        emoji_pref = value if isinstance(value, str) else None
    candidate = (emoji_pref or "black").strip().lower() or "black"
    return candidate, emoji_pref


def _preferred_family(mode: str, raw_pref: str | None) -> tuple[str | None, bool]:
    if mode in _BLACK_MODES or mode == "black":
        return "OpenMoji Black", False
    if mode in _COLOR_MODES or mode == "color":
        return "Noto Color Emoji", True
    if mode not in _LEGACY_DISABLE and mode != "twemoji" and raw_pref:
        return raw_pref, mode in _COLOR_MODES
    return None, False


def _materialize_family(
    family: str,
    *,
    fonts_dir: Path,
    emitter: Any = None,
) -> Path | None:
    specs = sources_for_family(family)
    if not specs:
        return None
    spec: FontSourceSpec = next((entry for entry in specs if entry.style == "regular"), specs[0])
    record = ensure_font(spec, emitter=emitter)
    if record is None:
        return None
    return materialize_font(record, build_dir=fonts_dir, prefer_symlink=False)


def resolve_emoji_preferences(
    context: Mapping[str, Any],
    *,
    engine: str | None,
    fonts_dir: Path,
    emitter: Any = None,
) -> EmojiPayload:
    """Return the final emoji mode and font details."""
    normalized_mode, raw_pref = _collect_candidate(context)
    warnings: list[str] = []

    engine_normalized = (engine or "").strip().lower()
    family, wants_color = _preferred_family(normalized_mode, raw_pref)
    color_enabled = wants_color and engine_normalized == "lualatex"
    mode = normalized_mode

    if wants_color and not color_enabled:
        warnings.append("Color emoji unsupported on this engine; falling back to monochrome.")
        mode = "black"
        family = "OpenMoji Black"
        color_enabled = False

    if mode in _LEGACY_DISABLE or mode == "twemoji":
        return EmojiPayload(
            mode="artifact" if mode == "twemoji" else mode,
            font_family=None,
            font_path=None,
            color_enabled=False,
            warnings=tuple(warnings),
        )

    font_path = None
    if family:
        materialized = _materialize_family(family, fonts_dir=fonts_dir, emitter=emitter)
        if materialized is None:
            warnings.append(f"Unable to download emoji font '{family}'.")
        else:
            font_path = materialized

    payload_mode = mode if family else "artifact"
    if family is None:
        warnings.append("No emoji font selected; emojis may render as boxes.")
    return EmojiPayload(
        mode=payload_mode,
        font_family=family,
        font_path=font_path,
        color_enabled=color_enabled,
        warnings=tuple(warnings),
    )


__all__ = ["EmojiPayload", "resolve_emoji_preferences"]
