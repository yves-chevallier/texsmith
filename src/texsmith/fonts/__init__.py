"""Font toolchain façade used to prepare reliable LaTeX fallbacks.

Architecture
: `FontCache` pins downloads of Noto metadata, ucharclasses tables, and computed
  fallback indexes to a single cache root so repeated renders never thrash the
  network. The cache also carries signatures so on-disk data can be trusted.
: Builders such as `NotoCoverageBuilder` and `UCharClassesBuilder` transform
  upstream datasets into structured coverage ranges. `FallbackBuilder` consumes
  that data to calculate the minimal set of fonts required for arbitrary text.
: `FallbackManager` wraps the pipeline with memoisation, exposing simple lookup
  helpers while persisting results via `FallbackRepository` for reuse.
: Convenience generators (``generate_fallback_entries``/``generate_noto_metadata``/
  ``generate_ucharclasses_data``) orchestrate the above pieces and return
  ready-to-embed artifacts for renderers and CLI tooling.

Goal
: Provide deterministic, cache-aware font selection so TeXSmith can emit
  LaTeX that compiles on machines without full Unicode font coverage while
  keeping downloads minimal and reproducible.
"""

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
