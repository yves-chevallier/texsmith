"""Front-matter custom counters: declaration, validation and allocation.

Technical documents number series LaTeX knows nothing about — findings,
requirements, bugs, risks. A ``counters:`` section in the YAML front matter
declares such a series; the body marks each item with ``#{prefix:key}`` (or any
``{#prefix:key}`` attribute list) and references it with ``@prefix:key``.

This module owns the declaration side (pydantic validation of the front-matter
payload into frozen :class:`CounterSpec` values) and the allocation side (a
process-wide, thread-safe :class:`CounterRegistry` handing out numbers in
document order). Numbers are deliberately allocated once per conversion batch
so the documents of a multi-file build continue a single series instead of
restarting; :func:`clear_registry` resets it between batches.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from threading import Lock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CounterValidationError(ValueError):
    """Raised when the front-matter ``counters`` section is invalid."""


#: Prefixes conventionally used by regular labels (``{#sec:intro}``); a custom
#: counter may not shadow them or ``@sec:intro`` would stop being a section.
RESERVED_PREFIXES = frozenset({"sec", "fig", "tbl", "eq", "lst", "app", "chap", "part", "note"})

#: Character classes shared by every piece of syntax naming a counter: the
#: front-matter keys, the ``#{prefix:key}`` markers, the ``{#prefix:key}``
#: attribute lists and the ``@prefix:key`` references.
PREFIX_PATTERN = r"[A-Za-z][A-Za-z0-9_-]*"
KEY_PATTERN = r"[A-Za-z0-9_][A-Za-z0-9_.:-]*"

PREFIX_RE = re.compile(rf"^{PREFIX_PATTERN}$")


class CounterSpec(BaseModel):
    """A counter series declared in the front matter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prefix: str
    name: str = Field(min_length=1)
    format: str = "{n}"
    start: int = 1

    def render(self, value: int, key: str) -> str:
        """Format ``value`` for the item ``key`` according to ``format``."""
        return self.format.format(n=value, prefix=self.prefix, key=key)


def parse_front_matter_counters(
    metadata: Mapping[str, Any] | None,
) -> dict[str, CounterSpec]:
    """Validate and normalise the ``counters:`` front-matter section."""
    if not isinstance(metadata, Mapping):
        return {}

    raw = metadata.get("counters")
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise CounterValidationError(
            "Front-matter 'counters' must be a mapping of prefix -> counter options."
        )

    specs: dict[str, CounterSpec] = {}
    for raw_prefix, value in raw.items():
        prefix = str(raw_prefix).strip()
        if not PREFIX_RE.match(prefix):
            raise CounterValidationError(
                f"Invalid counter prefix '{prefix}': expected [A-Za-z][A-Za-z0-9_-]*."
            )
        if prefix in RESERVED_PREFIXES:
            raise CounterValidationError(
                f"Counter prefix '{prefix}' is reserved for regular labels."
            )
        if not isinstance(value, Mapping):
            raise CounterValidationError(
                f"Counter '{prefix}' must be a mapping, got {type(value).__name__}."
            )
        try:
            spec = CounterSpec(prefix=prefix, **dict(value))
        except (TypeError, ValidationError) as exc:
            # ``TypeError``: the mapping itself smuggles a ``prefix`` key.
            raise CounterValidationError(f"Invalid counter '{prefix}': {exc}") from exc
        # Fail at parse time rather than mid-document: a bad format string would
        # otherwise only surface on the first marker that uses it.
        try:
            spec.render(spec.start, "probe")
        except (KeyError, IndexError, ValueError) as exc:
            raise CounterValidationError(
                f"Invalid format for counter '{prefix}': {spec.format!r} ({exc})."
            ) from exc

        specs[prefix] = spec

    return specs


@dataclass(slots=True)
class CounterRegistry:
    """Thread-safe allocator handing out counter values in document order."""

    _specs: dict[str, CounterSpec] = field(default_factory=dict)
    _values: dict[str, dict[str, int]] = field(default_factory=dict)
    _claimed: dict[str, set[str]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def declare(self, specs: Mapping[str, CounterSpec]) -> None:
        """Merge counter declarations into the registry; the last one wins."""
        if not specs:
            return
        with self._lock:
            self._specs.update(specs)

    def spec(self, prefix: str) -> CounterSpec | None:
        """Return the declaration for ``prefix``, or ``None`` when undeclared."""
        with self._lock:
            return self._specs.get(prefix)

    def prepare(self, prefix: str, key: str) -> int:
        """Reserve the value of ``prefix:key`` without claiming its definition.

        A pre-pass over a whole MkDocs site fixes the numbering in nav order so
        a reference on the first page resolves to an item defined on the last
        one; the definition itself is still claimed later, when the page that
        carries it is converted.
        """
        with self._lock:
            return self._assign(prefix, key)

    def allocate(self, prefix: str, key: str) -> tuple[int, bool]:
        """Return ``(value, is_duplicate)`` for ``prefix:key``.

        A key claimed twice keeps its first value and is reported as a
        duplicate; a merely :meth:`prepare` d one is not a duplicate — it is the
        definition the pre-pass was reserving a number for.
        """
        with self._lock:
            claimed = self._claimed.setdefault(prefix, set())
            is_duplicate = key in claimed
            value = self._assign(prefix, key)
            claimed.add(key)
            return value, is_duplicate

    def _assign(self, prefix: str, key: str) -> int:
        """Return the value of ``prefix:key``, allocating it on first sight."""
        spec = self._specs.get(prefix)
        if spec is None:
            raise KeyError(prefix)
        assigned = self._values.setdefault(prefix, {})
        existing = assigned.get(key)
        if existing is not None:
            return existing
        value = spec.start + len(assigned)
        assigned[key] = value
        return value

    def lookup(self, prefix: str, key: str) -> int | None:
        """Return the value allocated to ``prefix:key``, or ``None``."""
        with self._lock:
            return self._values.get(prefix, {}).get(key)

    def render(self, prefix: str, key: str) -> str | None:
        """Return the formatted number for ``prefix:key``, or ``None``."""
        with self._lock:
            spec = self._specs.get(prefix)
            value = self._values.get(prefix, {}).get(key)
            if spec is None or value is None:
                return None
        return spec.render(value, key)

    def clear(self) -> None:
        """Reset the registry to its initial empty state."""
        with self._lock:
            self._specs.clear()
            self._values.clear()
            self._claimed.clear()

    def snapshot(self) -> dict[str, dict[str, int]]:
        """Return a copy of the allocated values, keyed by prefix then item key."""
        with self._lock:
            return {prefix: dict(values) for prefix, values in self._values.items()}


_REGISTRY = CounterRegistry()


def get_registry() -> CounterRegistry:
    """Return the global counter registry."""
    return _REGISTRY


def clear_registry() -> None:
    """Convenience helper to wipe the global registry."""
    _REGISTRY.clear()


__all__ = [
    "KEY_PATTERN",
    "PREFIX_PATTERN",
    "PREFIX_RE",
    "RESERVED_PREFIXES",
    "CounterRegistry",
    "CounterSpec",
    "CounterValidationError",
    "clear_registry",
    "get_registry",
    "parse_front_matter_counters",
]
