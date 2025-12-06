"""Public API for TeXSmith font utilities."""

from texsmith.fonts.cache import FontCache
from texsmith.fonts.coverage import NotoCoverage, NotoCoverageBuilder
from texsmith.fonts.fallback import (
    FallbackBuilder,
    FallbackEntry,
    FallbackIndex,
    FallbackLookup,
    FallbackRepository,
)
from texsmith.fonts.logging import FontPipelineLogger
from texsmith.fonts.pipeline import (
    FallbackManager,
    generate_fallback_entries,
    generate_noto_metadata,
    generate_ucharclasses_data,
)
from texsmith.fonts.ucharclasses import UCharClass, UCharClassesBuilder


__all__ = [
    "FallbackBuilder",
    "FallbackEntry",
    "FallbackIndex",
    "FallbackLookup",
    "FallbackManager",
    "FallbackRepository",
    "FontCache",
    "FontPipelineLogger",
    "NotoCoverage",
    "NotoCoverageBuilder",
    "UCharClass",
    "UCharClassesBuilder",
    "generate_fallback_entries",
    "generate_noto_metadata",
    "generate_ucharclasses_data",
]
