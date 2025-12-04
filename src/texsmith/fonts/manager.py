"""Coordinate font selection, fallback ranges, and file copying."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from texsmith.fonts import locator as fonts_locator
from texsmith.fonts.blocks import environment_name as script_environment_name
from texsmith.fonts.cache import cache_fonts_for_families
from texsmith.fonts.cjk import CJK_SCRIPT_ROWS
from texsmith.fonts.constants import SCRIPT_FALLBACK_ALIASES
from texsmith.fonts.data import noto_dataset
from texsmith.fonts.emoji import EmojiPayload, resolve_emoji_preferences
from texsmith.fonts.fallback import NotoFallback
from texsmith.fonts.locator import FontFiles, FontLocator
from texsmith.fonts.matcher import FontMatchResult
from texsmith.fonts.selection import FontSelection, resolve_font_selection
from texsmith.fonts.utils import sanitize_script_id, unicode_class_ranges


if TYPE_CHECKING:
    from texsmith.core.diagnostics import DiagnosticEmitter


DEFAULT_FALLBACK_FONTS: list[str] = ["NotoSans"]
_SCRIPT_LOOKUP = {row[0]: row for row in noto_dataset.SCRIPT_FALLBACKS}
_SCRIPT_LOOKUP.update(CJK_SCRIPT_ROWS)
for alias, target in SCRIPT_FALLBACK_ALIASES.items():
    if target in _SCRIPT_LOOKUP and alias not in _SCRIPT_LOOKUP:
        _SCRIPT_LOOKUP[alias] = _SCRIPT_LOOKUP[target]


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _apply_twemoji_fallback(
    template_context: dict[str, Any],
    fallback_fonts: list[str],
    *,
    missing_font: str,
    emitter: DiagnosticEmitter | None,
) -> list[str]:
    if emitter:
        emitter.warning(
            f"Emoji font '{missing_font}' unavailable; falling back to twemoji SVG images."
        )
    template_context["emoji_mode"] = "artifact"
    template_context["emoji"] = "artifact"
    return [font for font in fallback_fonts if font != missing_font]


def _is_noto_font(family: str | None) -> bool:
    """Return True if the family appears to be part of the Noto collection."""
    if not family:
        return False
    return family.lower().startswith("noto")


@dataclass(slots=True)
class PreparedFonts:
    """Result of preparing font files and ranges for ts-fonts."""

    selection: FontSelection
    fallback_fonts: list[str]
    present_fonts: list[str]
    missing_fonts: list[str]
    font_ranges: dict[str, list[str]]
    copied_fonts: dict[str, dict[str, str]]
    unicode_classes: list[dict[str, Any]]
    script_fallbacks: list[dict[str, Any]]
    fonts_dir: Path


@dataclass(frozen=True, slots=True)
class _LocatorCacheKey:
    fonts_yaml: Path | None
    mtime_ns: int
    size: int
    skip_checks: bool
    run_available: bool


_LOCATOR_CACHE: dict[_LocatorCacheKey, FontLocator] = {}


def _locator_cache_key(fonts_yaml: Path | None) -> _LocatorCacheKey:
    skip_checks = bool(os.environ.get("TEXSMITH_SKIP_FONT_CHECKS"))
    run_available = fonts_locator.subprocess_run_available()
    if fonts_yaml is None:
        return _LocatorCacheKey(None, 0, 0, skip_checks, run_available)

    resolved = fonts_yaml.expanduser().resolve()
    try:
        stat = resolved.stat()
        mtime_ns = stat.st_mtime_ns
        size = stat.st_size
    except OSError:
        mtime_ns = -1
        size = -1
    return _LocatorCacheKey(resolved, mtime_ns, size, skip_checks, run_available)


def _cached_locator(fonts_yaml: Path | None) -> FontLocator:
    key = _locator_cache_key(fonts_yaml)
    locator = _LOCATOR_CACHE.get(key)
    if locator is not None:
        return locator

    locator = FontLocator(fonts_yaml=fonts_yaml)
    _LOCATOR_CACHE[key] = locator
    return locator


def _serialize_copied_fonts(
    copied: dict[str, FontFiles], base_dir: Path
) -> dict[str, dict[str, str]]:
    serialised: dict[str, dict[str, str]] = {}
    for family, files in copied.items():
        rel = files.relative_to(base_dir)
        entries = {}
        for key, value in rel.available().items():
            entries[key] = value.name
        if entries:
            serialised[family] = entries
    return serialised


def _build_unicode_classes(
    font_ranges: Mapping[str, list[str]],
    copied_fonts: Mapping[str, dict[str, str]],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    counter = 1
    for family, ranges in sorted(font_ranges.items()):
        if family == "__UNCOVERED__" or not ranges:
            continue
        files = copied_fonts.get(family)
        if not files:
            continue
        specs.append(
            {
                "class_name": f"TSUnicodeClass{counter}",
                "font_command": f"TSUnicodeFont{counter}",
                "family": family,
                "ranges": unicode_class_ranges(ranges),
                "files": files,
            }
        )
        counter += 1
    return specs


def _build_script_fallbacks(
    script_blocks: Mapping[str, tuple[str, ...]],
    copied_fonts: Mapping[str, dict[str, str]],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []

    for script_id in sorted(script_blocks.keys()):
        script_row = _SCRIPT_LOOKUP.get(script_id)
        if not script_row:
            continue
        family = script_row[2]
        if not family:
            continue
        language = script_id.replace("-", "").replace("_", "")
        env_name = script_environment_name(language)
        files = copied_fonts.get(family)
        if not files:
            continue
        specs.append(
            {
                "script_id": script_id,
                "title": script_row[1],
                "family": family,
                "blocks": sorted(script_blocks[script_id]),
                "font_command": f"TSFallback{sanitize_script_id(script_id)}",
                "files": files,
                "language": language,
                "environment_name": env_name,
            }
        )
    return specs


def prepare_fonts_for_context(
    *,
    template_context: dict[str, Any],
    output_dir: Path,
    font_match: FontMatchResult | None,
    emitter: DiagnosticEmitter | None = None,
    font_locator: FontLocator | None = None,
) -> PreparedFonts | None:
    """
    Mutate the template context with resolved font settings and assets.

    Returns a :class:`PreparedFonts` summary to help callers with telemetry.
    """
    selection = resolve_font_selection(
        template_context,
        script_usage=template_context.get("_script_usage"),
    )
    template_context.setdefault("font_profile", selection.profile)
    template_context.setdefault("main_font", selection.main)
    template_context.setdefault("sans_font", selection.sans)
    template_context.setdefault("mono_font", selection.mono)
    template_context.setdefault("math_font", selection.math)
    if selection.small_caps:
        template_context.setdefault("small_caps_font", selection.small_caps)
    template_context.setdefault("mono_italic", selection.mono_italic)
    template_context.setdefault("mono_bold_italic", selection.mono_bold_italic)
    template_context.setdefault("mono_fake_slant", selection.mono_fake_slant)

    locator = font_locator or _cached_locator(font_match.fonts_yaml if font_match else None)

    font_ranges = dict(font_match.font_ranges) if font_match else {}
    present_fonts = list(font_match.present_fonts) if font_match else []
    missing_fonts = list(font_match.missing_fonts) if font_match else []

    engine_hint = (
        str(
            template_context.get("_texsmith_latex_engine")
            or os.environ.get("TEXSMITH_SELECTED_ENGINE")
            or template_context.get("latex_engine")
            or ""
        )
        .strip()
        .lower()
    )

    fonts_dir = (output_dir / "fonts").resolve()

    emoji_payload = resolve_emoji_preferences(
        template_context,
        engine=engine_hint,
        fonts_dir=fonts_dir,
        emitter=emitter,
    )
    if emoji_payload.warnings and emitter:
        for message in emoji_payload.warnings:
            emitter.warning(message)
    emoji_font_family = emoji_payload.font_family
    emoji_font_path = None
    if emoji_payload.font_path:
        try:
            emoji_font_path = emoji_payload.font_path.relative_to(output_dir).as_posix()
        except ValueError:
            emoji_font_path = emoji_payload.font_path.as_posix()
    template_context["_texsmith_effective_emoji_mode"] = emoji_payload.mode
    template_context["emoji_mode"] = emoji_payload.mode
    template_context["emoji"] = emoji_payload.mode
    template_context["emoji_spec"] = {
        "mode": emoji_payload.mode,
        "font_family": emoji_font_family,
        "font_path": emoji_font_path,
        "color_enabled": emoji_payload.color_enabled,
    }

    base_fallbacks: list[str] = []
    if font_match:
        available_fonts = list(font_match.present_fonts) or list(font_match.fallback_fonts)
        base_fallbacks.extend(available_fonts)
        extra_fallbacks = template_context.get("extra_font_fallbacks") or []
        if isinstance(extra_fallbacks, (list, tuple, set)):
            base_fallbacks.extend(str(item) for item in extra_fallbacks if item)
    if not base_fallbacks:
        base_fallbacks.extend(DEFAULT_FALLBACK_FONTS)

    fallback_fonts = _dedupe_preserve_order(base_fallbacks)
    if emoji_font_family and emoji_font_family not in fallback_fonts:
        fallback_fonts = [emoji_font_family, *fallback_fonts]
    fallback_fonts = _dedupe_preserve_order(fallback_fonts)
    script_font_set: set[str] = {
        family for families in selection.script_fallbacks.values() for family in families
    }
    template_context["fallback_fonts"] = fallback_fonts
    template_context.setdefault("font_match_ranges", font_ranges)
    template_context.setdefault("present_fonts", present_fonts)
    template_context.setdefault("missing_fonts", missing_fonts)

    fonts_dir = (output_dir / "fonts").resolve()
    fonts_to_copy: set[str] = set()
    if emoji_font_family:
        fonts_to_copy.add(emoji_font_family)

    def _maybe_copy(font: str | None) -> None:
        if _is_noto_font(font):
            fonts_to_copy.add(str(font))

    for candidate in (
        selection.main,
        selection.sans,
        selection.mono,
        selection.math,
        selection.small_caps,
        *fallback_fonts,
        *script_font_set,
    ):
        _maybe_copy(candidate)

    cached_fonts, cache_failures = cache_fonts_for_families(list(fonts_to_copy), emitter=emitter)
    for family, cached_entry in cached_fonts.items():
        if isinstance(cached_entry, Mapping):
            for style, path in cached_entry.items():
                locator.register_font_file(
                    family, path, style=str(style) if isinstance(style, str) else None
                )
        else:
            locator.register_font_file(family, cached_entry)

    copied = locator.copy_families(fonts_to_copy, fonts_dir)
    copied_serialised = _serialize_copied_fonts(copied, output_dir)
    fonts_path_prefix = f"./{fonts_dir.relative_to(output_dir).as_posix()}/"
    template_context["font_path_prefix"] = fonts_path_prefix
    template_context["font_files"] = copied_serialised

    missing_after_copy = {family for family in fonts_to_copy if family not in copied_serialised} | (
        set(cache_failures) & set(fonts_to_copy)
    )

    small_caps_font = template_context.get("small_caps_font")
    if small_caps_font and small_caps_font in missing_after_copy:
        # Drop unavailable small-caps selection so templates don't reference a missing family.
        template_context["small_caps_font"] = None

    available_families = set(copied_serialised.keys())
    if emoji_font_family and emoji_font_family in missing_after_copy:
        fallback_fonts = _apply_twemoji_fallback(
            template_context, fallback_fonts, missing_font=emoji_font_family, emitter=emitter
        )
        missing_after_copy.discard(emoji_font_family)
        emoji_font_family = None
        template_context["emoji_spec"] = {
            "mode": template_context["emoji_mode"],
            "font_family": None,
            "font_path": None,
            "color_enabled": False,
        }

    template_context["fallback_fonts"] = fallback_fonts

    filtered_font_ranges = {
        family: ranges
        for family, ranges in font_ranges.items()
        if family == "__UNCOVERED__" or family in available_families
    }
    if emoji_font_family:
        filtered_font_ranges["NotoColorEmoji"] = list(_EMOJI_DEFAULT_RANGES)
        template_context["emoji_ranges"] = unicode_class_ranges(_EMOJI_DEFAULT_RANGES)
    template_context["font_match_ranges"] = filtered_font_ranges

    if missing_after_copy:
        missing_fonts = _dedupe_preserve_order([*missing_fonts, *missing_after_copy])

    if emitter and missing_after_copy:
        readable = ", ".join(sorted(missing_after_copy))
        emitter.warning(f"Unable to copy {len(missing_after_copy)} font families: {readable}")

    unicode_classes = _build_unicode_classes(filtered_font_ranges, copied_serialised)
    template_context["unicode_font_classes"] = unicode_classes

    script_fallbacks = _build_script_fallbacks(
        font_match.script_blocks if font_match else {},
        copied_serialised,
    )
    template_context["script_fallbacks"] = script_fallbacks
    if script_fallbacks:
        uchar_options = sorted({block for entry in script_fallbacks for block in entry["blocks"]})
        template_context["ucharclasses_options"] = uchar_options

    return PreparedFonts(
        selection=selection,
        fallback_fonts=fallback_fonts,
        present_fonts=present_fonts,
        missing_fonts=missing_fonts,
        font_ranges=filtered_font_ranges,
        copied_fonts=copied_serialised,
        unicode_classes=unicode_classes,
        script_fallbacks=script_fallbacks,
        fonts_dir=fonts_dir,
    )


__all__ = [
    "DEFAULT_FALLBACK_FONTS",
    "FontSelection",
    "PreparedFonts",
    "prepare_fonts_for_context",
    "resolve_font_selection",
]
_EMOJI_DEFAULT_RANGES: tuple[str, ...] = (
    "2000..27FF",  # symbols, dingbats, arrows, punctuation
    "FE00..FE0F",  # variation selectors
    "1F000..1FAFF",  # emoji blocks
)
