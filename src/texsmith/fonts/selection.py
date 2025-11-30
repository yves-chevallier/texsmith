"""Font profile resolution, configuration parsing, and fallback planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
import warnings

from pydantic import BaseModel, ConfigDict, ValidationError

from texsmith.fonts.cjk import CJK_SCRIPT_ROWS
from texsmith.fonts.constants import SCRIPT_FALLBACK_ALIASES
from texsmith.fonts.data import noto_dataset


_SCRIPT_LOOKUP: dict[str, tuple[Any, ...]] = {row[0]: row for row in noto_dataset.SCRIPT_FALLBACKS}
_SCRIPT_LOOKUP.update(CJK_SCRIPT_ROWS)
for alias, target in SCRIPT_FALLBACK_ALIASES.items():
    if target in _SCRIPT_LOOKUP and alias not in _SCRIPT_LOOKUP:
        _SCRIPT_LOOKUP[alias] = _SCRIPT_LOOKUP[target]

PROFILE_MAP: dict[str, dict[str, Any]] = {
    "default": {
        "main": "Latin Modern Roman",
        "sans": "Latin Modern Sans",
        "mono": "FreeMono",
        "math": "Latin Modern Math",
        "small_caps": "Latin Modern Roman Caps",
    },
    "sans": {
        "main": "Latin Modern Sans",
        "sans": "Latin Modern Sans",
        "mono": "IBM Plex Mono",
        "math": "Latin Modern Math",
        "small_caps": None,
    },
    "adventor": {
        "main": "TeX Gyre Adventor",
        "sans": "TeX Gyre Adventor",
        "mono": "IBM Plex Mono",
        "math": "TeX Gyre Pagella Math",
        "small_caps": None,
    },
    "heros": {
        "main": "TeX Gyre Heros",
        "sans": "TeX Gyre Heros",
        "mono": "IBM Plex Mono",
        "math": "TeX Gyre Pagella Math",
        "small_caps": None,
    },
    "noto": {
        "main": "Noto Serif",
        "sans": "Noto Sans",
        "mono": "Noto Sans Mono",
        "math": "Noto Sans Math",
        "small_caps": None,
        "mono_italic": "*",
        "mono_bold_italic": "* Bold",
        "mono_fake_slant": True,
    },
}


class FontFamilyOverrides(BaseModel):
    """Per-role overrides accepted in the font configuration."""

    model_config = ConfigDict(extra="forbid")

    main: str | None = None
    sans: str | None = None
    mono: str | None = None
    math: str | None = None
    small_caps: str | None = None
    sc: str | None = None

    def resolved(self) -> dict[str, str]:
        payload = {
            "main": self.main,
            "sans": self.sans,
            "mono": self.mono,
            "math": self.math,
            "small_caps": self.small_caps or self.sc,
        }
        return {key: value for key, value in payload.items() if value}


class FontsConfig(BaseModel):
    """Top-level configuration payload parsed from YAML/overrides."""

    model_config = ConfigDict(extra="allow")

    family: str | FontFamilyOverrides | None = None
    overrides: FontFamilyOverrides | None = None


@dataclass(frozen=True, slots=True)
class FontSelection:
    """Resolved font choices for the ts-fonts fragment."""

    profile: str
    main: str
    sans: str
    mono: str
    math: str
    small_caps: str | None
    mono_italic: str
    mono_bold_italic: str
    mono_fake_slant: bool
    script_fallbacks: dict[str, list[str]] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _parse_fonts_payload(raw: Any) -> FontsConfig | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return FontsConfig.model_validate({"family": raw})
    if isinstance(raw, Mapping):
        try:
            return FontsConfig.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover - defensive
            warnings.warn(f"Ignoring invalid fonts configuration: {exc}", stacklevel=3)
            return None
    warnings.warn(f"Unsupported fonts configuration type: {type(raw)!r}", stacklevel=3)
    return None


def _profile_defaults(name: str) -> dict[str, Any]:
    profile = PROFILE_MAP.get(name.lower())
    if profile:
        return dict(profile)
    return dict(PROFILE_MAP["default"])


def _apply_overrides(target: dict[str, Any], overrides: FontFamilyOverrides | None) -> None:
    if not overrides:
        return
    for key, value in overrides.resolved().items():
        target[key] = value


def _mono_variants(mono_font: str, profile_defaults: dict[str, Any]) -> tuple[str, str, bool]:
    mono_italic = profile_defaults.get("mono_italic")
    mono_bold_italic = profile_defaults.get("mono_bold_italic")
    mono_fake_slant = bool(profile_defaults.get("mono_fake_slant", False))

    if mono_italic is None:
        if mono_font == "FreeMono":
            mono_italic = "* Oblique"
            mono_bold_italic = "* Bold Oblique"
        else:
            mono_italic = "* Italic"
            mono_bold_italic = "* Bold Italic"
    elif mono_bold_italic is None:
        mono_bold_italic = mono_italic

    return mono_italic, mono_bold_italic or mono_italic, mono_fake_slant


def _merge_font_configs(
    document_config: FontsConfig | None, press_config: FontsConfig | None
) -> tuple[str, dict[str, Any]]:
    profile_name = "default"
    base: dict[str, Any] = _profile_defaults(profile_name)

    def update_profile(source: FontsConfig | None) -> None:
        nonlocal profile_name, base
        if source is None:
            return
        family = source.family
        if isinstance(family, str) and family.strip():
            profile_name = family.strip().lower()
            base = _profile_defaults(profile_name)
        elif isinstance(family, FontFamilyOverrides):
            _apply_overrides(base, family)

    update_profile(press_config)
    update_profile(document_config)

    _apply_overrides(base, getattr(press_config, "overrides", None))
    _apply_overrides(base, getattr(document_config, "overrides", None))

    return profile_name, base


def _fallback_for_script(script_id: str) -> str | None:
    entry = _SCRIPT_LOOKUP.get(script_id)
    if not entry:
        return None
    for candidate in entry[2:]:
        if candidate:
            return candidate
    return None


def _collect_script_fallbacks(script_usage: Any) -> tuple[dict[str, list[str]], list[str]]:
    fallbacks: dict[str, list[str]] = {}
    warnings_list: list[str] = []
    if not isinstance(script_usage, list):
        return fallbacks, warnings_list
    for entry in script_usage:
        if not isinstance(entry, Mapping):
            continue
        script_id = entry.get("script_id")
        if not isinstance(script_id, str):
            continue
        fallback_font = _fallback_for_script(script_id)
        if fallback_font:
            fallbacks.setdefault(script_id, [])
            if fallback_font not in fallbacks[script_id]:
                fallbacks[script_id].append(fallback_font)
        else:
            warnings_list.append(f"No fallback font registered for script '{script_id}'.")
    return fallbacks, warnings_list


def resolve_font_selection(
    context: Mapping[str, Any],
    *,
    script_usage: Any = None,
) -> FontSelection:
    """Resolve fonts configuration into concrete selections and fallbacks."""
    doc_config = _parse_fonts_payload(context.get("fonts"))
    press_fonts = None
    press = context.get("press")
    if isinstance(press, Mapping):
        press_fonts = _parse_fonts_payload(press.get("fonts"))

    profile_name, base_fonts = _merge_font_configs(doc_config, press_fonts)

    # Context-level overrides (legacy keys)
    for key in ("main", "sans", "mono", "math"):
        override = context.get(f"{key}_font")
        if isinstance(override, str) and override.strip():
            base_fonts[key] = override.strip()
    sc_override = context.get("small_caps_font")
    if isinstance(sc_override, str) and sc_override.strip():
        base_fonts["small_caps"] = sc_override.strip()

    mono_font = base_fonts.get("mono") or PROFILE_MAP["default"]["mono"]
    mono_italic, mono_bold_italic, mono_fake_slant = _mono_variants(mono_font, base_fonts)

    fallbacks, fallback_warnings = _collect_script_fallbacks(script_usage)

    selection = FontSelection(
        profile=profile_name,
        main=base_fonts.get("main") or PROFILE_MAP["default"]["main"],
        sans=base_fonts.get("sans") or PROFILE_MAP["default"]["sans"],
        mono=mono_font,
        math=base_fonts.get("math") or PROFILE_MAP["default"]["math"],
        small_caps=base_fonts.get("small_caps"),
        mono_italic=mono_italic,
        mono_bold_italic=mono_bold_italic,
        mono_fake_slant=mono_fake_slant,
        script_fallbacks=fallbacks,
        warnings=tuple(fallback_warnings),
    )
    return selection


__all__ = [
    "FontFamilyOverrides",
    "FontSelection",
    "FontsConfig",
    "resolve_font_selection",
]
