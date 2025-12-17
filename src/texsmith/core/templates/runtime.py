"""Runtime helpers for binding LaTeX templates to rendered documents."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import WrappableTemplate
from .loader import load_template
from .manifest import (
    DEFAULT_TEMPLATE_LANGUAGE,
    TemplateError,
    TemplateSlot,
    _BABEL_LANGUAGE_ALIASES,
)

from texsmith.core.fragments import FRAGMENT_REGISTRY

if TYPE_CHECKING:
    from texsmith.adapters.latex.formatter import LaTeXFormatter


@dataclass(slots=True)
class TemplateRuntime:
    """Resolved template metadata reused across conversions."""

    instance: WrappableTemplate
    name: str
    engine: str | None
    requires_shell_escape: bool
    slots: dict[str, TemplateSlot]
    default_slot: str
    formatter_overrides: dict[str, Path]
    base_level: int | None
    required_partials: set[str] = field(default_factory=set)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TemplateBinding:
    """Binding between slot requests and a LaTeX template."""

    runtime: TemplateRuntime | None
    instance: WrappableTemplate | None
    name: str | None
    engine: str | None
    requires_shell_escape: bool
    formatter_overrides: dict[str, Path]
    slots: dict[str, TemplateSlot]
    default_slot: str
    base_level: int | None
    required_partials: set[str] = field(default_factory=set)

    def slot_levels(self, *, offset: int = 0) -> dict[str, int]:
        """Return the resolved base level for each slot."""
        base = (self.base_level or 0) + offset
        return {name: slot.resolve_level(base) for name, slot in self.slots.items()}

    def apply_formatter_overrides(self, formatter: "LaTeXFormatter") -> None:
        """Apply template-provided overrides to a formatter."""
        for key, override_path in self.formatter_overrides.items():
            formatter.override_template(key, override_path)


def coerce_base_level(value: Any, *, allow_none: bool = True) -> int | None:
    """Normalise base-level metadata to an integer or ``None``."""
    if value is None:
        if allow_none:
            return None
        raise TemplateError("Base level value is missing.")

    if isinstance(value, bool):
        raise TemplateError("Base level must be an integer, booleans are not supported.")

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        candidate = value.strip().lower()
        if not candidate:
            if allow_none:
                return None
            raise TemplateError("Base level value cannot be empty.")
        alias_map = {
            "part": -1,
            "chapter": 0,
            "section": 1,
            "subsection": 2,
        }
        if candidate in alias_map:
            return alias_map[candidate]
        try:
            return int(candidate)
        except ValueError as exc:  # pragma: no cover - defensive
            raise TemplateError(
                f"Invalid base level '{value}'. Expected an integer value or one of "
                f"{', '.join(alias_map)}."
            ) from exc

    raise TemplateError(
        f"Base level should be provided as an integer value, got type '{type(value).__name__}'."
    )


def extract_base_level_override(overrides: Mapping[str, Any] | None) -> Any:
    """Extract a base level override from template metadata overrides."""
    if not overrides:
        return None

    press_section = overrides.get("press")
    direct_candidate = overrides.get("base_level")
    if direct_candidate is not None:
        return direct_candidate
    if isinstance(press_section, Mapping):
        return press_section.get("base_level")
    return None


def build_template_overrides(front_matter: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build template overrides from front matter while preserving metadata."""
    if not front_matter or not isinstance(front_matter, Mapping):
        return {}

    overrides = dict(front_matter)
    press_section = overrides.get("press")
    if isinstance(press_section, Mapping):
        overrides["press"] = dict(press_section)

    fragments = overrides.get("fragments")
    if fragments is None and isinstance(press_section, Mapping):
        fragments = press_section.get("fragments")
    if isinstance(fragments, list):
        overrides["fragments"] = list(fragments)

    callouts_section = overrides.get("callouts")
    if callouts_section is None and isinstance(press_section, Mapping):
        callouts_section = press_section.get("callouts")
    if isinstance(callouts_section, Mapping):
        overrides["callouts"] = dict(callouts_section)

    callouts_style = overrides.get("callouts_style")
    if callouts_style is None and isinstance(press_section, Mapping):
        callouts_style = press_section.get("callouts_style")
    if callouts_style is not None:
        overrides["callout_style"] = callouts_style

    base_override = overrides.get("base_level")
    if base_override is None and isinstance(press_section, Mapping):
        base_override = press_section.get("base_level")
    if base_override is not None:
        try:
            overrides["base_level"] = coerce_base_level(base_override)
        except TemplateError:
            overrides["base_level"] = base_override

    return overrides


def extract_language_from_front_matter(
    front_matter: Mapping[str, Any] | None,
) -> str | None:
    """Inspect front matter for language hints."""
    if not isinstance(front_matter, Mapping):
        return None

    for key in ("language", "lang"):
        value = front_matter.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped

    press_entry = front_matter.get("press")
    if isinstance(press_entry, Mapping):
        for key in ("language", "lang"):
            value = press_entry.get(key)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
    return None


