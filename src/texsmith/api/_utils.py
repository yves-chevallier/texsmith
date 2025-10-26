"""Internal helpers shared across API modules."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


__all__ = ["build_unique_stem_map"]


def build_unique_stem_map(paths: Iterable[Path]) -> dict[Path, str]:
    """Generate unique stems for a sequence of paths."""
    counters: dict[str, int] = {}
    used: set[str] = set()
    mapping: dict[Path, str] = {}

    for path in paths:
        base = path.stem
        index = counters.get(base, 0)
        candidate = base if index == 0 else f"{base}-{index + 1}"
        while candidate in used:
            index += 1
            candidate = f"{base}-{index + 1}"
        counters[base] = index + 1
        used.add(candidate)
        mapping[path] = candidate

    return mapping

