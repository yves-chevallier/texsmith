"""How a document's ``code`` settings are resolved.

Read from several places — the template's attribute defaults, the front
matter, its ``press`` section, the CLI overrides. ``coerce_emoji_mode``/
``extract_emoji_mode`` moved to :mod:`texsmith.core.options` (a leaf module
``passes/emoji.py`` can import without reaching into this package, which
imports ``texsmith.passes`` at module level); re-exported here for existing
callers.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from texsmith.core.code_options import normalise_inline_options
from texsmith.core.options import coerce_emoji_mode, extract_emoji_mode


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.templates import TemplateBinding


__all__ = ["coerce_emoji_mode", "extract_emoji_mode", "resolve_code_options"]


_CODE_ENGINES = {"minted", "listings", "verbatim", "pygments"}


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
