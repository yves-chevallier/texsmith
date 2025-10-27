"""Template orchestration helpers exposed by the TeXSmith API.

Architecture
: `TemplateSession` owns lifecycle management: it accepts documents, applies
  metadata overrides, and delegates aggregation to :class:`TemplateRenderer`.
: `TemplateRenderer` combines conversion bundles into slot-aware LaTeX output,
  copies template assets, and prepares the final context consumed by wrappers.
: `TemplateOptions` is a thin wrapper around a mutable mapping that keeps
  user-supplied overrides isolated from the template defaults. Its API is
  intentionally dictionary-like to integrate smoothly with CLI parsing.
: `TemplateRenderResult` captures the products of a render pass, including
  computed context, bibliography location, and shell-escape requirements so
  downstream tools can decide how to compile the LaTeX output.

Implementation Rationale
: Splitting lifecycle coordination (`TemplateSession`) from rendering concerns
  (`TemplateRenderer`) keeps slot aggregation logic in a single place and
  reduces duplication across front ends.
: Options are separated from documents to prevent accidental mutation of the
  default template metadata. Copy semantics are explicit, enabling safe reuse of
  sessions with different overrides.

Usage Example
:
    >>> from types import SimpleNamespace
    >>> from texsmith.api.templates import TemplateSession
    >>> from texsmith.templates import TemplateRuntime, TemplateSlot
    >>> dummy_info = SimpleNamespace(attributes={"cover_color": "indigo"})
    >>> dummy_template = SimpleNamespace(info=dummy_info)
    >>> runtime = TemplateRuntime(
    ...     instance=dummy_template,
    ...     name="demo",
    ...     engine=None,
    ...     requires_shell_escape=False,
    ...     slots={"mainmatter": TemplateSlot(default=True)},
    ...     default_slot="mainmatter",
    ...     formatter_overrides={},
    ...     base_level=None,
    ... )
    >>> session = TemplateSession(runtime=runtime)
    >>> session.get_default_options().to_dict()["cover_color"]
    'indigo'
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..context import DocumentState
from ..core.conversion.debug import ensure_emitter
from ..core.conversion.renderer import TemplateRenderer
from ..core.diagnostics import DiagnosticEmitter
from ..templates import TemplateError, TemplateRuntime, load_template_runtime
from .document import Document
from .pipeline import RenderSettings, convert_documents


__all__ = [
    "TemplateOptions",
    "TemplateRenderResult",
    "TemplateSession",
    "get_template",
]


@dataclass(slots=True)
class TemplateOptions:
    """Mutable mapping of template-level overrides."""

    _values: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError as exc:  # pragma: no cover - attribute passthrough
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_values":
            object.__setattr__(self, name, value)
        else:
            self._values[name] = value

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of the underlying values."""
        return copy.deepcopy(self._values)

    def copy(self) -> TemplateOptions:
        """Return a deep copy of the option set."""
        return TemplateOptions(self.to_dict())

    def update(self, values: Mapping[str, Any] | None = None, **extra: Any) -> None:
        """Update the option set in-place."""
        if values:
            self._values.update(values)
        if extra:
            self._values.update(extra)


@dataclass(slots=True)
class TemplateRenderResult:
    """Artifacts yielded by a :class:`TemplateSession` render pass."""

    main_tex_path: Path
    fragment_paths: list[Path]
    context: dict[str, Any]
    template_runtime: TemplateRuntime
    document_state: DocumentState
    bibliography_path: Path | None
    template_engine: str | None
    requires_shell_escape: bool

    @property
    def has_bibliography(self) -> bool:
        """Indicate whether a bibliography was generated."""
        return bool(self.bibliography_path)


