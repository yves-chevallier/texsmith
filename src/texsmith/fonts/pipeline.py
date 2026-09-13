"""High-level orchestration helpers for the font toolchain."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from texsmith.fonts.cache import FontCache
from texsmith.fonts.coverage import NotoCoverage, NotoCoverageBuilder
from texsmith.fonts.fallback import (
    FallbackBuilder,
    FallbackLookup,
    FallbackPlan,
    FallbackRepository,
)
from texsmith.fonts.logging import FontPipelineLogger
from texsmith.fonts.ucharclasses import UCharClass, UCharClassesBuilder


_UCHAR_DATA_CACHE: dict[str, list[UCharClass]] = {}
_NOTO_DATA_CACHE: dict[str, list[NotoCoverage]] = {}
_LOOKUP_CACHE: dict[str, FallbackLookup] = {}


def _cache_key(cache: FontCache | None) -> str | None:
    try:
        root = cache.root if cache is not None else FontCache().root
        return str(root.resolve())
    except Exception:
        return None


def generate_ucharclasses_data(
    *, cache: FontCache | None = None, logger: FontPipelineLogger | None = None
):
    """Fetch and parse ucharclasses definitions, downloading assets if missing."""
    key = _cache_key(cache)
    if key and key in _UCHAR_DATA_CACHE:
        return _UCHAR_DATA_CACHE[key]
    builder = UCharClassesBuilder(cache=cache, logger=logger)
    data = builder.build()
    if key:
        _UCHAR_DATA_CACHE[key] = data
    return data


def generate_noto_metadata(
    *, cache: FontCache | None = None, logger: FontPipelineLogger | None = None
):
    """Build the Noto coverage dataset (equivalent to sandbox/build.py)."""
    key = _cache_key(cache)
    if key and key in _NOTO_DATA_CACHE:
        return _NOTO_DATA_CACHE[key]
    builder = NotoCoverageBuilder(cache=cache, logger=logger)
    data = builder.build()
    if key:
        _NOTO_DATA_CACHE[key] = data
    return data


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
    _lookup: FallbackLookup | None = field(default=None, init=False, repr=False)
    _coverage: list[NotoCoverage] | None = field(default=None, init=False, repr=False)

    def _ensure_lookup(self) -> FallbackLookup:
        if self._lookup is not None:
            return self._lookup
        repository = FallbackRepository(cache=self.cache, logger=self.logger)
        had_cache = repository.cache_path.exists()

        cache_key = _cache_key(self.cache)
        cached_any = repository.load()
        if cache_key and cache_key in _LOOKUP_CACHE and cached_any is None:
            self._lookup = _LOOKUP_CACHE[cache_key]
            return self._lookup

        classes = generate_ucharclasses_data(cache=self.cache, logger=self.logger)
        coverage = self._ensure_coverage()
        announce = not had_cache
        entries = FallbackBuilder(logger=self.logger).build(classes, coverage, announce=announce)
        signature = repository._signature(entries)  # noqa: SLF001

        cached = repository.load(expected_signature=signature)
        if cached is None:
            cached = repository.load_or_build(entries)

        self._lookup = FallbackLookup(cached)
        if cache_key:
            _LOOKUP_CACHE[cache_key] = self._lookup
        return self._lookup

    def _ensure_coverage(self) -> list[NotoCoverage]:
        if self._coverage is None:
            self._coverage = generate_noto_metadata(cache=self.cache, logger=self.logger)
        return self._coverage

    def _fonts_from_summary(self, summary: list[dict]) -> list[dict]:
        fonts: dict[str, dict] = {}
        for entry in summary:
            if not isinstance(entry, dict):
                continue
            font_meta = entry.get("font") if isinstance(entry.get("font"), dict) else {}
            name = font_meta.get("name")
            if not name:
                continue
            groups = set(fonts.get(name, {}).get("groups", []))
            group = entry.get("group") or entry.get("class")
            if isinstance(group, str) and group.strip():
                groups.add(group)
            ranges = set(fonts.get(name, {}).get("ranges", []))
            entry_ranges = entry.get("ranges")
            if isinstance(entry_ranges, Iterable) and not isinstance(entry_ranges, (str, bytes)):
                ranges.update(str(r) for r in entry_ranges)
            count = fonts.get(name, {}).get("count", 0) or 0
            entry_count = entry.get("count")
            if isinstance(entry_count, (int, float)):
                count += int(entry_count)
            fonts[name] = {
                "name": name,
                "extension": font_meta.get("extension", ".otf"),
                "styles": font_meta.get("styles", []),
                "dir": font_meta.get("dir"),
                "groups": sorted(groups),
                "ranges": sorted(ranges),
                "count": count if count else None,
            }
        return sorted(fonts.values(), key=lambda entry: entry["name"])

    def _merge_range_strings(self, codes: Iterable[int]) -> list[str]:
        from texsmith.fonts.fallback import FallbackLookup as _Lookup

        return _Lookup._merge_ranges(list(codes))  # noqa: SLF001

    def scan_text(self, text: str) -> FallbackPlan:
        lookup = self._ensure_lookup()
        summary = lookup.summary(text)
        fonts = self._fonts_from_summary(summary)
        group_fonts: dict[str, dict] = {}
        for entry in fonts:
            groups = entry.get("groups") or []
            if isinstance(groups, (list, tuple, set)):
                for group in groups:
                    if isinstance(group, str) and group:
                        group_fonts.setdefault(group, entry)
        return FallbackPlan(
            summary=summary,
            fonts=fonts,
            group_fonts=group_fonts,
            uncovered=[],
            strategy="by_class",
        )


__all__ = [
    "FallbackManager",
    "generate_fallback_entries",
    "generate_noto_metadata",
    "generate_ucharclasses_data",
]