def normalise_template_language(value: str | None) -> str | None:
    """Normalise language codes and map them through babel aliases when available."""
    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    lowered = stripped.lower().replace("_", "-")
    alias = _BABEL_LANGUAGE_ALIASES.get(lowered)
    if alias:
        return alias

    primary = lowered.split("-", 1)[0]
    alias = _BABEL_LANGUAGE_ALIASES.get(primary)
    if alias:
        return alias

    if lowered.isalpha():
        return lowered

    return None


def resolve_template_language(
    explicit: str | None,
    front_matter: Mapping[str, Any] | None,
) -> str:
    """Resolve the effective template language from CLI and front matter inputs."""
    candidates = (
        normalise_template_language(explicit),
        normalise_template_language(extract_language_from_front_matter(front_matter)),
    )

    for candidate in candidates:
        if candidate:
            return candidate

    return DEFAULT_TEMPLATE_LANGUAGE


def load_template_runtime(template: str) -> TemplateRuntime:
    """Resolve template metadata for repeated conversions."""
    template_instance = load_template(template)

    template_base = coerce_base_level(
        template_instance.info.get_attribute_default("base_level"),
    )

    slots, default_slot = template_instance.info.resolve_slots()
    formatter_overrides = dict(template_instance.iter_formatter_overrides())
    extras_payload = getattr(template_instance, "extras", {}) or {}
    extras = {key: value for key, value in extras_payload.items()}
    declared_fragments = (
        list(template_instance.info.fragments) if template_instance.info.fragments is not None else None
    )
    extras.setdefault(
        "fragments",
        declared_fragments if declared_fragments is not None else [],
    )

    return TemplateRuntime(
        instance=template_instance,
        name=template_instance.info.name,
        engine=template_instance.info.engine,
        requires_shell_escape=bool(template_instance.info.shell_escape),
        slots=slots,
        default_slot=default_slot,
        formatter_overrides=formatter_overrides,
        base_level=template_base,
        required_partials=set(template_instance.info.required_partials or []),
        extras=extras,
    )


def resolve_template_binding(
    *,
    template: str | None,
    template_runtime: TemplateRuntime | None,
    template_overrides: Mapping[str, Any],
    slot_requests: Mapping[str, str],
    warn: Callable[[str], None] | None = None,
) -> tuple[TemplateBinding, dict[str, str]]:
    """Resolve template runtime metadata and apply slot overrides."""
    runtime = template_runtime
    if runtime is None and template:
        runtime = load_template_runtime(template)

    if runtime is not None:
        # Adjust base level for book parts when requested via overrides.
        binding_base_level = runtime.base_level
        part_flag = None
        press_section = template_overrides.get("press")
        if isinstance(template_overrides.get("part"), bool):
            part_flag = template_overrides.get("part")
        elif isinstance(press_section, Mapping) and isinstance(press_section.get("part"), bool):
            part_flag = press_section.get("part")
        if part_flag and runtime.name == "book":
            binding_base_level = coerce_base_level("part")

        binding = TemplateBinding(
            runtime=runtime,
            instance=runtime.instance,
            name=runtime.name,
            engine=runtime.engine,
            requires_shell_escape=runtime.requires_shell_escape,
            formatter_overrides=dict(runtime.formatter_overrides),
            slots=runtime.slots,
            default_slot=runtime.default_slot,
            base_level=binding_base_level,
            required_partials=set(runtime.required_partials),
        )
    else:
        binding = TemplateBinding(
            runtime=None,
            instance=None,
            name=None,
            engine=None,
            requires_shell_escape=False,
            formatter_overrides={},
            slots={"mainmatter": TemplateSlot(default=True)},
            default_slot="mainmatter",
            base_level=None,
            required_partials=set(),
        )

    base_override = coerce_base_level(extract_base_level_override(template_overrides))
    if base_override is not None:
        binding.base_level = base_override

    filtered: dict[str, str] = {}
    for slot_name, selector in slot_requests.items():
        if slot_name not in binding.slots:
            if warn is not None:
                template_hint = f"template '{binding.name}'" if binding.name else "the template"
                warn(
                    f"slot '{slot_name}' is not defined by {template_hint}; "
                    f"content will remain in '{binding.default_slot}'."
                )
            continue
        if binding.runtime is None:
            if warn is not None:
                warn(f"slot '{slot_name}' was requested but no template is selected; ignoring.")
            continue
        filtered[slot_name] = selector

    return binding, filtered


__all__ = [
    "TemplateBinding",
    "TemplateRuntime",
    "build_template_overrides",
    "coerce_base_level",
    "extract_base_level_override",
    "extract_language_from_front_matter",
    "load_template_runtime",
    "normalise_template_language",
    "resolve_template_binding",
    "resolve_template_language",
]
