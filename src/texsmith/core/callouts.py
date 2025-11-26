"""Built-in callout definitions and helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CalloutConfig = dict[str, Any]

DEFAULT_CALLOUTS: dict[str, CalloutConfig] = {
    "note": {"background_color": "ecf3ff", "border_color": "448aff", "icon": "📝"},
    "abstract": {"background_color": "e5f7ff", "border_color": "00b0ff", "icon": "📄"},
    "summary": {"background_color": "e5f8fb", "border_color": "00b8d4", "icon": "📋"},
    "info": {"background_color": "e5f8fb", "border_color": "00b8d4", "icon": "ℹ"},  # noqa: RUF001
    "tip": {"background_color": "e5f8f6", "border_color": "00bfa5", "icon": "⭐"},
    "success": {"background_color": "e5f9ed", "border_color": "00c853", "icon": "✅"},
    "question": {"background_color": "effce7", "border_color": "64dd17", "icon": "❓"},
    "warning": {"background_color": "fff1d6", "border_color": "ffb200", "icon": "⚠"},
    "caution": {"background_color": "fff8e1", "border_color": "ff9100", "icon": "🚧"},
    "failure": {"background_color": "ffeded", "border_color": "ff5252", "icon": "❗"},
    "danger": {"background_color": "ffe2e7", "border_color": "c62828", "icon": "🔥"},
    "important": {"background_color": "ffe0f0", "border_color": "d81b60", "icon": "❗"},
    "bug": {"background_color": "fee5ee", "border_color": "f50057", "icon": "🐞"},
    "example": {"background_color": "f2edff", "border_color": "7c4dff", "icon": "🧪"},
    "quote": {"background_color": "f5f5f5", "border_color": "9e9e9e", "icon": "✒️"},
    "hint": {"background_color": "e5f8f6", "border_color": "00bfa5", "icon": "💡"},
    "default": {"background_color": "f0f0f0", "border_color": "808080", "icon": "🎤"},
}


def _flatten_callouts(definitions: Mapping[str, Any]) -> dict[str, CalloutConfig]:
    """Flatten nested callout definitions declared under arbitrary keys."""
    flat: dict[str, CalloutConfig] = {}
    for name, cfg in definitions.items():
        if not isinstance(cfg, Mapping):
            continue
        if {"icon", "background_color", "border_color", "title_color"} & set(cfg):
            flat[name] = dict(cfg)
            continue
        nested = _flatten_callouts(cfg)
        for child_name, child_cfg in nested.items():
            flat[child_name] = child_cfg
    return flat


def merge_callouts(
    base: Mapping[str, CalloutConfig],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, CalloutConfig]:
    """Merge callout definitions with user-provided overrides."""
    combined: dict[str, CalloutConfig] = {
        key: dict(value) for key, value in _flatten_callouts(base).items()
    }
    if not overrides:
        return combined
    for key, cfg in _flatten_callouts(overrides).items():
        merged = dict(combined.get(key, {}))
        for name, value in cfg.items():
            if value is None:
                continue
            merged[name] = value
        combined[key] = merged
    return combined


def _normalise_color(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"{value:06X}"
    if isinstance(value, str):
        stripped = value.strip().lstrip("#").lstrip("0x").lstrip("0X")
        if not stripped:
            return None
        try:
            parsed = int(stripped, 16)
        except ValueError:
            return None
        return f"{parsed:06X}"
    return None


def normalise_callouts(definitions: Mapping[str, CalloutConfig]) -> dict[str, CalloutConfig]:
    """Return a copy of callouts with hex color strings normalised."""
    normalised: dict[str, CalloutConfig] = {}
    for name, cfg in definitions.items():
        if not isinstance(cfg, Mapping):
            continue
        updated: CalloutConfig = dict(cfg)
        for key in ("background_color", "border_color", "title_color"):
            colour = _normalise_color(updated.get(key))
            if colour:
                updated[key] = colour
        normalised[name] = updated
    return normalised


__all__ = ["DEFAULT_CALLOUTS", "CalloutConfig", "merge_callouts"]
