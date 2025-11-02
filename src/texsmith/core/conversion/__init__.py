"""Public gateway into the low-level conversion engine."""

from __future__ import annotations

from texsmith.core.conversion_contexts import (
    BinderContext,
    DocumentContext,
    GenerationStrategy,
    SegmentContext,
)
from texsmith.core.templates import (
    DEFAULT_TEMPLATE_LANGUAGE,
    TemplateBinding,
    TemplateRuntime,
    build_template_overrides,
    load_template_runtime,
    resolve_template_language,
)

from .core import (
    ConversionResult,
    attempt_transformer_fallback,
    convert_document,
    copy_document_state,
    ensure_fallback_converters,
    render_with_fallback,
)
from .debug import (
    ConversionError,
    DiagnosticEmitter,
    LoggingEmitter,
    NullEmitter,
    debug_enabled,
    ensure_emitter,
    format_rendering_error,
    persist_debug_artifacts,
    raise_conversion_error,
    record_event,
)
from .inputs import (
    DOCUMENT_SELECTOR_SENTINEL,
    InputKind,
    UnsupportedInputError,
    build_document_context,
    coerce_slot_selector,
    extract_content,
    extract_front_matter_bibliography,
    extract_front_matter_slots,
    parse_slot_mapping,
)
from .renderer import (
    FragmentOverrideError,
    TemplateFragment,
    TemplateRenderer,
    TemplateRendererResult,
)
from .templates import build_binder_context, extract_slot_fragments, heading_level_for


__all__ = [
    "DEFAULT_TEMPLATE_LANGUAGE",
    "DOCUMENT_SELECTOR_SENTINEL",
    "BinderContext",
    "ConversionError",
    "ConversionResult",
    "DiagnosticEmitter",
    "DocumentContext",
    "FragmentOverrideError",
    "GenerationStrategy",
    "InputKind",
    "LoggingEmitter",
    "NullEmitter",
    "SegmentContext",
    "TemplateBinding",
    "TemplateFragment",
    "TemplateRenderer",
    "TemplateRendererResult",
    "TemplateRuntime",
    "UnsupportedInputError",
    "attempt_transformer_fallback",
    "build_binder_context",
    "build_document_context",
    "build_template_overrides",
    "coerce_slot_selector",
    "convert_document",
    "copy_document_state",
    "debug_enabled",
    "ensure_emitter",
    "ensure_fallback_converters",
    "extract_content",
    "extract_front_matter_bibliography",
    "extract_front_matter_slots",
    "extract_slot_fragments",
    "format_rendering_error",
    "heading_level_for",
    "load_template_runtime",
    "parse_slot_mapping",
    "persist_debug_artifacts",
    "raise_conversion_error",
    "record_event",
    "render_with_fallback",
    "resolve_template_language",
]
