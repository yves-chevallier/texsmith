"""Public template helpers shared across the conversion pipeline."""

from __future__ import annotations

from .base import BaseTemplate, ResolvedAsset, WrappableTemplate
from .loader import copy_template_assets, discover_templates, load_template
from .manifest import (
    DEFAULT_TEMPLATE_LANGUAGE,
    LATEX_HEADING_LEVELS,
    TemplateAttributeSpec,
    TemplateAsset,
    TemplateError,
    TemplateInfo,
    TemplateManifest,
    TemplateSlot,
)
from .runtime import (
    TemplateBinding,
    TemplateRuntime,
    build_template_overrides,
    coerce_base_level,
    extract_base_level_override,
    extract_language_from_front_matter,
    load_template_runtime,
    normalise_template_language,
    resolve_template_binding,
    resolve_template_language,
)
from .wrapper import TemplateWrapResult, wrap_template_document

__all__ = [
    "BaseTemplate",
    "DEFAULT_TEMPLATE_LANGUAGE",
    "LATEX_HEADING_LEVELS",
    "ResolvedAsset",
    "TemplateAttributeSpec",
    "TemplateAsset",
    "TemplateBinding",
    "TemplateError",
    "TemplateInfo",
    "TemplateManifest",
    "TemplateRuntime",
    "TemplateSlot",
    "TemplateWrapResult",
    "WrappableTemplate",
    "build_template_overrides",
    "coerce_base_level",
    "copy_template_assets",
    "discover_templates",
    "extract_base_level_override",
    "extract_language_from_front_matter",
    "load_template",
    "load_template_runtime",
    "normalise_template_language",
    "wrap_template_document",
    "resolve_template_binding",
    "resolve_template_language",
]
