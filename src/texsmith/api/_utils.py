"""Supporting utilities shared by the high-level API modules.

Architecture
: `build_unique_stem_map` receives the original source paths used by the API and
  produces collision-free stem identifiers. Conversion pipelines rely on these
  stems to generate fragment file names and manifest entries without leaking
  implementation details from the caller.

Implementation Rationale
: The conversion pipeline needs deterministic names to produce predictable
  outputs across runs. Centralising the stem logic ensures that future
  refinements, such as Unicode slug handling, propagate consistently.
: Encapsulating the naming strategy inside a dedicated helper keeps pipeline
  tests focused on transformation behaviour instead of string manipulation edge
  cases.

Usage Example
:
    >>> from pathlib import Path
    >>> paths = [Path("book/chapter.md"), Path("notes/chapter.md"), Path("notes/appendix.md")]
    >>> mapping = build_unique_stem_map(paths)
    >>> mapping[Path("book/chapter.md")]
    'chapter'
    >>> mapping[Path("notes/chapter.md")]
    'chapter-2'
    >>> mapping[Path("notes/appendix.md")]
    'appendix'
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


__all__ = ["build_unique_stem_map"]


def build_unique_stem_map(paths: Iterable[Path]) -> dict[Path, str]:
    """Generate unique stems for a sequence of paths to avoid filename collisions during rendering."""
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
