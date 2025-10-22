"""Declarative rule registry and execution engine for LaTeX rendering."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Protocol


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import Tag

    from .context import RenderContext


class RenderPhase(Enum):
    """High-level passes executed by the rendering engine."""

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
    """Protocol implemented by rule decorators."""

    def bind(self, handler: RuleCallable) -> RenderRule: ...


DOCUMENT_NODE = "__document__"


@dataclass(order=True)
class RenderRule:
    """Concrete rendering rule registered in the engine."""

    priority: int
    phase: RenderPhase = field(compare=False)
    tags: tuple[str, ...] = field(compare=False)
    name: str = field(compare=False)
    handler: RuleCallable = field(compare=False)
    auto_mark: bool = field(default=True, compare=False)
    nestable: bool = field(default=True, compare=False)
    after_children: bool = field(default=False, compare=False)

    def applies_to_document(self) -> bool:
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
        )


class RenderRegistry:
    """Container used to gather render rules before execution."""

    def __init__(self) -> None:
        self._rules: dict[RenderPhase, dict[str, list[RenderRule]]] = {}

    def register(self, rule: RenderRule) -> None:
        """Register a rule for later execution."""

        phase_bucket = self._rules.setdefault(rule.phase, {})
        if rule.applies_to_document():
            tag_bucket = phase_bucket.setdefault(DOCUMENT_NODE, [])
            tag_bucket.append(rule)
            tag_bucket.sort()
            return

        for tag in rule.tags:
            tag_bucket = phase_bucket.setdefault(tag, [])
            tag_bucket.append(rule)
            tag_bucket.sort()

    def iter_phase(self, phase: RenderPhase) -> Iterable[RenderRule]:
        """Iterate over rules for the provided phase."""

        buckets = self._rules.get(phase, {})
        for tag_rules in buckets.values():
            yield from tag_rules

    def rules_for_phase(self, phase: RenderPhase) -> dict[str, tuple[RenderRule, ...]]:
        """Return the rule mapping for the requested phase."""

        phase_bucket = self._rules.get(phase, {})
        return {tag: tuple(rules) for tag, rules in phase_bucket.items()}


def renders(
    *tags: str,
    phase: RenderPhase = RenderPhase.BLOCK,
    priority: int = 0,
    name: str | None = None,
    auto_mark: bool = True,
    nestable: bool = True,
    after_children: bool = False,
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
    )

    def decorator(handler: RuleCallable) -> RuleCallable:
        handler.__render_rule__ = definition
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

    def _execute_rule(
        self, rule: RenderRule, node: Any, context: RenderContext
    ) -> None:
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
