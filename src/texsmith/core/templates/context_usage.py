"""Helpers to introspect template context emitters and consumers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from jinja2 import meta

from texsmith.core.fragments import FRAGMENT_REGISTRY, FragmentDefinition
from texsmith.core.templates.base import WrappableTemplate, _build_environment


def _format_value_preview(value: Any, *, limit: int = 60) -> str:
    """Return a compact string representation suitable for tables."""

    try:
        rendered = repr(value)
    except Exception:  # pragma: no cover - defensive
        rendered = "<unrenderable>"

    if len(rendered) > limit:
        return rendered[: limit - 1] + "\u2026"
    return rendered


def _discover_template_variables(template: WrappableTemplate) -> set[str]:
    """Return undeclared variables referenced by the template entrypoint."""

    env = template.environment
    try:
        source, _, _ = env.loader.get_source(env, template.info.entrypoint)
    except Exception:
        return set()
    parsed = env.parse(source)
    return set(meta.find_undeclared_variables(parsed))


def _discover_fragment_variables(fragment: Any) -> set[str]:
    """Return undeclared variables referenced by a fragment's pieces."""

    variables: set[str] = set()
    pieces = getattr(fragment, "pieces", None) or []
    for piece in pieces:
        env = _build_environment(piece.template_path.parent)
        try:
            source, _, _ = env.loader.get_source(env, piece.template_path.name)
        except Exception:
            continue
        parsed = env.parse(source)
        variables.update(meta.find_undeclared_variables(parsed))
    return variables


def summarise_context_usage(
    template: WrappableTemplate,
    template_context: Mapping[str, Any],
    *,
    fragment_names: Sequence[str] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return a summary of context attributes with emitters/consumers."""

    fragment_names = fragment_names or []
    emitter_map: dict[str, set[str]] = defaultdict(set)
    consumer_map: dict[str, set[str]] = defaultdict(set)

    # Template-declared attributes and emitted helpers.
    template_name = template.info.name
    for name, spec in getattr(template.info, "attributes", {}).items():
        owner = getattr(spec, "owner", None) or template_name
        emitter_map[name].add(f"template:{owner} (attribute)")
    for key in getattr(template.info, "emit", {}) or {}:
        emitter_map[key].add(f"template:{template_name} (emit)")

    # Fragment-provided attributes and context defaults.
    for fragment_name in fragment_names:
        try:
            fragment = FRAGMENT_REGISTRY.resolve(fragment_name)
        except Exception:
            continue

        if isinstance(fragment, FragmentDefinition):
            attributes = fragment.attributes
            context_defaults = fragment.context_defaults
        else:
            attributes = FRAGMENT_REGISTRY.attributes_for(fragment.name)
            context_defaults = getattr(fragment, "context_defaults", {}) or {}

        for attr_name, spec in attributes.items():
            owner = getattr(spec, "owner", None) or fragment.name
            emitter_map[attr_name].add(f"fragment:{owner} (attribute)")
        for key in context_defaults:
            emitter_map[key].add(f"fragment:{fragment.name} (context)")

        for variable in _discover_fragment_variables(fragment):
            if variable:
                consumer_map[variable].add(f"fragment:{fragment.name}")

    # Track which attributes were supplied via overrides.
    if overrides:
        press_section = overrides.get("press") if isinstance(overrides, Mapping) else None
        for key in template_context.keys():
            direct_override = key in overrides if isinstance(overrides, Mapping) else False
            press_override = bool(isinstance(press_section, Mapping) and key in press_section)
            if direct_override or press_override:
                emitter_map[key].add("override")

    # Anything injected by the pipeline without a declared owner.
    for key in template_context.keys():
        if key not in emitter_map:
            emitter_map[key].add("pipeline")

    for variable in _discover_template_variables(template):
        if variable:
            consumer_map[variable].add(f"template:{template_name}")

    keys = sorted(set(template_context.keys()) | set(emitter_map) | set(consumer_map))

    summary: list[dict[str, Any]] = []
    for key in keys:
        value = template_context.get(key)
        summary.append(
            {
                "name": key,
                "type": type(value).__name__ if value is not None else "None",
                "value": _format_value_preview(value),
                "emitters": sorted(emitter_map.get(key, {"-"})),
                "consumers": sorted(consumer_map.get(key, {"-"})),
            }
        )

    return summary


__all__ = ["summarise_context_usage"]
