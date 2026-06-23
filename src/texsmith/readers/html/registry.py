"""Lowering registry — the ``@reads`` decorator and its registry.

``@reads`` declares a handler that *returns* an IR node (or a sequence of IR
nodes) for a given HTML tag — never mutating the BeautifulSoup tree. The
registry keeps the mapping extensible so extensions can register their own
lowering without touching the core reader.

A lowering is selected by ``(level, tag)``: the reader walks the tree at a
known level (``BLOCK`` while collecting top-level/structural nodes, ``INLINE``
while gathering phrasing content) and asks the registry for the most specific
handler. Handlers are tried in registration order — earlier registrations win —
and a handler signals "not mine" by returning :data:`NotHandled`, letting the
reader fall through to the next candidate (and ultimately to a generic fallback
that never drops content silently).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import Tag

    from .context import ReadContext


class ReadLevel(Enum):
    """The structural level a lowering produces.

    A handler is consulted only at its own level: ``BLOCK`` handlers build
    block nodes (paragraphs, lists, figures, tables…), ``INLINE`` handlers
    build phrasing nodes (emphasis, links, code spans…). A few constructs are
    valid at either level (e.g. images, math, margin notes) and register for
    :data:`ReadLevel.ANY`.
    """

    BLOCK = auto()
    INLINE = auto()
    ANY = auto()


class _NotHandledType:
    """Sentinel returned by a lowering that declines an element.

    Distinct from ``None`` (which a handler may legitimately return to mean
    "this element lowers to nothing", e.g. a stripped anchor). Declining lets
    the reader try the next registered handler for the same tag.
    """

    _instance: _NotHandledType | None = None

    def __new__(cls) -> _NotHandledType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "NotHandled"


NotHandled = _NotHandledType()
"""Singleton sentinel; return it from a lowering to decline an element."""

# A lowering returns one IR node, a sequence of nodes, ``None`` (lowers to
# nothing), or :data:`NotHandled` (decline, try the next handler).
LoweringResult = "AnyNode | Sequence[AnyNode] | None | _NotHandledType"
Lowering = Callable[["Tag", "ReadContext"], Any]


@dataclass(frozen=True)
class ReaderRule:
    """A concrete lowering bound to one or more tags at a given level."""

    level: ReadLevel
    tags: tuple[str, ...]
    handler: Lowering
    name: str
    priority: int = 0


@dataclass
class ReaderRegistry:
    """Collects :class:`ReaderRule` instances indexed by ``(level, tag)``.

    Lookups return every candidate for a tag (at the requested level plus the
    ``ANY`` level), highest priority first then registration order. The reader
    walks the candidates, applying the first that does not return
    :data:`NotHandled`.
    """

    _rules: list[ReaderRule] = field(default_factory=list)

    def register(self, rule: ReaderRule) -> None:
        """Append ``rule`` to the registry (registration order is stable)."""
        self._rules.append(rule)

    def collect_from(self, owner: object) -> None:
        """Register every ``@reads``-decorated callable found on ``owner``.

        ``owner`` is typically a module; its public callables are scanned for
        the descriptor installed by :func:`reads`.
        """
        for attribute in dir(owner):
            handler = getattr(owner, attribute, None)
            if not callable(handler):
                continue
            definition = getattr(handler, "__reader_rule__", None)
            if isinstance(definition, _ReaderDefinition):
                self.register(definition.bind(handler))

    def candidates(self, tag: str, level: ReadLevel) -> tuple[ReaderRule, ...]:
        """Return lowerings for ``tag`` applicable at ``level`` (best first)."""
        matched = [
            rule
            for rule in self._rules
            if tag in rule.tags and (rule.level is level or rule.level is ReadLevel.ANY)
        ]
        matched.sort(key=lambda rule: -rule.priority)
        return tuple(matched)


@dataclass(frozen=True)
class _ReaderDefinition:
    """Descriptor installed on a callable by :func:`reads`."""

    level: ReadLevel
    tags: tuple[str, ...]
    priority: int = 0
    name: str | None = None

    def bind(self, handler: Lowering) -> ReaderRule:
        name = self.name or getattr(handler, "__name__", handler.__class__.__name__)
        return ReaderRule(
            level=self.level,
            tags=self.tags,
            handler=handler,
            name=name,
            priority=self.priority,
        )


def reads(
    *tags: str,
    level: ReadLevel = ReadLevel.BLOCK,
    priority: int = 0,
    name: str | None = None,
) -> Callable[[Lowering], Lowering]:
    """Declare ``handler`` as the lowering for ``tags`` at ``level``.

    The decorated callable *returns* an IR node (or sequence/``None``/
    :data:`NotHandled`) instead of mutating a soup. Higher ``priority`` wins
    when several handlers target the same tag.
    """
    definition = _ReaderDefinition(
        level=level,
        tags=tuple(tags),
        priority=priority,
        name=name,
    )

    def decorator(handler: Lowering) -> Lowering:
        handler.__reader_rule__ = definition  # type: ignore[attr-defined]
        return handler

    return decorator


__all__ = [
    "Lowering",
    "NotHandled",
    "ReadLevel",
    "ReaderRegistry",
    "ReaderRule",
    "reads",
]
