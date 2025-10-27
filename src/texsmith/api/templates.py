"""Template orchestration helpers exposed by the TeXSmith API.

Architecture
: `TemplateSession` owns lifecycle management: it accepts documents, ensures
  metadata overrides are applied, and invokes the conversion engine either once
  (single document) or repeatedly (multi-fragment projects).
: `TemplateOptions` is a thin wrapper around a mutable mapping that keeps
  user-supplied overrides isolated from the template defaults. Its API is
  intentionally dictionary-like to integrate smoothly with CLI parsing.
: `TemplateRenderResult` captures the products of a render pass, including
  computed context, bibliography location, and shell-escape requirements so
  downstream tools can decide how to compile the LaTeX output.

Implementation Rationale
: Templates often need to render multiple fragments into specific slots while
  sharing state such as bibliography caches. The session abstraction keeps that
  orchestration logic together and reduces duplication across the CLI,
  pre-built commands, and programmatic usage.
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
from ..conversion.core import convert_document
from ..conversion.debug import ConversionCallbacks
from ..conversion_contexts import DocumentContext
from ..templates import (
    TemplateError,
    TemplateRuntime,
    copy_template_assets,
    load_template_runtime,
)
from ._utils import build_unique_stem_map
from .document import Document
from .pipeline import RenderSettings


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
    """Encapsulates a template, documents, and rendering settings."""

    def __init__(
        self,
        runtime: TemplateRuntime,
        *,
        settings: RenderSettings | None = None,
        callbacks: ConversionCallbacks | None = None,
    ) -> None:
        self.runtime = runtime
        attributes = runtime.instance.info.attributes if runtime.instance else {}
        self._options = TemplateOptions(copy.deepcopy(attributes))
        self._documents: list[Document] = []
        self._bibliography_files: list[Path] = []
        self.settings = settings.copy() if settings else RenderSettings()
        self.callbacks = callbacks

    def _prepare_context(self, document: Document) -> DocumentContext:
        context = document.to_context()
        overrides_dict = self._options.to_dict()
        if overrides_dict:
            template_section = context.front_matter.setdefault("template", {})
            if isinstance(template_section, Mapping):
                template_section.update(overrides_dict)
            else:
                context.front_matter["template"] = dict(overrides_dict)
        return context

    def get_default_options(self) -> TemplateOptions:
        """Return a copy of the default template options."""
        return self._options.copy()

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

        if len(self._documents) == 1:
            context = self._prepare_context(self._documents[0])
            result = convert_document(
                document=context,
                output_dir=output_dir,
                parser=self.settings.parser,
                disable_fallback_converters=self.settings.disable_fallback_converters,
                copy_assets=self.settings.copy_assets,
                manifest=self.settings.manifest,
                template=self.runtime.name,
                persist_debug_html=self.settings.persist_debug_html,
                language=self.settings.language,
                slot_overrides=self._documents[0].slot_overrides or None,
                bibliography_files=list(self._bibliography_files),
                legacy_latex_accents=self.settings.legacy_latex_accents,
                template_runtime=self.runtime,
                wrap_document=True,
                callbacks=self.callbacks,
            )

            if result.tex_path is None:
                raise TemplateError("Template rendering failed to produce a LaTeX document.")

            return TemplateRenderResult(
                main_tex_path=result.tex_path,
                fragment_paths=[],
                context=result.template_overrides or {},
                template_runtime=self.runtime,
                document_state=result.document_state or DocumentState(),
                bibliography_path=result.bibliography_path,
                template_engine=result.template_engine,
                requires_shell_escape=result.template_shell_escape,
            )

        unique_stems = build_unique_stem_map([doc.source_path for doc in self._documents])
        aggregated_slots: dict[str, list[str]] = {}
        default_slot = self.runtime.default_slot
        aggregated_slots.setdefault(default_slot, [])

        shared_state: DocumentState | None = None
        bibliography_path: Path | None = None
        template_overrides_master: dict[str, Any] | None = None
        fragment_paths: list[Path] = []
        template_engine: str | None = None
        requires_shell_escape = self.runtime.requires_shell_escape

        for _index, document in enumerate(self._documents):
            context = self._prepare_context(document)
            result = convert_document(
                document=context,
                output_dir=output_dir,
                parser=self.settings.parser,
                disable_fallback_converters=self.settings.disable_fallback_converters,
                copy_assets=self.settings.copy_assets,
                manifest=self.settings.manifest,
                template=self.runtime.name,
                persist_debug_html=self.settings.persist_debug_html,
                language=self.settings.language,
                slot_overrides=document.slot_overrides or None,
                bibliography_files=list(self._bibliography_files),
                legacy_latex_accents=self.settings.legacy_latex_accents,
                state=shared_state,
                template_runtime=self.runtime,
                wrap_document=False,
                callbacks=self.callbacks,
            )

            if template_engine is None:
                template_engine = result.template_engine
            requires_shell_escape = requires_shell_escape or result.template_shell_escape

            shared_state = result.document_state or shared_state
            bibliography_path = result.bibliography_path or bibliography_path
            if template_overrides_master is None:
                template_overrides_master = dict(result.template_overrides)

            stem = unique_stems[document.source_path]
            fragment_path = output_dir / f"{stem}.tex"
            fragment_path.write_text(result.latex_output, encoding="utf-8")
            fragment_paths.append(fragment_path)

            full_slots = set(document.slot_inclusions)
            if default_slot not in aggregated_slots:
                aggregated_slots[default_slot] = []
            if default_slot not in full_slots and result.latex_output.strip():
                aggregated_slots[default_slot].append(f"\\input{{{fragment_path.stem}}}")

            for slot_name in full_slots:
                aggregated_slots.setdefault(slot_name, []).append(
                    f"\\input{{{fragment_path.stem}}}"
                )

            for slot_name, fragment_content in result.slot_outputs.items():
                if not fragment_content:
                    continue
                if slot_name == default_slot and slot_name not in full_slots:
                    continue
                if slot_name in full_slots:
                    continue
                aggregated_slots.setdefault(slot_name, []).append(fragment_content)

        if shared_state is None:
            shared_state = DocumentState()
        if template_overrides_master is None:
            template_overrides_master = self._options.to_dict()

        aggregated_render = {
            slot: "\n\n".join(chunk for chunk in chunks if chunk)
            for slot, chunks in aggregated_slots.items()
        }

        main_content = aggregated_render.get(default_slot, "")
        template_context = self.runtime.instance.prepare_context(
            main_content,
            overrides=template_overrides_master if template_overrides_master else None,
        )

        for slot_name, content in aggregated_render.items():
            if slot_name == default_slot:
                continue
            template_context[slot_name] = content

        template_context["index_entries"] = shared_state.has_index_entries
        template_context["acronyms"] = shared_state.acronyms.copy()
        template_context["citations"] = list(shared_state.citations)
        template_context["bibliography_entries"] = shared_state.bibliography
        if shared_state.citations and bibliography_path is not None:
            template_context["bibliography"] = bibliography_path.stem
            template_context["bibliography_resource"] = bibliography_path.name
            template_context.setdefault("bibliography_style", "plain")

        final_output = self.runtime.instance.wrap_document(
            main_content,
            context=template_context,
        )

        try:
            copy_template_assets(
                self.runtime.instance,
                output_dir,
                context=template_context,
                overrides=template_overrides_master if template_overrides_master else None,
            )
        except TemplateError as exc:
            message = str(exc)
            if self.callbacks and self.callbacks.emit_error:
                self.callbacks.emit_error(message, exc)
            raise

        first_stem = unique_stems[self._documents[0].source_path]
        main_tex_path = output_dir / f"{first_stem}-collection.tex"
        main_tex_path.write_text(final_output, encoding="utf-8")

        return TemplateRenderResult(
            main_tex_path=main_tex_path,
            fragment_paths=fragment_paths,
            context=template_context,
            template_runtime=self.runtime,
            document_state=shared_state,
            bibliography_path=bibliography_path,
            template_engine=template_engine,
            requires_shell_escape=requires_shell_escape,
        )


def get_template(identifier: str | Path, **kwargs: Any) -> TemplateSession:
    """Instantiate a :class:`TemplateSession` for the requested template."""
    runtime = load_template_runtime(str(identifier))
    settings = kwargs.pop("settings", None)
    callbacks = kwargs.pop("callbacks", None)
    if kwargs:
        unexpected = ", ".join(sorted(kwargs))
        raise TypeError(f"Unexpected keyword arguments: {unexpected}")
    return TemplateSession(runtime, settings=settings, callbacks=callbacks)
