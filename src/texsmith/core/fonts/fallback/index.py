"""Fast lookup helpers for the bundled Noto fallback coverage."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
from pathlib import Path
import pickle
from typing import Any

import yaml


CACHE_VERSION = 1
BLOCK_SHIFT = 8  # 256-codepoint buckets

_DEFAULT_FONTS_YAML = Path(__file__).with_name("noto.yml")


@dataclass(frozen=True, slots=True)
class FontRange:
    """Unicode range covered by a font family."""

    start: int
    end: int
    family: str


@dataclass(frozen=True, slots=True)
class LookupSummary:
    """Aggregated lookup results for a single matcher instance."""

    ranges: tuple[FontRange, ...]
    fonts: tuple[str, ...]


class FontIndex:
    """Bucketed interval index over Unicode codepoints."""

    def __init__(self, ranges: Iterable[tuple[int, int, str]]) -> None:
        self._buckets: dict[int, list[tuple[int, int, str]]] = {}
        for start, end, family in ranges:
            start_block = start >> BLOCK_SHIFT
            end_block = end >> BLOCK_SHIFT
            for block in range(start_block, end_block + 1):
                self._buckets.setdefault(block, []).append((start, end, family))

    def ranges_for_codepoint(self, codepoint: int) -> list[tuple[int, int, str]]:
        bucket = self._buckets.get(codepoint >> BLOCK_SHIFT)
        if not bucket:
            return []
        return [(start, end, family) for start, end, family in bucket if start <= codepoint <= end]

    def to_serialized(self) -> dict[str, Any]:
        return {"version": CACHE_VERSION, "block_shift": BLOCK_SHIFT, "buckets": self._buckets}

    @classmethod
    def from_serialized(cls, data: dict[str, Any]) -> FontIndex | None:
        if data.get("version") != CACHE_VERSION or data.get("block_shift") != BLOCK_SHIFT:
            return None
        index = cls([])
        index._buckets = {
            int(block): [tuple(r) for r in ranges] for block, ranges in data["buckets"].items()
        }  # type: ignore[attr-defined,assignment]
        return index


def _parse_codepoint(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        val = value.strip()
        if val.upper().startswith("U+"):
            val = val[2:]
        base = 16 if val.lower().startswith("0x") else None
        if base is None and all(ch in "0123456789ABCDEFabcdef" for ch in val):
            base = 16
        return int(val, base or 10)
    msg = f"Unsupported codepoint value: {value!r}"
    raise TypeError(msg)


def _parse_range(range_item: Any, family: str) -> tuple[int, int, str]:
    if isinstance(range_item, str):
        if ".." in range_item:
            start_str, end_str = range_item.split("..", 1)
        elif "-" in range_item:
            start_str, end_str = range_item.split("-", 1)
        else:
            start_str = end_str = range_item
        start = _parse_codepoint(start_str)
        end = _parse_codepoint(end_str)
    elif isinstance(range_item, (list, tuple)):
        if len(range_item) == 1:
            start = end = _parse_codepoint(range_item[0])
        elif len(range_item) == 2:
            start = _parse_codepoint(range_item[0])
            end = _parse_codepoint(range_item[1])
        else:
            msg = f"Unexpected range list length: {range_item!r}"
            raise ValueError(msg)
    else:
        msg = f"Unsupported range type: {type(range_item)}"
        raise TypeError(msg)
    start, end = (start, end) if start <= end else (end, start)
    return (start, end, family)


def _load_ranges(fonts_yaml: Path) -> list[FontRange]:
    data = yaml.safe_load(fonts_yaml.read_text(encoding="utf-8"))
    ranges: list[FontRange] = []
    for entry in data:
        family = entry["family"]
        for r in entry["unicode_ranges"]:
            start, end, fam = _parse_range(r, family)
            ranges.append(FontRange(start=start, end=end, family=fam))
    return ranges


class FallbackFontIndex:
    """Lookup helper built on top of the bundled Noto coverage table."""

    def __init__(self, *, fonts_yaml: Path | None = None, cache_path: Path | None = None) -> None:
        self.fonts_yaml = fonts_yaml or _DEFAULT_FONTS_YAML
        self.cache_path = cache_path or self.fonts_yaml.with_suffix(".fontindex.pkl")
        self._fonts_signature = hashlib.sha256(self.fonts_yaml.read_bytes()).hexdigest()
        self._index = self._load_index()
        self._lookup_cache: dict[int, tuple[FontRange, ...]] = {}
        self.reset()

    def _load_index(self) -> FontIndex:
        cached = self._load_cached_index()
        if cached is not None:
            return cached

        ranges = _load_ranges(self.fonts_yaml)
        index = FontIndex((r.start, r.end, r.family) for r in ranges)
        self._persist_cache(index)
        return index

    def _load_cached_index(self) -> FontIndex | None:
        if not self.cache_path.exists():
            return None
        try:
            data = pickle.loads(self.cache_path.read_bytes())
            if (
                data.get("version") != CACHE_VERSION
                or data.get("signature") != self._fonts_signature
            ):
                return None
            return FontIndex.from_serialized(data.get("index", {}))
        except Exception:
            return None

    def _persist_cache(self, index: FontIndex) -> None:
        payload = {
            "version": CACHE_VERSION,
            "signature": self._fonts_signature,
            "index": index.to_serialized(),
        }
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_bytes(pickle.dumps(payload))
        except Exception:
            return

    def _coerce_codepoint(self, value: str | int) -> int:
        if isinstance(value, str):
            if not value:
                msg = "Empty string cannot be converted to a codepoint."
                raise ValueError(msg)
            value = ord(value[0])
        return int(value)

    def lookup(self, value: str | int) -> tuple[FontRange, ...]:
        """Return the ranges covering the provided character or codepoint."""
        codepoint = self._coerce_codepoint(value)
        cached = self._lookup_cache.get(codepoint)
        if cached is None:
            ranges = tuple(FontRange(*hit) for hit in self._index.ranges_for_codepoint(codepoint))
            self._lookup_cache[codepoint] = ranges
        else:
            ranges = cached

        if ranges:
            self._history_ranges.update(ranges)
            self._history_fonts.update(r.family for r in ranges)
        return ranges

    def summary(self) -> LookupSummary:
        """Return the fonts and ranges seen since the last reset()."""
        ranges = tuple(sorted(self._history_ranges, key=lambda r: (r.start, r.end, r.family)))
        fonts = tuple(sorted(self._history_fonts))
        return LookupSummary(ranges=ranges, fonts=fonts)

    def reset(self) -> None:
        """Clear any accumulated lookup history."""
        self._history_ranges: set[FontRange] = set()
        self._history_fonts: set[str] = set()


__all__ = [
    "FallbackFontIndex",
    "FontRange",
    "LookupSummary",
]
