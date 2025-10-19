"""Pipeline primitives shared by the LaTeX renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Protocol

from bs4.element import Tag


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .config import BookConfig
    from .formatters import LaTeXFormatter


class RenderPhase(Enum):
    """High-level phases for the LaTeX rendering pipeline."""

    PRE = auto()
    BLOCK = auto()
    POST = auto()


class StageCallable(Protocol):
    """Callable signature expected by rendering stages."""

    def __call__(
        self, soup: Tag, context: "RenderingContext", **runtime: Any
    ) -> Tag | None: ...


@dataclass
class RenderingContext:
    """Shared mutable context passed to each rendering stage."""

    config: "BookConfig"
    formatter: "LaTeXFormatter"
    output_path: Path
    assets_map: Dict[Any, Any]
    state: Dict[str, Any] = field(default_factory=dict)
    runtime: Dict[str, Any] = field(default_factory=dict)

    def update_runtime(self, **runtime: Any) -> None:
        """Attach per-render parameters to the context."""

        self.runtime = runtime

    def clear_runtime(self) -> None:
        """Reset transient runtime data."""

        self.runtime = {}


@dataclass(order=True)
class RenderStage:
    """Concrete rendering stage."""

    phase: RenderPhase
    priority: int
    name: str = field(compare=False)
    handler: StageCallable = field(compare=False)

    def __call__(self, soup: Tag, context: RenderingContext) -> None:
        """Execute the stage."""

        self.handler(soup, context, **context.runtime)


@dataclass(frozen=True)
class StageDefinition:
    """Definition attached to handler methods via decorator."""

    name: str
    phase: RenderPhase
    priority: int = 0

    def bind(self, handler: StageCallable) -> RenderStage:
        """Bind a definition to its callable."""

        return RenderStage(
            phase=self.phase,
            priority=self.priority,
            name=self.name,
            handler=handler,
        )


class RenderRegistry:
    """Registry used to collect stages before execution."""

    def __init__(self) -> None:
        self._stages: Dict[RenderPhase, List[RenderStage]] = {}

    def register(self, stage: RenderStage) -> None:
        """Register a stage and keep ordering stable."""

        stages = self._stages.setdefault(stage.phase, [])
        stages.append(stage)
        stages.sort()

    def iter_phase(self, phase: RenderPhase) -> Iterable[RenderStage]:
        """Iterate over stages attached to a specific phase."""

        return tuple(self._stages.get(phase, []))


class RenderPipeline:
    """Execution engine responsible for orchestrating stages."""

    def __init__(self, registry: RenderRegistry | None = None) -> None:
        self.registry = registry or RenderRegistry()

    def collect_from(self, instance: Any) -> None:
        """Collect decorated methods from an instance."""

        for attribute in dir(instance):
            handler = getattr(instance, attribute)
            definition = getattr(handler, "__render_stage__", None)
            if isinstance(definition, StageDefinition):
                self.registry.register(definition.bind(handler))

    def run_phase(
        self, phase: RenderPhase, soup: Tag, context: RenderingContext
    ) -> None:
        """Run all stages registered for a given phase."""

        for stage in self.registry.iter_phase(phase):
            stage(soup, context)


def render_stage(
    *, name: str | None = None, phase: RenderPhase, priority: int = 0
) -> Callable[[StageCallable], StageCallable]:
    """Decorator used to declare pipeline stages."""

    def decorator(handler: StageCallable) -> StageCallable:
        stage_name = name or handler.__name__
        setattr(
            handler, "__render_stage__", StageDefinition(stage_name, phase, priority)
        )
        return handler

    return decorator
