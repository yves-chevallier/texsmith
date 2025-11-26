"""Font matching helpers built around precomputed Noto coverage metadata."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import resources
import os
from pathlib import Path
import pickle
import shutil
from typing import Any

import yaml

from texsmith.fonts.locator import FontLocator
from texsmith.fonts.utils import normalize_family


CACHE_VERSION = 3
BLOCK_SHIFT = 8  # 256-codepoint buckets for fast narrowing
BLOCK_SIZE = 1 << BLOCK_SHIFT
_DATA_PACKAGE = "texsmith.fonts.data"


@dataclass(frozen=True, slots=True)
class FontMatchResult:
    """Summary of the fonts required to cover a text payload."""

    fallback_fonts: tuple[str, ...]
    present_fonts: tuple[str, ...]
    missing_fonts: tuple[str, ...]
    missing_codepoints: tuple[int, ...]
    font_ranges: Mapping[str, list[str]]
    fonts_yaml: Path | None = None

    def to_context(self) -> dict[str, object]:
        """Convert the match details into a template-friendly context mapping."""
        return {
            "fallback_fonts": list(self.fallback_fonts),
            "present_fonts": list(self.present_fonts),
            "missing_fonts": list(self.missing_fonts),
            "missing_codepoints": [f"U+{cp:04X}" for cp in self.missing_codepoints],
            "fonts_yaml": str(self.fonts_yaml) if self.fonts_yaml else None,
            "font_ranges": dict(self.font_ranges),
        }


class FontIndex:
    """Bucketed interval index over Unicode codepoints."""

    def __init__(self, ranges: Iterable[tuple[int, int, str]]) -> None:
        self._buckets: dict[int, list[tuple[int, int, str]]] = {}
        self._family_priority: dict[str, tuple] = {}
        for start, end, family in ranges:
            start_block = start >> BLOCK_SHIFT
            end_block = end >> BLOCK_SHIFT
            for block in range(start_block, end_block + 1):
                self._buckets.setdefault(block, []).append((start, end, family))

    def fonts_for_codepoint(self, codepoint: int) -> set[str]:
        bucket = self._buckets.get(codepoint >> BLOCK_SHIFT)
        if not bucket:
            return set()
        return {family for start, end, family in bucket if start <= codepoint <= end}

    def ranges_for_codepoint(self, codepoint: int) -> list[tuple[int, int, str]]:
        bucket = self._buckets.get(codepoint >> BLOCK_SHIFT)
        if not bucket:
            return []
        return [(start, end, family) for start, end, family in bucket if start <= codepoint <= end]

    def to_serialized(self) -> dict:
        return {
            "version": CACHE_VERSION,
            "block_shift": BLOCK_SHIFT,
            "buckets": dict(self._buckets),
        }

    @classmethod
    def from_serialized(cls, data: Mapping[str, Any]) -> FontIndex | None:
        if data.get("version") != CACHE_VERSION or data.get("block_shift") != BLOCK_SHIFT:
            return None
        inst = cls([])
        inst._buckets = {
            int(block): [tuple(r) for r in ranges]
            for block, ranges in data.get("buckets", {}).items()
        }  # type: ignore[assignment]
        inst._family_priority = {}
        return inst


def _parse_codepoint(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        val = value.strip()
        if val.upper().startswith("U+"):
            val = val[2:]
        return int(
            val,
            16
            if val.lower().startswith("0x") or all(ch in "0123456789ABCDEFabcdef" for ch in val)
            else 10,
        )
    raise TypeError(f"Unsupported codepoint value: {value!r}")


def parse_range(range_item: Any, family: str) -> tuple[int, int, str]:
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
            raise ValueError(f"Unexpected range list length: {range_item!r}")
    else:
        raise TypeError(f"Unsupported range type: {type(range_item)}")
    start, end = (start, end) if start <= end else (end, start)
    return (start, end, family)


def load_ranges(fonts_yaml: Path | bytes | str) -> list[tuple[int, int, str]]:
    if isinstance(fonts_yaml, Path):
        raw = fonts_yaml.read_text(encoding="utf-8")
    elif isinstance(fonts_yaml, bytes):
        raw = fonts_yaml.decode("utf-8")
    else:
        raw = str(fonts_yaml)

    data = yaml.safe_load(raw)
    ranges: list[tuple[int, int, str]] = []
    for entry in data:
        family = entry["family"]
        for r in entry["unicode_ranges"]:
            ranges.append(parse_range(r, family))
    return ranges


def cache_path_for(fonts_yaml: Path) -> Path:
    return fonts_yaml.with_suffix(".fontindex.pkl")


def load_cached_index(fonts_yaml: Path) -> FontIndex | None:
    cache_path = cache_path_for(fonts_yaml)
    if not cache_path.exists():
        return None
    try:
        if cache_path.stat().st_mtime < fonts_yaml.stat().st_mtime:
            return None
        data = pickle.loads(cache_path.read_bytes())
        return FontIndex.from_serialized(data)
    except Exception:
        return None


def save_cached_index(index: FontIndex, fonts_yaml: Path) -> None:
    cache_path = cache_path_for(fonts_yaml)
    try:
        cache_path.write_bytes(pickle.dumps(index.to_serialized()))
    except Exception:
        return


def _resource_bytes(name: str) -> bytes:
    resource = resources.files(_DATA_PACKAGE) / name
    with resources.as_file(resource) as path:
        return path.read_bytes()


def _load_default_index() -> FontIndex:
    try:
        serialized = pickle.loads(_resource_bytes("fonts.fontindex.pkl"))
        index = FontIndex.from_serialized(serialized)
        if index is not None:
            return index
    except Exception:
        serialized = None

    fonts_yaml = _resource_bytes("fonts.yaml")
    return FontIndex(load_ranges(fonts_yaml))


_DEFAULT_INDEX: FontIndex | None = None


def get_index(fonts_yaml: Path | None = None) -> FontIndex:
    global _DEFAULT_INDEX
    if fonts_yaml is None:
        if _DEFAULT_INDEX is None:
            _DEFAULT_INDEX = _load_default_index()
        return _DEFAULT_INDEX

    cached = load_cached_index(fonts_yaml)
    if cached:
        return cached

    index = FontIndex(load_ranges(fonts_yaml))
    save_cached_index(index, fonts_yaml)
    return index


def _ranges_from_codepoints(codepoints: Iterable[int]) -> list[str]:
    cps = sorted(set(codepoints))
    if not cps:
        return []
    ranges: list[str] = []
    start = prev = cps[0]
    for cp in cps[1:]:
        if cp == prev + 1:
            prev = cp
            continue
        if start == prev:
            ranges.append(f"U+{start:04X}")
        else:
            ranges.append(f"U+{start:04X}..U+{prev:04X}")
        start = prev = cp
    if start == prev:
        ranges.append(f"U+{start:04X}")
    else:
        ranges.append(f"U+{start:04X}..U+{prev:04X}")
    return ranges


def _font_priority(family: str) -> tuple:
    # Prefer the generic Noto families over specialised script variants so that
    # ASCII/Latin does not randomly select niche fonts that also cover Basic Latin.
    if family == "NotoSans":
        return (0, family)
    if family == "NotoSerif":
        return (1, family)
    if family.startswith("NotoSans"):
        return (2, len(family), family)
    if family.startswith("NotoSerif"):
        return (3, len(family), family)
    return (4, family)


def _font_priority_cached(font_index: FontIndex, family: str) -> tuple:
    cached = font_index._family_priority.get(family)  # noqa: SLF001
    if cached is not None:
        return cached
    pr = _font_priority(family)
    font_index._family_priority[family] = pr  # noqa: SLF001
    return pr


def _assign_fonts(text: str, fonts_yaml: Path | None = None) -> tuple[dict[int, str], set[int]]:
    index = get_index(fonts_yaml)
    assignments: dict[int, str] = {}
    missing: set[int] = set()
    for cp in {ord(ch) for ch in text}:
        # Skip ASCII entirely; base fonts already cover it and we don't want
        # fallback substitutions to hijack Basic Latin.
        if cp <= 0x7F:
            continue
        fonts = index.fonts_for_codepoint(cp) or _manual_fonts_for_codepoint(cp)
        if not fonts:
            missing.add(cp)
            continue
        best = min(fonts, key=lambda f: _font_priority_cached(index, f))
        assignments[cp] = best
    return assignments, missing


def _manual_fonts_for_codepoint(codepoint: int) -> set[str]:
    """Fallback map for scripts missing in the bundled font index."""
    if 0x0700 <= codepoint <= 0x074F:  # Syriac block
        return {
            "NotoSansSyriacEastern",
            "NotoSansSyriacWestern",
            "NotoSansSyriac",
        }
    return set()


def required_fonts(text: str, fonts_yaml: Path | None = None) -> set[str]:
    assignments, _ = _assign_fonts(text, fonts_yaml)
    return set(assignments.values())


def required_fonts_with_ranges(text: str, fonts_yaml: Path | None = None) -> dict[str, list[str]]:
    assignments, missing = _assign_fonts(text, fonts_yaml)
    per_font_cps: dict[str, set[int]] = {}
    for cp, family in assignments.items():
        per_font_cps.setdefault(family, set()).add(cp)
    if missing:
        per_font_cps["__UNCOVERED__"] = missing
    return {family: _ranges_from_codepoints(cps) for family, cps in per_font_cps.items()}


def discover_installed_families() -> dict[str, set[str]]:
    import subprocess

    # Avoid interfering with patched subprocess in tests or environments.
    run_fn = getattr(subprocess, "run", None)
    if run_fn is None or getattr(run_fn, "__module__", "") != "subprocess":
        return {}

    if shutil.which("fc-list") is None or os.environ.get("TEXSMITH_SKIP_FONT_CHECKS"):
        return {}

    try:
        proc = subprocess.run(
            ["fc-list", "-f", "%{family}\n"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return {}
    families: dict[str, set[str]] = {}
    for line in proc.stdout.splitlines():
        for part in line.split(","):
            part = part.strip()
            if part:
                norm = normalize_family(part)
                families.setdefault(norm, set()).add(part)
    return families


def check_installed(required: Iterable[str]) -> tuple[set[str], set[str]]:
    installed = discover_installed_families()
    present: set[str] = set()
    missing: set[str] = set()

    for fam in required:
        norm = normalize_family(fam)
        if norm in installed:
            present.add(fam)
        else:
            missing.add(fam)
    return present, missing


def match_text(
    text: str,
    *,
    fonts_yaml: Path | None = None,
    check_system: bool = True,
    font_locator: FontLocator | None = None,
) -> FontMatchResult:
    required = required_fonts(text, fonts_yaml=fonts_yaml)
    _assignments, missing_codepoints = _assign_fonts(text, fonts_yaml=fonts_yaml)
    font_ranges = required_fonts_with_ranges(text, fonts_yaml=fonts_yaml)

    present: set[str]
    missing_fonts: set[str]
    if check_system:
        if font_locator is not None:
            present, missing_fonts = font_locator.check_installed(required)
        else:
            present, missing_fonts = check_installed(required)
    else:
        present, missing_fonts = set(), set()

    return FontMatchResult(
        fallback_fonts=tuple(sorted(required)),
        present_fonts=tuple(sorted(present)),
        missing_fonts=tuple(sorted(missing_fonts)),
        missing_codepoints=tuple(sorted(missing_codepoints)),
        font_ranges=font_ranges,
        fonts_yaml=fonts_yaml,
    )


__all__ = [
    "FontIndex",
    "FontMatchResult",
    "check_installed",
    "discover_installed_families",
    "match_text",
    "required_fonts",
    "required_fonts_with_ranges",
]
