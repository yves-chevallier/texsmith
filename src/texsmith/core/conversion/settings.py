"""How a document's ``emoji`` and ``code`` settings are resolved.

Both are read from several places — the template's attribute defaults, the
front matter, its ``fonts`` or ``press`` sections, the CLI overrides — and
both are needed by a pass as well as by the renderer. They live here so that
``passes/emoji.py`` stops importing a private name from the orchestrator it
runs under.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from texsmith.core.code_options import normalise_inline_options


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.templates import TemplateBinding


__all__ = ["coerce_emoji_mode", "extract_emoji_mode", "resolve_code_options"]


_EMOJI_SPECIAL_MODES = {"artifact", "symbola", "color", "black", "twemoji"}
_CODE_ENGINES = {"minted", "listings", "verbatim", "pygments"}


def coerce_emoji_mode(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    return lowered if lowered in _EMOJI_SPECIAL_MODES else candidate


def resolve_code_options(
    binding: TemplateBinding,
    overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the effective code configuration merging defaults and overrides."""
    default_options: dict[str, Any] = {}
    instance = binding.instance
    if instance is not None:
        try:
            defaults = instance.info.attribute_defaults()
        except Exception:
            defaults = {}
        code_default = defaults.get("code")
        if isinstance(code_default, Mapping):
            default_options.update(code_default)

    merged = dict(default_options)
    override_sources: list[Any] = []
    if overrides:
        if "code" in overrides:
            override_sources.append(overrides.get("code"))
        press_section = overrides.get("press")
        if (
            isinstance(press_section, Mapping)
            and "code" in press_section
            and "code" not in overrides
        ):
            override_sources.append(press_section.get("code"))

    for candidate in override_sources:
        if isinstance(candidate, Mapping):
            merged.update(candidate)
        elif isinstance(candidate, str):
            merged["engine"] = candidate

    engine_value = str(merged.get("engine", "pygments") or "pygments").strip().lower()
    merged["engine"] = engine_value if engine_value in _CODE_ENGINES else "pygments"
    style_value = merged.get("style", "bw")
    if isinstance(style_value, str):
        style_candidate = style_value.strip()
    else:
        style_candidate = str(style_value).strip() if style_value is not None else ""
    merged["style"] = style_candidate or "bw"
    merged["inline"] = normalise_inline_options(merged.get("inline"), default_options.get("inline"))
    return merged


def extract_emoji_mode(mapping: Mapping[str, Any] | None) -> str | None:
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
