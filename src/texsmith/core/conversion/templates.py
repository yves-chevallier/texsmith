"""Template orchestration helpers powering the conversion pipeline."""

from __future__ import annotations

from collections.abc import Mapping
import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from texsmith.core.exceptions import raise_conversion_error
from texsmith.diagnostics import (
    DiagnosticEmitter,
    debug_enabled,
    emit_diagnostic,
    ensure_emitter,
)

from ..config import BookConfig
from ..conversion_contexts import ConversionContext
from ..templates import TemplateBinding, TemplateError, resolve_template_binding


if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


def _resolve_callout_style(*contexts: Mapping[str, Any] | None) -> str | None:
    for context in contexts:
        if not isinstance(context, Mapping):
            continue
        callouts = context.get("callouts")
        if isinstance(callouts, Mapping):
            style = callouts.get("style")
            if isinstance(style, str) and style.strip():
                return style.strip()
        press_section = context.get("press")
        if isinstance(press_section, Mapping):
            press_callouts = press_section.get("callouts")
            if isinstance(press_callouts, Mapping):
                style = press_callouts.get("style")
                if isinstance(style, str) and style.strip():
                    return style.strip()
            for key in ("callout_style", "callouts_style"):
                style = press_section.get(key)
                if isinstance(style, str) and style.strip():
                    return style.strip()
        for key in ("callout_style", "callouts_style"):
            style = context.get(key)
            if isinstance(style, str) and style.strip():
                return style.strip()
    return None


def _build_mustache_defaults(*contexts: Mapping[str, Any] | None) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    callout_style = _resolve_callout_style(*contexts) or "fancy"
    defaults["callouts"] = {"style": callout_style}
    return defaults


def bind_template(
    *,
    context: ConversionContext,
    template: str | None,
    emitter: DiagnosticEmitter | None,
    legacy_latex_accents: bool,
) -> ConversionContext:
    """Resolve the template binding and attach it to ``context``.

    The incoming :class:`ConversionContext` has its template-bound fields
    unset; this function selects the template, builds a :class:`BookConfig`
    from the resolved language, and stores both back on the context. The
    same object is returned (mutated in place) so callers can chain.
    """
    emitter = ensure_emitter(emitter)
    document = context.document

    config = BookConfig(
        project_dir=document.source_path.parent,
        language=context.language,
        legacy_latex_accents=legacy_latex_accents,
    )

    active_slot_requests: dict[str, str] = {}
    binding: TemplateBinding | None = None
    try:
        binding, active_slot_requests = resolve_template_binding(
            template=template,
            template_runtime=context.template_runtime,
            template_overrides=context.template_overrides,
            slot_requests=context.slot_requests,
            warn=lambda message: emit_diagnostic(emitter, "slot-undeclared", message),
        )
    except TemplateError as exc:
        if debug_enabled(emitter):
            raise
        raise_conversion_error(emitter, str(exc), exc)
    if binding is None:  # pragma: no cover - defensive
        raise RuntimeError("Failed to resolve template binding.")

    if binding.runtime and binding.runtime.extras:
        template_mermaid = binding.runtime.extras.get("mermaid_config")
        if template_mermaid and not config.mermaid_config:
            config.mermaid_config = Path(template_mermaid)

    context.config = config
    context.template_binding = binding
    context.slot_requests = active_slot_requests
    return context


def _merge_template_overrides(
    base: Mapping[str, Any], overrides: Mapping[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(dict(base))

    def _merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, Mapping):
                existing = target.get(key)
                nested: dict[str, Any] = dict(existing) if isinstance(existing, Mapping) else {}
                _merge(nested, value)
                target[key] = nested
            else:
                target[key] = copy.deepcopy(value)

    _merge(merged, overrides)
    return merged
