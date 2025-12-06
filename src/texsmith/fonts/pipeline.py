"""High-level orchestration helpers for the font toolchain."""

from __future__ import annotations

from dataclasses import dataclass, field

from texsmith.fonts.cache import FontCache
from texsmith.fonts.coverage import NotoCoverageBuilder
from texsmith.fonts.fallback import FallbackBuilder, FallbackLookup, FallbackRepository
from texsmith.fonts.logging import FontPipelineLogger
from texsmith.fonts.ucharclasses import UCharClassesBuilder


def generate_ucharclasses_data(
    *, cache: FontCache | None = None, logger: FontPipelineLogger | None = None
):
    """Fetch and parse ucharclasses definitions, downloading assets if missing."""
    builder = UCharClassesBuilder(cache=cache, logger=logger)
    return builder.build()


def generate_noto_metadata(
    *, cache: FontCache | None = None, logger: FontPipelineLogger | None = None
):
    """Build the Noto coverage dataset (equivalent to sandbox/build.py)."""
    builder = NotoCoverageBuilder(cache=cache, logger=logger)
    return builder.build()


def generate_fallback_entries(
    *,
    cache: FontCache | None = None,
    logger: FontPipelineLogger | None = None,
):
    """Compute fallback associations, reusing cached inputs when available."""
    cache = cache or FontCache()
    logger = logger or FontPipelineLogger()
    classes = generate_ucharclasses_data(cache=cache, logger=logger)
    coverage = generate_noto_metadata(cache=cache, logger=logger)
    return FallbackBuilder(logger=logger).build(classes, coverage)


@dataclass(slots=True)
class FallbackManager:
    """Facade that caches the fallback index and exposes fast lookups."""

    cache: FontCache = field(default_factory=FontCache)
    logger: FontPipelineLogger = field(default_factory=FontPipelineLogger)

    def _ensure_lookup(self) -> FallbackLookup:
        classes = generate_ucharclasses_data(cache=self.cache, logger=self.logger)
        coverage = generate_noto_metadata(cache=self.cache, logger=self.logger)
        entries = FallbackBuilder(logger=self.logger).build(classes, coverage)
        index = FallbackRepository(cache=self.cache, logger=self.logger).load_or_build(entries)
        return FallbackLookup(index)

    def scan_text(self, text: str) -> list[dict]:
        lookup = self._ensure_lookup()
        return lookup.summary(text)


__all__ = [
    "FallbackManager",
    "generate_fallback_entries",
    "generate_noto_metadata",
    "generate_ucharclasses_data",
]
