"""Rendering context primitives shared across the LaTeX pipeline."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, MutableMapping
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
import warnings

from slugify import slugify

from .exceptions import AssetMissingError


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.adapters.latex.formatter import LaTeXFormatter

    from .config import BookConfig
    from .rules import RenderPhase


@dataclass(slots=True)
class DocumentState:
    """In-memory state accumulated while rendering a document."""

    abbreviations: dict[str, str] = field(default_factory=dict)
    acronym_keys: dict[str, str] = field(default_factory=dict)
    acronyms: dict[str, tuple[str, str]] = field(default_factory=dict)
    glossary: dict[str, dict[str, Any]] = field(default_factory=dict)
    snippets: dict[str, dict[str, Any]] = field(default_factory=dict)
    solutions: list[dict[str, Any]] = field(default_factory=list)
    headings: list[dict[str, Any]] = field(default_factory=list)
    exercise_counter: int = 0
    has_index_entries: bool = False
    requires_shell_escape: bool = False
    counters: dict[str, int] = field(default_factory=dict)
    bibliography: dict[str, dict[str, Any]] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
    _citation_index: set[str] = field(default_factory=set, init=False, repr=False)
    footnotes: dict[str, str] = field(default_factory=dict)
    index_entries: list[tuple[str, ...]] = field(default_factory=list)
    pygments_styles: dict[str, str] = field(default_factory=dict)
    script_usage: list[dict[str, Any]] = field(default_factory=list)
    fallback_summary: list[dict[str, Any]] = field(default_factory=list)
    callouts_used: bool = False

    def remember_acronym(self, term: str, description: str) -> str:
        """Register an acronym definition keyed by a normalised identifier."""
        return self.remember_abbreviation(term=term, description=description)

    def remember_abbreviation(self, term: str, description: str) -> str:
        """Track abbreviation definitions while ensuring consistency."""
        normalised_term = term.strip()
        normalised_description = description.strip()
        if not normalised_term or not normalised_description:
            return ""

        existing_description = self.abbreviations.get(normalised_term)
        if existing_description is not None:
            if existing_description != normalised_description:
                warnings.warn(
                    (
                        f"Inconsistent acronym definition for '{normalised_term}': "
                        f"'{existing_description}' vs '{normalised_description}'"
                    ),
                    stacklevel=2,
                )
            return self.acronym_keys.get(normalised_term, "")

        key = self._generate_acronym_key(normalised_term)
        self.abbreviations[normalised_term] = normalised_description
        self.acronym_keys[normalised_term] = key
        self.acronyms[key] = (normalised_term, normalised_description)
        return key

    def _generate_acronym_key(self, term: str) -> str:
        """Produce a unique key suitable for the glossaries package."""
        slug = slugify(term, separator="", lowercase=False)
        if not slug:
            slug = "acronym"
        candidate = slug
        suffix = 2
        while candidate in self.acronyms:
            candidate = f"{slug}{suffix}"
            suffix += 1
        return candidate

    def remember_glossary(self, key: str, entry: dict[str, Any]) -> None:
        """Record a glossary entry keyed by its identifier."""
        self.glossary[key] = entry

    def register_snippet(self, key: str, payload: dict[str, Any]) -> None:
        """Cache snippet metadata to render later in the pipeline."""
        self.snippets[key] = payload

    def add_solution(self, solution: dict[str, Any]) -> None:
        """Append a solution block encountered during parsing."""
        self.solutions.append(solution)

    def add_heading(self, *, level: int, text: str, ref: str | None = None) -> None:
        """Track heading metadata to power table-of-contents generation."""
        self.headings.append({"level": level, "text": text, "ref": ref})

    def next_exercise(self) -> int:
        """Increment and return the exercise counter."""
        counter = self.next_counter("exercise")
        self.exercise_counter = counter
        return counter

    def next_counter(self, key: str = "default") -> int:
        """Increment and return the named counter."""
        value = self.counters.get(key, 0) + 1
        self.counters[key] = value
        return value

    def peek_counter(self, key: str = "default") -> int:
        """Return the current value of the named counter without modifying it."""
        return self.counters.get(key, 0)

    def reset_counter(self, key: str) -> None:
        """Clear the named counter if it has been tracked."""
        self.counters.pop(key, None)

    def record_citation(self, key: str) -> None:
        """Track citation keys used throughout the document."""
        if key in self._citation_index:
            return
        self._citation_index.add(key)
        self.citations.append(key)


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
            path = (self.output_root / path).resolve() if self.copy_assets else Path(path)
        self.assets_map[key] = path
        return path

    def lookup(self, key: str) -> Path | None:
        """Return a previously registered artefact when available."""
        stored = self.assets_map.get(key)
        return Path(stored) if stored is not None else None

    def get(self, key: str) -> Path:
        """Retrieve a previously registered artefact."""
        try:
            return Path(self.assets_map[key])
        except KeyError as exc:
            raise AssetMissingError(f"Missing asset '{key}'") from exc

    def items(self) -> Iterable[tuple[str, Path]]:
        """Iterate over registered assets yielding key/path pairs."""
        return ((k, Path(v)) for k, v in self.assets_map.items())

    def latex_path(self, path: Path | str) -> str:
        """Return a LaTeX-friendly path for an artefact."""
        candidate = Path(path)
        if not candidate.is_absolute():
            return candidate.as_posix()

        output_dir = self.output_root.parent
        try:
            reference = candidate.relative_to(output_dir)
        except ValueError:
            try:
                reference = Path(os.path.relpath(candidate, output_dir))
            except ValueError:
                reference = candidate

        return reference.as_posix()


@dataclass
class RenderContext:
    """Shared context passed to every handler during rendering."""

    config: BookConfig
    formatter: LaTeXFormatter
    document: Any
    assets: AssetRegistry
    state: DocumentState = field(default_factory=DocumentState)
    runtime: dict[str, Any] = field(default_factory=dict)
    phase: RenderPhase | None = None

    _processed_nodes: defaultdict[int, set[int]] = field(
        default_factory=lambda: defaultdict(set), init=False
    )
    _skip_children: defaultdict[int, set[int]] = field(
        default_factory=lambda: defaultdict(set), init=False
    )
    _persistent_runtime: dict[str, Any] = field(default_factory=dict, init=False)

    def enter_phase(self, phase: RenderPhase) -> None:
        """Mark the current phase and reset transient runtime data."""
        self.phase = phase
        self.runtime = dict(self._persistent_runtime)
        self._skip_children[phase.value].clear()

    def attach_runtime(self, **runtime: Any) -> None:
        """Attach ad-hoc data visible to handlers for the running phase."""
        self._persistent_runtime.update(runtime)
        self.runtime.update(runtime)

    def mark_processed(self, node: Any, *, phase: RenderPhase | None = None) -> None:
        """Flag a node as already transformed for the selected phase."""
        label = phase or self.phase
        if label is None:
            return
        self._processed_nodes[label.value].add(id(node))

    def is_processed(self, node: Any, *, phase: RenderPhase | None = None) -> bool:
        """Check whether a node has been processed in the given phase."""
        label = phase or self.phase
        if label is None:
            return False
        return id(node) in self._processed_nodes[label.value]

    def suppress_children(self, node: Any, *, phase: RenderPhase | None = None) -> None:
        """Prevent traversal of node children for the active phase."""
        label = phase or self.phase
        if label is None:
            return
        self._skip_children[label.value].add(id(node))

    def should_skip_children(self, node: Any, *, phase: RenderPhase | None = None) -> bool:
        """Check whether children should be skipped during traversal."""
        label = phase or self.phase
        if label is None:
            return False
        return id(node) in self._skip_children[label.value]
