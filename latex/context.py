"""Rendering context primitives shared across the LaTeX pipeline."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, DefaultDict, Dict, Iterable, MutableMapping

from .exceptions import AssetMissingError


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .config import BookConfig
    from .formatter import LaTeXFormatter
    from .rules import RenderPhase


@dataclass(slots=True)
class DocumentState:
    """In-memory state accumulated while rendering a document."""

    abbreviations: Dict[str, str] = field(default_factory=dict)
    acronyms: Dict[str, tuple[str, str]] = field(default_factory=dict)
    glossary: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    snippets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    solutions: list[Dict[str, Any]] = field(default_factory=list)
    headings: list[Dict[str, Any]] = field(default_factory=list)
    exercise_counter: int = 0

    def remember_acronym(self, key: str, short: str, expanded: str) -> None:
        self.acronyms[key] = (short, expanded)

    def remember_abbreviation(self, key: str, text: str) -> None:
        self.abbreviations[key] = text

    def remember_glossary(self, key: str, entry: Dict[str, Any]) -> None:
        self.glossary[key] = entry

    def register_snippet(self, key: str, payload: Dict[str, Any]) -> None:
        self.snippets[key] = payload

    def add_solution(self, solution: Dict[str, Any]) -> None:
        self.solutions.append(solution)

    def add_heading(self, *, level: int, text: str, ref: str | None = None) -> None:
        self.headings.append({"level": level, "text": text, "ref": ref})

    def next_exercise(self) -> int:
        self.exercise_counter += 1
        return self.exercise_counter


@dataclass(slots=True)
class AssetRegistry:
    """Centralised registry for rendered assets."""

    output_root: Path
    assets_map: MutableMapping[str, Path] = field(default_factory=dict)
    copy_assets: bool = True

    def register(self, key: str, artefact: Path | str) -> Path:
        """Register a generated artefact and return its resolved path."""

        path = Path(artefact)
        if not path.is_absolute():
            if self.copy_assets:
                path = (self.output_root / path).resolve()
            else:
                path = Path(path)
        self.assets_map[key] = path
        return path

    def get(self, key: str) -> Path:
        """Retrieve a previously registered artefact."""

        try:
            return Path(self.assets_map[key])
        except KeyError as exc:
            raise AssetMissingError(f"Missing asset '{key}'") from exc

    def items(self) -> Iterable[tuple[str, Path]]:
        return ((k, Path(v)) for k, v in self.assets_map.items())


@dataclass
class RenderContext:
    """Shared context passed to every handler during rendering."""

    config: "BookConfig"
    formatter: "LaTeXFormatter"
    document: Any
    assets: AssetRegistry
    state: DocumentState = field(default_factory=DocumentState)
    runtime: Dict[str, Any] = field(default_factory=dict)
    phase: "RenderPhase | None" = None

    _processed_nodes: DefaultDict[int, set[int]] = field(
        default_factory=lambda: defaultdict(set), init=False
    )
    _skip_children: DefaultDict[int, set[int]] = field(
        default_factory=lambda: defaultdict(set), init=False
    )
    _persistent_runtime: Dict[str, Any] = field(default_factory=dict, init=False)

    def enter_phase(self, phase: "RenderPhase") -> None:
        """Mark the current phase and reset transient runtime data."""

        self.phase = phase
        self.runtime = dict(self._persistent_runtime)
        self._skip_children[phase.value].clear()

    def attach_runtime(self, **runtime: Any) -> None:
        """Attach ad-hoc data visible to handlers for the running phase."""

        self._persistent_runtime.update(runtime)
        self.runtime.update(runtime)

    def mark_processed(self, node: Any, *, phase: "RenderPhase | None" = None) -> None:
        """Flag a node as already transformed for the selected phase."""

        label = phase or self.phase
        if label is None:
            return
        self._processed_nodes[label.value].add(id(node))

    def is_processed(self, node: Any, *, phase: "RenderPhase | None" = None) -> bool:
        """Check whether a node has been processed in the given phase."""

        label = phase or self.phase
        if label is None:
            return False
        return id(node) in self._processed_nodes[label.value]

    def suppress_children(
        self, node: Any, *, phase: "RenderPhase | None" = None
    ) -> None:
        """Prevent traversal of node children for the active phase."""

        label = phase or self.phase
        if label is None:
            return
        self._skip_children[label.value].add(id(node))

    def should_skip_children(
        self, node: Any, *, phase: "RenderPhase | None" = None
    ) -> bool:
        """Check whether children should be skipped during traversal."""

        label = phase or self.phase
        if label is None:
            return False
        return id(node) in self._skip_children[label.value]