class TemplateSession:
    """Manage template state while delegating rendering to :class:`TemplateRenderer`."""

    def __init__(
        self,
        runtime: TemplateRuntime,
        *,
        settings: RenderSettings | None = None,
        emitter: DiagnosticEmitter | None = None,
    ) -> None:
        self.runtime = runtime
        attributes = runtime.instance.info.attributes if runtime.instance else {}
        self._options = TemplateOptions(copy.deepcopy(attributes))
        self._default_options = TemplateOptions(copy.deepcopy(attributes))
        self._documents: list[Document] = []
        self._bibliography_files: list[Path] = []
        self.settings = settings.copy() if settings else RenderSettings()
        self.emitter = ensure_emitter(emitter)

    def _prepare_document(self, document: Document) -> Document:
        """Return a document copy with template overrides applied."""
        overrides_dict = self._options.to_dict()
        if not overrides_dict:
            return document.copy()

        prepared = document.copy()
        front_matter: dict[str, Any] = dict(prepared.front_matter)
        template_section = front_matter.setdefault("template", {})
        if not isinstance(template_section, dict):
            template_section = dict(template_section)
            front_matter["template"] = template_section
        template_section.update(overrides_dict)
        prepared.set_front_matter(front_matter)
        return prepared

    def _collect_option_overrides(self) -> dict[str, Any]:
        """Compute overrides that differ from the template defaults."""
        current = self._options.to_dict()
        baseline = self._default_options.to_dict()

        def _diff(current_map: Mapping[str, Any], baseline_map: Mapping[str, Any]) -> dict[str, Any]:
            overrides: dict[str, Any] = {}
            for key, value in current_map.items():
                baseline_value = baseline_map.get(key)
                if isinstance(value, Mapping) and isinstance(baseline_value, Mapping):
                    nested = _diff(value, baseline_value)
                    if nested:
                        overrides[key] = nested
                elif value != baseline_value:
                    overrides[key] = value
            return overrides

        return _diff(current, baseline)

    def get_default_options(self) -> TemplateOptions:
        """Return a copy of the default template options."""
        return self._default_options.copy()

    def set_options(self, options: TemplateOptions | Mapping[str, Any]) -> None:
        """Replace the current template overrides."""
        if isinstance(options, TemplateOptions):
            self._options = options.copy()
        else:
            self._options = TemplateOptions(dict(options))

    def update_options(self, values: Mapping[str, Any] | None = None, **extra: Any) -> None:
        """Update the current template overrides."""
        self._options.update(values, **extra)

    def add_bibliography(self, *paths: Path) -> None:
        """Register bibliography files applied to all documents."""
        for path in paths:
            resolved = Path(path)
            if resolved not in self._bibliography_files:
                self._bibliography_files.append(resolved)

    def add_document(
        self,
        document: Document,
        *,
        slot: str | None = None,
        selector: str | None = None,
        include_document: bool | None = None,
    ) -> Document:
        """Register a document for rendering."""
        doc = document.copy()
        if slot is not None:
            doc.assign_slot(slot, selector=selector, include_document=include_document)
        self._documents.append(doc)
        return doc

    @property
    def documents(self) -> Sequence[Document]:
        """Return the registered documents."""
        return tuple(self._documents)

    def render(self, output_dir: Path) -> TemplateRenderResult:
        """Render the registered documents into a LaTeX project."""
        if not self._documents:
            raise ValueError("At least one document must be added before rendering.")

        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        prepared_documents = [self._prepare_document(document) for document in self._documents]

        bundle = convert_documents(
            prepared_documents,
            output_dir=output_dir,
            settings=self.settings,
            emitter=self.emitter,
            bibliography_files=self._bibliography_files,
            template=self.runtime.name,
            template_runtime=self.runtime,
            wrap_document=False,
            write_fragments=False,
        )

        renderer = TemplateRenderer(self.runtime, emitter=self.emitter)
        try:
            rendered = renderer.render(
                bundle,
                output_dir=output_dir,
                overrides=self._collect_option_overrides(),
                copy_assets=self.settings.copy_assets,
            )
        except TemplateError as exc:
            message = str(exc)
            self.emitter.error(message, exc)
            raise

        return TemplateRenderResult(
            main_tex_path=rendered.main_tex_path,
            fragment_paths=rendered.fragment_paths,
            context=rendered.template_context,
            template_runtime=self.runtime,
            document_state=rendered.document_state,
            bibliography_path=rendered.bibliography_path,
            template_engine=rendered.template_engine,
            requires_shell_escape=rendered.requires_shell_escape,
        )


def get_template(identifier: str | Path, **kwargs: Any) -> TemplateSession:
    """Instantiate a :class:`TemplateSession` for the requested template."""
    runtime = load_template_runtime(str(identifier))
    settings = kwargs.pop("settings", None)
    emitter = kwargs.pop("emitter", None)
    if "callbacks" in kwargs:
        raise TypeError("'callbacks' is no longer supported; provide an emitter instead.")
    if kwargs:
        unexpected = ", ".join(sorted(kwargs))
        raise TypeError(f"Unexpected keyword arguments: {unexpected}")
    return TemplateSession(runtime, settings=settings, emitter=emitter)
