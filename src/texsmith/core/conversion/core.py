"""Core orchestration logic for the conversion pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import copy
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.context import DocumentState
from texsmith.core.conversion_contexts import ConversionContext
from texsmith.core.diagnostics import (
    debug_enabled,
    ensure_emitter,
    raise_conversion_error,
    record_event,
)
from texsmith.core.documents import Document
from texsmith.core.templates import (
    TemplateError,
    TemplateRuntime,
    wrap_template_document,
)
from texsmith.ir.codec import persist_debug_ir

from ..diagnostics import DiagnosticEmitter, NullEmitter
from ._utils import build_unique_stem_map
from .execution import resolve_conversion_context
from .models import ConversionRequest
from .pipeline import render_ir_document
from .renderer import TemplateFragment
from .resolution import ResolutionChain, bibliography_paths
from .settings import resolve_code_options
from .templates import bind_template


@dataclass(slots=True)
class ConversionResult:
    """Artifacts produced during a document conversion."""

    latex_output: str
    tex_path: Path | None
    template_engine: str | None
    template_shell_escape: bool
    language: str
    has_bibliography: bool = False
    slot_outputs: dict[str, str] = field(default_factory=dict)
    default_slot: str = "mainmatter"
    document_state: DocumentState | None = None
    bibliography_path: Path | None = None
    template_overrides: dict[str, Any] = field(default_factory=dict)
    document: Document | None = None
    context: ConversionContext | None = None
    assets_map: dict[str, Path] = field(default_factory=dict)


def convert_document(
    document: Document,
    output_dir: Path,
    request: ConversionRequest,
    *,
    slot_overrides: Mapping[str, str] | None,
    template_overrides: Mapping[str, Any] | None = None,
    state: DocumentState | None = None,
    template_runtime: TemplateRuntime | None = None,
    wrap_document: bool = True,
    emitter: DiagnosticEmitter | None = None,
    preloaded_bibliography: BibliographyCollection | None = None,
    seen_bibliography_issues: set[tuple[str, str | None, str | None]] | None = None,
    resolution: ResolutionChain | None = None,
) -> ConversionResult:
    """Orchestrate the full conversion of a single document to LaTeX.

    ``resolution`` (IR path) chains the counter state across the documents of
    a batch; ``None`` starts a fresh chain for this document alone.
    """
    emitter = ensure_emitter(emitter or request.emitter)
    output_dir = output_dir.resolve()

    context = resolve_conversion_context(
        document=document,
        request=request,
        template_runtime=template_runtime,
        output_dir=output_dir,
        slot_overrides=slot_overrides,
        template_overrides=template_overrides,
        bibliography_files=request.bibliography_files,
        preloaded_bibliography=preloaded_bibliography,
        seen_bibliography_issues=seen_bibliography_issues,
    )
    context.resolution = resolution

    record_event(
        emitter,
        "convert_document",
        {
            "source": str(context.document.source_path),
            "template": request.template,
            "language": context.language,
            "copy_assets": context.generation.copy_assets,
            "convert_assets": context.generation.convert_assets,
        },
    )
    bind_template(
        context=context,
        template=request.template,
        emitter=emitter,
        legacy_latex_accents=request.legacy_latex_accents,
    )

    return _render_document(
        context=context,
        emitter=emitter,
        initial_state=state,
        wrap_document=wrap_document,
    )


def _render_document(
    *,
    context: ConversionContext,
    emitter: DiagnosticEmitter,
    initial_state: DocumentState | None,
    wrap_document: bool,
) -> ConversionResult:
    # Everything the per-document render needs is carried on the context: the
    # document, the resolved request, and the generation strategy. Derive the
    # locals here rather than threading them through the signature.
    document = context.document
    request = context.request
    strategy = context.generation

    if request.persist_debug_ir and document.ir is not None:
        persist_debug_ir(context.output_dir, document.source_path, document.ir)

    binding = context.template_binding
    if binding is None:  # pragma: no cover - defensive safeguard
        raise RuntimeError("Conversion context is missing a template binding.")

    # The passes, one ``tmark.resolve``, one ``tmark.write`` per slot body;
    # ``Requires`` drives the fragment flags of the state.
    try:
        ir_result = render_ir_document(
            context=context,
            binding=binding,
            emitter=emitter,
            backend="latex",
            chain=context.resolution,
            initial_state=initial_state,
            code_options=resolve_code_options(binding, context.template_overrides),
        )
    except TemplateError as exc:
        if debug_enabled(emitter):
            raise
        raise_conversion_error(emitter, str(exc), exc)
    slot_outputs = ir_result.slot_outputs
    # The resolution travels back onto the caller's document: the service
    # publishes its reference inventory from the labels tmark allocated.
    document.resolved = ir_result.document.resolved
    document_state = ir_result.document_state
    if initial_state is not None:
        # A batch of linked fragments shares one state object: the template
        # wrapper reads the first fragment's state, so what a later document
        # requires (a ``ts-code`` body, an index, a citation) has to land on the
        # very object the earlier fragments carry, not on a copy of it.
        _copy_document_state(initial_state, document_state)
        document_state = initial_state
    ir_assets = ir_result.assets

    default_content = slot_outputs.get(binding.default_slot)
    if default_content is None:
        default_content = ""
        slot_outputs[binding.default_slot] = default_content
    latex_output = default_content

    citations = list(document_state.citations)
    bibliography_output: Path | None = None
    if citations and context.bibliography_collection is not None and context.bibliography_map:
        try:
            context.output_dir.mkdir(parents=True, exist_ok=True)
            bibliography_output = context.output_dir / "texsmith-bibliography.bib"
            context.bibliography_collection.write_bibtex(
                bibliography_output,
                keys=citations,
            )
        except OSError as exc:
            if debug_enabled(emitter):
                raise
            emitter.warning(f"Failed to write bibliography file: {exc}")
            bibliography_output = None

    tex_path: Path | None = None
    if document_state is not None:
        document_state.requires_shell_escape = (
            document_state.requires_shell_escape or binding.requires_shell_escape
        )
    template_instance = binding.instance
    if template_instance is not None and wrap_document:
        try:
            wrap_result = wrap_template_document(
                template=template_instance,
                default_slot=binding.default_slot,
                slot_outputs=slot_outputs,
                document_state=document_state,
                template_overrides=(
                    context.template_overrides if context.template_overrides else None
                ),
                output_dir=context.output_dir,
                copy_assets=strategy.copy_assets,
                output_name=f"{document.source_path.stem}.tex",
                bibliography_path=bibliography_output,
                emitter=emitter,
                fragments=list(
                    context.template_overrides.get(
                        "fragments", binding.runtime.extras.get("fragments", [])
                    )
                ),
                template_runtime=binding.runtime,
            )
            latex_output = wrap_result.latex_output
            tex_path = wrap_result.output_path
        except TemplateError as exc:
            if debug_enabled(emitter):
                raise
            raise_conversion_error(emitter, str(exc), exc)
        except OSError as exc:
            if debug_enabled(emitter):
                raise
            raise_conversion_error(
                emitter,
                f"Failed to write LaTeX output to '{context.output_dir}': {exc}",
                exc,
            )

    asset_map: dict[str, Path] = dict(ir_assets)

    return ConversionResult(
        latex_output=latex_output,
        tex_path=tex_path,
        template_engine=binding.engine,
        template_shell_escape=bool(
            binding.requires_shell_escape
            or (document_state and document_state.requires_shell_escape)
        ),
        language=context.language,
        has_bibliography=bool(bibliography_output),
        slot_outputs=dict(slot_outputs),
        default_slot=binding.default_slot,
        document_state=document_state,
        bibliography_path=bibliography_output,
        template_overrides=dict(context.template_overrides),
        document=document,
        context=context,
        assets_map=asset_map,
    )


def _copy_document_state(target: DocumentState, source: DocumentState) -> None:
    """Synchronise ``target`` in place with a freshly produced ``DocumentState``."""
    for state_field in dataclasses.fields(DocumentState):
        setattr(target, state_field.name, copy.deepcopy(getattr(source, state_field.name)))


@dataclass(slots=True)
class LaTeXFragment:
    """Represents a rendered LaTeX fragment."""

    document: Document
    latex: str
    stem: str
    output_path: Path | None = None
    conversion: ConversionResult | None = None

    def write_to(self, target: Path) -> None:
        """Persist the fragment to disk so later template steps can reference it."""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.latex, encoding="utf-8")
        self.output_path = target


@dataclass(slots=True)
class ConversionBundle:
    """Collection returned by :func:`convert_documents`."""

    fragments: list[LaTeXFragment]

    def combined_output(self) -> str:
        """Concatenate all fragments separated by blank lines for quick previews."""
        return "\n\n".join(fragment.latex for fragment in self.fragments if fragment.latex)


def convert_documents(
    documents: Sequence[Document],
    *,
    output_dir: Path | None = None,
    settings: ConversionRequest | None = None,
    emitter: DiagnosticEmitter | None = None,
    bibliography_files: Iterable[Path] | None = None,
    template: str | None = None,
    template_runtime: TemplateRuntime | None = None,
    template_overrides: Mapping[str, Any] | None = None,
    wrap_document: bool = True,
    shared_state: DocumentState | None = None,
    write_fragments: bool | None = None,
) -> ConversionBundle:
    """Convert one or more documents into LaTeX fragments while coordinating shared state."""
    if not documents:
        raise ValueError("At least one document is required for conversion.")

    request = settings.copy() if settings is not None else ConversionRequest()
    request.bibliography_files = list(bibliography_files or [])
    request.template = template
    unique_stems = build_unique_stem_map([doc.source_path for doc in documents])

    shared_bibliography: BibliographyCollection | None = None
    seen_bibliography_issues: set[tuple[str, str | None, str | None]] = set()

    if bibliography_files:
        shared_bibliography = BibliographyCollection()
        shared_bibliography.load_files(bibliography_files)

    fragments: list[LaTeXFragment] = []
    should_write_fragments = write_fragments if write_fragments is not None else True
    state = shared_state
    active_emitter = emitter or NullEmitter()
    # IR path: one chain per batch, ``start`` carried from document to document.
    resolution = ResolutionChain(bibliography=bibliography_paths(request.bibliography_files))

    for document in documents:
        document = document.prepare_for_conversion()
        target_dir = Path(output_dir) if output_dir is not None else Path("build")
        slot_overrides = dict(document.slot_selectors)
        result = convert_document(
            document=document,
            output_dir=target_dir,
            request=request,
            slot_overrides=slot_overrides or None,
            emitter=active_emitter,
            template_overrides=template_overrides,
            state=None if wrap_document else state,
            template_runtime=template_runtime,
            wrap_document=wrap_document,
            preloaded_bibliography=shared_bibliography,
            seen_bibliography_issues=seen_bibliography_issues,
            resolution=resolution,
        )

        if not wrap_document:
            state = result.document_state or state

        stem = unique_stems[document.source_path]
        fragment = LaTeXFragment(
            document=document,
            latex=result.latex_output,
            stem=stem,
            conversion=result,
        )
        if output_dir is not None and should_write_fragments:
            target = target_dir / f"{stem}.tex"
            fragment.write_to(target)
        fragments.append(fragment)

    return ConversionBundle(fragments=fragments)


def to_template_fragments(bundle: ConversionBundle) -> list[TemplateFragment]:
    """Convert bundle fragments into the template fragment contract used by the template engine."""
    fragments: list[TemplateFragment] = []
    for fragment in bundle.fragments:
        conversion = fragment.conversion
        if conversion is None:
            raise ValueError("Template rendering requires conversion metadata for each fragment.")

        document = fragment.document
        slot_includes: set[str] = set()
        if document is not None:
            slot_includes = set(document.slot_includes)

        fragments.append(
            TemplateFragment(
                stem=fragment.stem,
                latex=conversion.latex_output,
                default_slot=conversion.default_slot or "mainmatter",
                slot_outputs=dict(conversion.slot_outputs),
                slot_includes=slot_includes,
                document_state=conversion.document_state,
                bibliography_path=conversion.bibliography_path,
                template_engine=conversion.template_engine,
                requires_shell_escape=conversion.template_shell_escape,
                template_overrides=dict(conversion.template_overrides),
                output_path=fragment.output_path,
                front_matter=document.front_matter,
                source_path=document.source_path,
                assets=dict(conversion.assets_map),
            )
        )
    return fragments


__all__ = [
    "ConversionBundle",
    "ConversionResult",
    "LaTeXFragment",
    "convert_document",
    "convert_documents",
    "to_template_fragments",
]
