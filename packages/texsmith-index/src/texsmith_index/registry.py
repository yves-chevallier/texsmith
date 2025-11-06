"""Global registry tracking hashtag-index entries across documents."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from threading import Lock


IndexEntry = tuple[str, ...]


@dataclass(slots=True)
class IndexRegistry:
    """Thread-safe container gathering index entries encountered during rendering."""

    _entries: set[IndexEntry] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def add(self, entry: Iterable[str]) -> None:
        """Record a tuple describing an index entry."""
        values = tuple(part for part in entry if part)
        if not values:
            return
        with self._lock:
            self._entries.add(values)

    def clear(self) -> None:
        """Reset the registry to its initial empty state."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:  # pragma: no cover - trivial
        with self._lock:
            return len(self._entries)

    def __iter__(self) -> Iterator[IndexEntry]:  # pragma: no cover - simple proxy
        with self._lock:
            yield from sorted(self._entries)

    def snapshot(self) -> set[IndexEntry]:
        """Return a shallow copy of the registered entries."""
        with self._lock:
            return set(self._entries)


_REGISTRY = IndexRegistry()


def get_registry() -> IndexRegistry:
    """Return the global index registry."""
    return _REGISTRY


def clear_registry() -> None:
    """Convenience helper to wipe the global registry."""
    _REGISTRY.clear()
