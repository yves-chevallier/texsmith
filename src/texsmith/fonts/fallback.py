"""Fallback selection and fast lookup helpers."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
import pickle
from typing import Any

from texsmith.fonts.cache import FontCache
from texsmith.fonts.coverage import NotoCoverage
from texsmith.fonts.logging import FontPipelineLogger
from texsmith.fonts.ucharclasses import UCharClass


CACHE_VERSION = 1
BLOCK_SHIFT = 8  # 256-codepoint buckets


def _sanitize_family(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum())


def _merge_ranges(ranges: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """Merge overlapping/contiguous ranges and return a sorted tuple."""
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return tuple((start, end) for start, end in merged)


@dataclass(slots=True)
class _CoverageView:
    """Preprocessed coverage entry with merged ranges and fast-starts."""

    meta: NotoCoverage
    ranges: tuple[tuple[int, int], ...]
    starts: tuple[int, ...]
    total_span: int
    family_lower: str


@dataclass(slots=True)
class FallbackPlan:
    """Structured result of a fallback scan."""

    summary: list[dict]
    fonts: list[dict]
    group_fonts: dict[str, dict]
    uncovered: list[int]
    strategy: str = "by_class"

    def __iter__(self) -> Any:
        return iter(self.summary)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.summary)

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return bool(self.summary)


@dataclass(slots=True)
class FallbackEntry:
    name: str
    start: int
    end: int
    group: str | None
    font: dict

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "start": self.start,
            "end": self.end,
            "group": self.group,
            "font": self.font,
        }
        return payload


class FallbackBuilder:
    """Associate ucharclasses with the best matching Noto font."""

    def __init__(self, *, logger: FontPipelineLogger | None = None) -> None:
        self.logger = logger or FontPipelineLogger()

    def _prepare_coverage(self, coverage: Iterable[NotoCoverage]) -> list[_CoverageView]:
        views: list[_CoverageView] = []
        for entry in coverage:
            merged = _merge_ranges(entry.ranges)
            starts = tuple(start for start, _ in merged)
            total_span = sum(end - start + 1 for start, end in merged)
            views.append(
                _CoverageView(
                    meta=entry,
                    ranges=merged,
                    starts=starts,
                    total_span=total_span,
                    family_lower=entry.family.lower(),
                )
            )
        return views

    @staticmethod
    def _range_overlap(
        class_start: int,
        class_end: int,
        ranges: tuple[tuple[int, int], ...],
        starts: tuple[int, ...],
    ) -> int:
        """Compute overlap using sorted ranges and early exit."""
        if not ranges:
            return 0
        idx = bisect_left(starts, class_start)
        if idx:
            idx -= 1  # include the range that could start before the class
        total = 0
        for r_start, r_end in ranges[idx:]:
            if r_start > class_end:
                break
            if r_end < class_start:
                continue
            lo = class_start if class_start > r_start else r_start
            hi = class_end if class_end < r_end else r_end
            total += hi - lo + 1
        return total

    def _pick_font(self, cls: UCharClass, coverage: Iterable[_CoverageView]) -> dict | None:
        """Pick the most specific font for a class.

        Scoring favours the largest overlap, then smaller coverage span (script-specific
        fonts), then a small bonus when the family name mentions the class name.
        """
        class_range = (cls.start, cls.end)
        class_name = cls.name.lower()
        best: _CoverageView | None = None
        best_score: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)
        group_token = (cls.group or cls.name or "").lower()
        for view in coverage:
            overlap = self._range_overlap(class_range[0], class_range[1], view.ranges, view.starts)
            if overlap == 0:
                continue
            # Prefer families that declare usable styles so we avoid display-only sets with missing OTFs.
            style_bonus = len(view.meta.styles) if view.meta.styles else 0
            # Prefer non-display families when all else is equal so we select workhorse sets over
            # print/display cuts that may be narrower or less available.
            display_bonus = 0 if "display" in view.family_lower else 1
            name_bonus = (
                1 if (class_name in view.family_lower or group_token in view.family_lower) else 0
            )
            score = (overlap, name_bonus, style_bonus, display_bonus, -view.total_span)
            if score > best_score:
                best_score = score
                best = view
        if best is None:
            return None
        styles = list(best.meta.styles or ["regular", "bold"])
        return {
            "name": best.meta.file_base or _sanitize_family(best.meta.family),
            "extension": ".otf",
            "styles": styles,
            "dir": best.meta.dir_base,
        }

    def build(
        self,
        classes: Iterable[UCharClass],
        coverage: Iterable[NotoCoverage],
        *,
        announce: bool | None = None,
    ) -> list[FallbackEntry]:
        coverage_views = self._prepare_coverage(coverage)
        entries: list[FallbackEntry] = []
        for cls in classes:
            font = cls.font or self._pick_font(cls, coverage_views)
            if font is None:
                fallback_name = _sanitize_family(f"NotoSans{cls.name}")
                font = {
                    "name": fallback_name,
                    "extension": ".otf",
                    "styles": ["regular", "bold"],
                }
            entries.append(
                FallbackEntry(
                    name=cls.name,
                    start=cls.start,
                    end=cls.end,
                    group=cls.group,
                    font=font,
                ),
            )
        log_fn = self.logger.info if announce else self.logger.debug
        log_fn(f"Fallback fonts generated for {len(entries)} classes.")
        return entries


class FallbackIndex:
    """Bucketed interval index for O(1) fallback lookups."""

    def __init__(self, entries: Iterable[FallbackEntry]) -> None:
        self.entries = tuple(entries)
        self._buckets: dict[int, list[int]] = {}
        for idx, entry in enumerate(self.entries):
            start_block = entry.start >> BLOCK_SHIFT
            end_block = entry.end >> BLOCK_SHIFT
            for block in range(start_block, end_block + 1):
                self._buckets.setdefault(block, []).append(idx)

    def ranges_for_codepoint(self, codepoint: int) -> list[FallbackEntry]:
        bucket = self._buckets.get(codepoint >> BLOCK_SHIFT)
        if not bucket:
            return []
        hits: list[FallbackEntry] = []
        for idx in bucket:
            entry = self.entries[idx]
            if entry.start <= codepoint <= entry.end:
                hits.append(entry)
        return hits

    def serialize(self) -> dict:
        return {
            "version": CACHE_VERSION,
            "block_shift": BLOCK_SHIFT,
            "entries": [entry.to_dict() for entry in self.entries],
            "buckets": self._buckets,
        }

    @classmethod
    def from_serialized(cls, payload: dict) -> FallbackIndex | None:
        if payload.get("version") != CACHE_VERSION or payload.get("block_shift") != BLOCK_SHIFT:
            return None
        entries = [
            FallbackEntry(
                name=entry["name"],
                start=int(entry["start"]),
                end=int(entry["end"]),
                group=entry.get("group"),
                font=entry.get("font", {}),
            )
            for entry in payload.get("entries", [])
        ]
        index = cls(entries)
        index._buckets = {int(k): list(v) for k, v in payload.get("buckets", {}).items()}  # type: ignore[assignment]
        return index


class FallbackRepository:
    """Load or build a cached fallback index."""

    def __init__(
        self,
        *,
        cache: FontCache | None = None,
        logger: FontPipelineLogger | None = None,
    ) -> None:
        self.cache = cache or FontCache()
        self.logger = logger or FontPipelineLogger()
        self.cache_path = self.cache.path("fallback_index.pkl")

    def _signature(self, entries: list[FallbackEntry]) -> str:
        data = [e.to_dict() for e in entries]
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()

    def load(self, expected_signature: str | None = None) -> FallbackIndex | None:
        if not self.cache_path.exists():
            return None
        try:
            raw = pickle.loads(self.cache_path.read_bytes())
        except Exception:
            return None
        if raw.get("version") != CACHE_VERSION:
            return None
        if expected_signature and raw.get("signature") != expected_signature:
            return None
        return FallbackIndex.from_serialized(raw.get("index", {}))

    def save(self, index: FallbackIndex, signature: str) -> None:
        payload = {
            "version": CACHE_VERSION,
            "signature": signature,
            "index": index.serialize(),
        }
        try:
            self.cache_path.write_bytes(pickle.dumps(payload))
        except Exception:
            self.logger.warning("Impossible d'écrire le cache des fallbacks.")

    def load_or_build(self, entries: list[FallbackEntry]) -> FallbackIndex:
        signature = self._signature(entries)
        cached = self.load(expected_signature=signature)
        if cached:
            self.logger.notice("Index fallback chargé depuis %s", self.cache_path)
            return cached
        index = FallbackIndex(entries)
        self.save(index, signature)
        return index


class FallbackLookup:
    """Lookup helper exposing a get_classes-like summary."""

    def __init__(self, index: FallbackIndex) -> None:
        self.index = index

    def lookup(self, text: str) -> dict[str, dict]:
        classes: dict[str, dict] = {}
        for ch in text:
            codepoint = ord(ch)
            hits = self.index.ranges_for_codepoint(codepoint)
            if not hits:
                if codepoint <= 0x7F:
                    continue
                hits = [
                    FallbackEntry(
                        name="Unknown",
                        start=codepoint,
                        end=codepoint,
                        group=None,
                        font={},
                    )
                ]
            for hit in hits:
                entry = classes.setdefault(
                    hit.name,
                    {
                        "fonts": set(),
                        "ranges": [],
                        "group": hit.group or hit.name,
                        "font": hit.font,
                    },
                )
                entry["fonts"].add(hit.font.get("name") if hit.font else None)
                entry["ranges"].append(codepoint)
        return classes

    @staticmethod
    def _merge_ranges(codes: list[int]) -> list[str]:
        if not codes:
            return []
        codes = sorted(set(codes))
        merged: list[str] = []
        start = end = codes[0]
        for value in codes[1:]:
            if value == end + 1:
                end = value
            else:
                merged.append(f"U+{start:04X}" if start == end else f"U+{start:04X}-U+{end:04X}")
                start = end = value
        merged.append(f"U+{start:04X}" if start == end else f"U+{start:04X}-U+{end:04X}")
        return merged

    def summary(self, text: str) -> list[dict]:
        raw = self.lookup(text)
        output: list[dict] = []
        for cls, data in raw.items():
            ranges = self._merge_ranges(data["ranges"])
            count = len(set(data["ranges"]))
            fonts = sorted(f for f in data["fonts"] if f)
            output.append(
                {
                    "class": cls,
                    "group": data.get("group", cls),
                    "fonts": fonts,
                    "font": data.get("font", {}),
                    "ranges": ranges,
                    "count": count,
                }
            )
        return sorted(output, key=lambda entry: entry["class"])


def merge_fallback_summaries(
    existing: Iterable[Mapping[str, Any]], updates: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Merge fallback summaries keyed by class/group, accumulating counts and ranges."""
    merged: dict[str, dict[str, Any]] = {}

    def _key(entry: Mapping[str, Any]) -> str | None:
        cls = entry.get("class")
        group = entry.get("group")
        if isinstance(cls, str) and cls.strip():
            return cls
        if isinstance(group, str) and group.strip():
            return group
        return None

    def _consume(entry: Mapping[str, Any]) -> None:
        key = _key(entry)
        if key is None:
            return
        target = merged.setdefault(key, {"class": entry.get("class"), "group": entry.get("group")})
        font_meta = entry.get("font")
        if isinstance(font_meta, Mapping) and font_meta:
            target.setdefault("font", dict(font_meta))
        fonts = entry.get("fonts")
        if isinstance(fonts, Iterable) and not isinstance(fonts, (str, bytes)):
            font_set = set(target.get("fonts", []))
            font_set.update(str(f) for f in fonts if f)
            if font_set:
                target["fonts"] = sorted(font_set)
        ranges = entry.get("ranges")
        if isinstance(ranges, Iterable) and not isinstance(ranges, (str, bytes)):
            range_set = set(target.get("ranges", []))
            range_set.update(str(r) for r in ranges if r)
            target["ranges"] = sorted(range_set)
        count = entry.get("count")
        if isinstance(count, (int, float)):
            target["count"] = int(target.get("count", 0) or 0) + int(count)

    for payload in existing:
        if isinstance(payload, Mapping):
            _consume(payload)
    for payload in updates:
        if isinstance(payload, Mapping):
            _consume(payload)

    return sorted(
        merged.values(),
        key=lambda entry: entry.get("class") or entry.get("group") or "",
    )


__all__ = [
    "FallbackBuilder",
    "FallbackEntry",
    "FallbackIndex",
    "FallbackLookup",
    "FallbackPlan",
    "FallbackRepository",
    "merge_fallback_summaries",
]
