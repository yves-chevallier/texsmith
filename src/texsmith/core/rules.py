"""Rule declaration and execution engine for the LaTeX renderer.

This module implements the rule-based architecture that powers Texsmith's
HTML-to-LaTeX pipeline. Handlers declare their intent via the ``@renders``
decorator, which records structural metadata (phase, priority, targeted tags).
At runtime the :class:`RenderEngine` collects those declarations, organises them
per :class:`RenderPhase`, and walks the BeautifulSoup DOM ensuring that each
pass is executed in a predictable, stable order.

Architecture

`Declaration layer`
: ``@renders`` stores a lightweight :class:`RuleDefinition` on every handler.

`Registry layer`
: :class:`RenderRegistry` collates definitions into sortable :class:`RenderRule`
  instances grouped by phase/tag.

`Execution layer`
: :class:`RenderEngine` coordinates multi-pass traversal using the private
  :class:`_DOMVisitor` to apply handlers depth-first while respecting
  auto-marking and child-suppression semantics.

This separation keeps rule authors focused on transformations while the engine
handles ordering, deduplication, and orchestration concerns.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Protocol, cast


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import Tag

    from .context import RenderContext


class RenderPhase(Enum):
    """Ordered passes executed while mutating the parsed HTML tree.

    The renderer performs multiple sweeps over the DOM instead of a single
    monolithic traversal. Each phase isolates a category of mutations so that
    earlier transformations stabilise before later ones begin. This drastically
    reduces coupling between handlers and makes ordering guarantees explicit.

    Phases progress from coarse structural edits to fine-grained formatting:

    ``PRE``
    : normalise the tree and discard unwanted nodes before any heavy lifting
      occurs.

    ``BLOCK``
    : build block-level LaTeX (paragraphs, lists, figures) once the structure is
      stable.

    ``INLINE``
    : apply inline formatting after blocks have established their final shape.

    ``POST``
    : run cleanup or bookkeeping steps that depend on previous phases, such as
      final numbering, synthetic nodes, or state aggregation.
    """

    PRE = auto()
    """DOM normalisation pass: strip/reshape nodes before structural work begins."""

    BLOCK = auto()
    """Block transformation pass: convert paragraphs, lists, figures, etc."""

    INLINE = auto()
    """Inline formatting pass: apply emphasis, links, inline math once blocks exist."""

    POST = auto()
    """Finalisation pass: run cleanup that depends on earlier transformations."""


RuleCallable = Callable[[Any, "RenderContext"], None]


class RuleFactory(Protocol):
    """Protocol implemented by rule decorators.

    Decorators return lightweight factory objects instead of immediately
    constructing :class:`RenderRule` instances. This indirection lets us bind
    metadata once (at decoration time) while deferring handler resolution until
    the registry collects rules. The factory pattern keeps the decorator API
    ergonomic, avoids premature instantiation, and allows the same definition
    to be rebound for different callables (e.g. class/static methods) without
    duplicating registration logic.
    """

    def bind(self, handler: RuleCallable) -> RenderRule:
        """Create a concrete render rule for the decorated handler."""
        ...


DOCUMENT_NODE = "__document__"


@dataclass
class RenderRule:
    """Concrete rendering rule registered in the engine."""

    priority: int
    phase: RenderPhase
    tags: tuple[str, ...]
    name: str
    handler: RuleCallable
    auto_mark: bool = True
    nestable: bool = True
    after_children: bool = False
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()

    def applies_to_document(self) -> bool:
        """Return True when the rule targets the synthetic document node."""
        return self.tags == (DOCUMENT_NODE,)


@dataclass(frozen=True)
class RuleDefinition:
    """Descriptor installed on handler callables by the decorator."""

    phase: RenderPhase
    tags: tuple[str, ...]
    priority: int = 0
    name: str | None = None
    auto_mark: bool = True
    nestable: bool = True
    after_children: bool = False
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()

    def bind(self, handler: RuleCallable) -> RenderRule:
        """Create a concrete rule instance bound to the callable."""
        name = self.name or getattr(handler, "__name__", handler.__class__.__name__)
        return RenderRule(
            phase=self.phase,
            tags=self.tags,
            priority=self.priority,
            name=name,
            handler=handler,
            auto_mark=self.auto_mark,
            nestable=self.nestable,
            after_children=self.after_children,
            before=self.before,
            after=self.after,
        )


class RenderRegistry:
    """Container used to gather render rules before execution."""

    def __init__(self) -> None:
        self._rules: dict[RenderPhase, dict[str, list[RenderRule]]] = {}
        self._rule_sources: dict[int, str] = {}

    def register(self, rule: RenderRule) -> None:
        """Register a rule for later execution."""
        phase_bucket = self._rules.setdefault(rule.phase, {})
        self._rule_sources.setdefault(id(rule), rule.name)
        if rule.applies_to_document():
            tag_bucket = phase_bucket.setdefault(DOCUMENT_NODE, [])
            tag_bucket.append(rule)
            tag_bucket[:] = self._sort_rules(tag_bucket)
            return

        for tag in rule.tags:
            tag_bucket = phase_bucket.setdefault(tag, [])
            tag_bucket.append(rule)
            tag_bucket[:] = self._sort_rules(tag_bucket)

    def iter_phase(self, phase: RenderPhase) -> Iterable[RenderRule]:
        """Iterate over rules for the provided phase."""
        buckets = self._rules.get(phase, {})
        for tag_rules in buckets.values():
            yield from tag_rules

    def rules_for_phase(self, phase: RenderPhase) -> dict[str, tuple[RenderRule, ...]]:
        """Return the rule mapping for the requested phase."""
        phase_bucket = self._rules.get(phase, {})
        return {tag: tuple(rules) for tag, rules in phase_bucket.items()}

    def describe(self) -> list[dict[str, object]]:
        """Return a serialisable snapshot of the registered rules."""
        entries: list[dict[str, object]] = []
        for phase in RenderPhase:
            for tag, rules in sorted(self.rules_for_phase(phase).items(), key=lambda item: item[0]):
                for order, rule in enumerate(rules):
                    entries.append(
                        {
                            "phase": phase.name,
                            "tag": tag,
                            "name": rule.name,
                            "priority": rule.priority,
                            "before": list(rule.before),
                            "after": list(rule.after),
                            "order": order,
                        }
                    )
        return entries

    def _sort_rules(self, rules: list[RenderRule]) -> list[RenderRule]:
        """Return rules ordered deterministically using before/after constraints."""
        if len(rules) <= 1:
            return list(rules)

        name_to_index: dict[str, int] = {}
        for index, rule in enumerate(rules):
            name_to_index.setdefault(rule.name, index)

        adjacency: dict[int, set[int]] = {index: set() for index in range(len(rules))}
        indegree: dict[int, int] = dict.fromkeys(range(len(rules)), 0)

        def _add_edge(source: int, target: int) -> None:
            if target in adjacency[source]:
                return
            adjacency[source].add(target)
            indegree[target] += 1

        for current_index, rule in enumerate(rules):
            for target_name in rule.before:
                target_index = name_to_index.get(target_name)
                if target_index is not None:
                    _add_edge(current_index, target_index)
            for target_name in rule.after:
                target_index = name_to_index.get(target_name)
                if target_index is not None:
                    _add_edge(target_index, current_index)

        queue: deque[int] = deque(
            sorted(
                (index for index, count in indegree.items() if count == 0),
                key=lambda idx: (rules[idx].priority, rules[idx].name, idx),
            )
        )
        ordered: list[int] = []

        while queue:
            current = queue.popleft()
            ordered.append(current)
            for neighbour in sorted(
                adjacency[current], key=lambda idx: (rules[idx].priority, rules[idx].name, idx)
            ):
                indegree[neighbour] -= 1
                if indegree[neighbour] == 0:
                    queue.append(neighbour)

            queue = deque(
                sorted(queue, key=lambda idx: (rules[idx].priority, rules[idx].name, idx))
            )

        if len(ordered) != len(rules):  # pragma: no cover - defensive
            cycle_names = sorted(
                rule.name for index, rule in enumerate(rules) if index not in ordered
            )
            raise RuntimeError(
                "Cyclic render rule dependencies detected: " + ", ".join(cycle_names)
            )

        return [rules[index] for index in ordered]


def renders(
    *tags: str,
    phase: RenderPhase = RenderPhase.BLOCK,
    priority: int = 0,
    name: str | None = None,
    auto_mark: bool = True,
    nestable: bool = True,
    after_children: bool = False,
    before: Iterable[str] = (),
    after: Iterable[str] = (),
) -> Callable[[RuleCallable], RuleCallable]:
    """Decorator used to register element handlers."""
    selected_tags = tags or (DOCUMENT_NODE,)
    definition = RuleDefinition(
        phase=phase,
        tags=tuple(selected_tags),
        priority=priority,
        name=name,
        auto_mark=auto_mark,
        nestable=nestable,
        after_children=after_children,
        before=tuple(before),
        after=tuple(after),
    )

    def decorator(handler: RuleCallable) -> RuleCallable:
        cast(Any, handler).__render_rule__ = definition
        return handler

    return decorator


class RenderEngine:
    """Execution engine that orchestrates the registered rules."""

    def __init__(self, registry: RenderRegistry | None = None) -> None:
        self.registry = registry or RenderRegistry()

    def collect_from(self, owner: Any) -> None:
        """Collect decorated callables from an object or module."""
        for attribute in dir(owner):
            handler = getattr(owner, attribute)
            definition = getattr(handler, "__render_rule__", None)
            if definition is None and hasattr(handler, "__func__"):
                definition = getattr(handler.__func__, "__render_rule__", None)
            if isinstance(definition, RuleDefinition):
                self.registry.register(definition.bind(handler))

    def register(self, handler: RuleCallable) -> None:
        """Register a standalone callable decorated with ``@renders``."""
        definition = getattr(handler, "__render_rule__", None)
        if not isinstance(definition, RuleDefinition):
            msg = "Handler must be decorated with @renders"
            raise TypeError(msg)
        self.registry.register(definition.bind(handler))

    def run(self, root: Tag, context: RenderContext) -> None:
        """Execute all registered rules against the provided DOM root."""
        for phase in RenderPhase:
            context.enter_phase(phase)
            phase_rules = self.registry.rules_for_phase(phase)
            document_rules = phase_rules.get(DOCUMENT_NODE, ())

            for rule in document_rules:
                self._execute_rule(rule, root, context)

            visitor = _DOMVisitor(phase, phase_rules, context)
            visitor.walk(root)

    def _execute_rule(self, rule: RenderRule, node: Any, context: RenderContext) -> None:
        """Execute a rule against a specific node applying bookkeeping."""
        if rule.auto_mark and context.is_processed(node):
            return
        rule.handler(node, context)
        if rule.auto_mark:
            context.mark_processed(node)
        if not rule.nestable:
            context.suppress_children(node)


class _DOMVisitor:
    """Depth-first visitor applying rules by tag while traversing the DOM tree."""

    def __init__(
        self,
        phase: RenderPhase,
        rules_by_tag: dict[str, tuple[RenderRule, ...]],
        context: RenderContext,
    ) -> None:
        self.phase = phase
        self.rules_by_tag = rules_by_tag
        self.context = context

    def walk(self, node: Tag) -> None:
        """Traverse descendants depth-first and apply matching rules."""
        self._dispatch(node, after_children=False)
        if self.context.should_skip_children(node, phase=self.phase):
            return

        # Copy the children list to avoid concurrent modification issues
        for child in list(getattr(node, "children", ())):
            # Only Tags should be traversed recursively
            if getattr(child, "name", None):
                self.walk(child)

        self._dispatch(node, after_children=True)

    def _dispatch(self, node: Tag, *, after_children: bool) -> None:
        """Dispatch node to registered rules for its tag name."""
        tag_name = getattr(node, "name", None)
        if not tag_name:
            return

        for rule in self.rules_by_tag.get(tag_name, ()):
            if rule.after_children != after_children:
                continue
            if rule.tags == (DOCUMENT_NODE,):
                # Document handlers already executed
                continue
            if rule.auto_mark and self.context.is_processed(node):
                continue
            rule.handler(node, self.context)
            if rule.auto_mark:
                self.context.mark_processed(node)
            if not rule.nestable:
                self.context.suppress_children(node)
