"""Conversion orchestration utilities for CLI and embedding integrations."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from texsmith.adapters.latex.engines import (
    EngineResult,
    build_engine_command,
    build_tex_env,
    compute_features,
    ensure_command_paths,
    missing_dependencies,
    resolve_engine,
    run_engine_command,
)
from texsmith.adapters.latex.pyxindy import is_available as pyxindy_available
from texsmith.adapters.latex.tectonic import (
    BiberAcquisitionError,
    MakeglossariesAcquisitionError,
    TectonicAcquisitionError,
    select_biber_binary,
    select_makeglossaries,
    select_tectonic_binary,
)
from texsmith.adapters.markdown import split_front_matter

from ..diagnostics import DiagnosticEmitter
from ..documents import Document, TitleStrategy, front_matter_has_title
from ..templates.session import TemplateRenderResult, TemplateSession, get_template
from .core import ConversionBundle, convert_documents
from .debug import ConversionError, ensure_emitter
from .inputs import (
    InputKind,
    UnsupportedInputError,
    extract_front_matter_slots,
)
from .models import ConversionRequest


__all__ = [
    "ConversionResponse",
    "ConversionService",
    "SplitInputsResult",
    "classify_input_source",
]


@dataclass(slots=True)
class SplitInputsResult:
    """Structured partitioning of input paths."""

    documents: list[Path]
    bibliography_files: list[Path]
    front_matter: Mapping[str, Any] | None = None
    front_matter_paths: list[Path] = field(default_factory=list)

    def __iter__(self) -> Iterable[object]:  # pragma: no cover - convenience iterator
        yield self.documents
        yield self.bibliography_files


@dataclass(slots=True)
class ConversionResponse:
    """Captured outcome of :class:`ConversionService` execution."""

    request: ConversionRequest
    documents: list[Document]
    bibliography_files: list[Path]
    result: ConversionBundle | TemplateRenderResult
    emitter: DiagnosticEmitter | None = None

    @property
    def is_template(self) -> bool:
        """Return True when the response contains template output rather than raw fragments."""
        return isinstance(self.result, TemplateRenderResult)

    @property
    def bundle(self) -> ConversionBundle:
        """Expose the conversion bundle while guarding against template misuse."""
        if isinstance(self.result, ConversionBundle):
            return self.result
        raise TypeError("ConversionResponse does not contain a ConversionBundle.")

    @property
    def render_result(self) -> TemplateRenderResult:
        """Expose the template render result while guarding against bundle misuse."""
        if isinstance(self.result, TemplateRenderResult):
            return self.result
        raise TypeError("ConversionResponse does not contain a TemplateRenderResult.")


@dataclass(slots=True)
class _PreparedBatch:
    documents: list[Document]
    document_map: dict[Path, Document]
    emitter: DiagnosticEmitter
    bibliography_files: list[Path]


class ConversionService:
    """High-level façade that encapsulates document preparation and execution."""

    def split_inputs(
        self,
        inputs: Iterable[Path],
        extra_bibliography: Iterable[Path] = (),
    ) -> SplitInputsResult:
        """Separate document inputs, bibliography files, and optional front matter to keep downstream parsing deterministic."""
        inline_bibliography: list[Path] = []
        documents: list[Path] = []
        front_matter_entries: list[tuple[Path, Mapping[str, Any]]] = []

        for candidate in inputs:
            suffix = candidate.suffix.lower()
            if suffix in {".bib", ".bibtex"}:
                inline_bibliography.append(candidate)
                continue
            loaded_front_matter = _load_front_matter_file(candidate)
            if isinstance(loaded_front_matter, Mapping):
                front_matter_entries.append((candidate, loaded_front_matter))
                continue
            documents.append(candidate)

        bibliography_paths = _deduplicate_paths([*inline_bibliography, *extra_bibliography])
        if not documents and front_matter_entries:
            # Treat the last front-matter file as an input document so templates can
            # operate on YAML sources without requiring additional Markdown/HTML
            # content; any earlier YAML inputs keep acting as shared configuration.
            last_path, _ = front_matter_entries.pop()
            documents.append(last_path)

        front_matter: Mapping[str, Any] | None = None
        front_matter_paths: list[Path] = []
        for path, payload in front_matter_entries:
            # Deep-merge in argument order: later files override earlier ones.
            front_matter = _merge_front_matter(front_matter or {}, payload)
            front_matter_paths.append(path)

        return SplitInputsResult(
            documents=documents,
            bibliography_files=bibliography_paths,
            front_matter=front_matter,
            front_matter_paths=front_matter_paths,
        )

    def prepare_documents(self, request: ConversionRequest) -> _PreparedBatch:
        """Normalise input sources into :class:`Document` instances so conversion steps operate on consistent objects."""
        emitter = ensure_emitter(request.emitter)
        documents: list[Document] = []
        mapping: dict[Path, Document] = {}
        shared_front_matter = _normalise_front_matter(request.front_matter)

        for index, path in enumerate(request.documents):
            input_kind = classify_input_source(path)
            extract_title = request.promote_title and index == 0 and not request.suppress_title
            effective_strip = request.strip_heading_all or (
                request.strip_heading_first_document and index == 0
            )
            strategy: TitleStrategy | None = None
            if effective_strip:
                strategy = TitleStrategy.DROP
                extract_title = False
            elif not extract_title:
                strategy = TitleStrategy.KEEP
            else:
                strategy = None

            if input_kind is InputKind.MARKDOWN:
                document = Document.from_markdown(
                    path,
                    extensions=list(request.markdown_extensions),
                    base_level=request.base_level,
                    promote_title=extract_title,
                    strip_heading=effective_strip,
                    suppress_title=request.suppress_title,
                    title_strategy=strategy,
                    numbered=request.numbered,
                    emitter=emitter,
                )
            else:
                document = Document.from_html(
                    path,
                    selector=request.selector,
                    base_level=request.base_level,
                    promote_title=extract_title,
                    strip_heading=effective_strip,
                    suppress_title=request.suppress_title,
                    title_strategy=strategy,
                    numbered=request.numbered,
                    full_document=request.full_document,
                    emitter=emitter,
                )

            documents.append(document)
            mapping[path] = document

        press_sources = _collect_press_sources(documents, shared_front_matter, request)
        if len(press_sources) > 1:
            raise ConversionError(
                "Multiple sources declare press metadata; only one is allowed for a conversion: "
                + ", ".join(press_sources)
            )

        _apply_shared_front_matter(documents, shared_front_matter)

        for path, directives in request.slot_assignments.items():
            document = mapping.get(path)
            if document is None or not directives:
                continue
            for directive in directives:
                document.assign_slot(
                    directive.slot,
                    selector=directive.selector,
                    include_document=directive.include_document,
                )
        bibliography = _deduplicate_paths(request.bibliography_files)
        return _PreparedBatch(
            documents=documents,
            document_map=mapping,
            emitter=emitter,
            bibliography_files=bibliography,
        )

    def execute(
        self,
        request: ConversionRequest,
        *,
        prepared: _PreparedBatch | None = None,
    ) -> ConversionResponse:
        """Execute a conversion workflow and return a structured response, routing to template or raw conversion paths as needed."""
        batch = prepared or self.prepare_documents(request)
        settings = request.copy()
        emitter = batch.emitter

        if request.template is None:
            bundle = convert_documents(
                batch.documents,
                output_dir=request.render_dir,
                settings=settings,
                emitter=emitter,
                bibliography_files=batch.bibliography_files,
            )
            return ConversionResponse(
                request=request,
                documents=batch.documents,
                bibliography_files=batch.bibliography_files,
                result=bundle,
                emitter=emitter,
            )

        session = self._initialise_template_session(
            request.template,
            settings=settings,
            emitter=emitter,
        )
        if request.template_options:
            session.update_options(request.template_options)
        if batch.bibliography_files:
            session.add_bibliography(*batch.bibliography_files)
        for document in batch.documents:
            session.add_document(document)

        target_dir = (request.render_dir or Path("build")).resolve()
        render_result = session.render(target_dir, embed_fragments=request.embed_fragments)
        return ConversionResponse(
            request=request,
            documents=batch.documents,
            bibliography_files=batch.bibliography_files,
            result=render_result,
            emitter=emitter,
        )

    def build_pdf(
        self,
        render_result: TemplateRenderResult,
        *,
        engine: str | None = "tectonic",
        classic_output: bool = False,
        isolate_cache: bool = False,
        env: Mapping[str, str] | None = None,
        console: Any | None = None,
        verbosity: int = 0,
        use_system_tectonic: bool = False,
        run_engine: Callable[..., EngineResult] = run_engine_command,
    ) -> EngineResult:
        """Compile a rendered template into a PDF using the requested engine, selecting dependencies on demand.

        ``run_engine`` is the LaTeX-engine runner, injectable so callers (and
        tests) can substitute the execution step without monkeypatching module
        globals; it defaults to :func:`run_engine_command`.
        """
        template_context = getattr(render_result, "template_context", None) or getattr(
            render_result, "context", None
        )
        features = compute_features(
            requires_shell_escape=render_result.requires_shell_escape,
            bibliography=render_result.has_bibliography,
            document_state=render_result.document_state,
            template_context=template_context,
        )
        choice = resolve_engine(engine, render_result.template_engine)
        tectonic_binary: Path | None = None
        biber_binary: Path | None = None
        makeglossaries_binary: Path | None = None
        bundled_bin: Path | None = None
        if choice.backend == "tectonic":
            try:
                selection = select_tectonic_binary(use_system_tectonic, console=console)
                if features.bibliography and not use_system_tectonic:
                    biber_binary = select_biber_binary(console=console)
                    bundled_bin = biber_binary.parent
                if features.has_glossary and not pyxindy_available():
                    glossaries = select_makeglossaries(console=console)
                    makeglossaries_binary = glossaries.path
                    if glossaries.source == "bundled":
                        bundled_bin = bundled_bin or glossaries.path.parent
            except (
                TectonicAcquisitionError,
                BiberAcquisitionError,
                MakeglossariesAcquisitionError,
            ) as exc:
                raise ConversionError(str(exc)) from exc
            tectonic_binary = selection.path

        available_bins: dict[str, Path] = {}
        if biber_binary:
            available_bins["biber"] = biber_binary
        if makeglossaries_binary:
            available_bins["makeglossaries"] = makeglossaries_binary

        missing = missing_dependencies(
            choice,
            features,
            use_system_tectonic=use_system_tectonic,
            available_binaries=available_bins or None,
        )
        if missing:
            formatted = ", ".join(sorted(missing))
            raise ConversionError(f"Missing required LaTeX tools for '{choice.label}': {formatted}")

        command_plan = ensure_command_paths(
            build_engine_command(
                choice,
                features,
                main_tex_path=render_result.main_tex_path,
                tectonic_binary=tectonic_binary,
            )
        )
        base_env = build_tex_env(
            render_result.main_tex_path.parent,
            isolate_cache=isolate_cache,
            extra_path=bundled_bin,
            biber_path=biber_binary,
        )
        merged_env = dict(base_env)
        if env:
            merged_env.update(env)

        return run_engine(
            command_plan,
            backend=choice.backend,
            workdir=render_result.main_tex_path.parent,
            env=merged_env,
            console=console,
            verbosity=verbosity,
            classic_output=classic_output,
            features=features,
        )

    @staticmethod
    def _initialise_template_session(
        template: str,
        *,
        settings: ConversionRequest,
        emitter: DiagnosticEmitter,
    ) -> TemplateSession:
        return get_template(
            template,
            settings=settings,
            emitter=emitter,
        )


_NOT_FRONT_MATTER = object()


def _load_front_matter_file(path: Path) -> Mapping[str, Any] | object:
    """Return parsed front matter when the path looks like a metadata file."""
    suffix = path.suffix.lower()
    if suffix not in {".yml", ".yaml"}:
        return _NOT_FRONT_MATTER
    name_lower = path.name.lower()
    if name_lower in {"mkdocs.yml", "mkdocs.yaml"}:
        return _NOT_FRONT_MATTER
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConversionError(f"Failed to read front matter source '{path}': {exc}") from exc

    if not payload.strip():
        return {}

    if payload.lstrip().startswith("---"):
        metadata, body = split_front_matter(payload)
        if body.strip():
            return _NOT_FRONT_MATTER
        return metadata

    try:
        parsed = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        raise ConversionError(f"Invalid YAML front matter in '{path}': {exc}") from exc
    return dict(parsed) if isinstance(parsed, Mapping) else _NOT_FRONT_MATTER


def _normalise_front_matter(data: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise ConversionError("Front matter must be a mapping when provided programmatically.")
    return copy.deepcopy(dict(data))


def _front_matter_declares_press(metadata: Mapping[str, Any] | None) -> bool:
    if not isinstance(metadata, Mapping):
        return False
    press_section = metadata.get("press")
    if isinstance(press_section, Mapping):
        return True
    return any(isinstance(key, str) and key.startswith("press.") for key in metadata)


def _merge_front_matter(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in override.items():
        if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_front_matter(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _apply_shared_front_matter(
    documents: list[Document],
    shared_front_matter: Mapping[str, Any] | None,
) -> None:
    if not shared_front_matter:
        return
    for document in documents:
        merged = _merge_front_matter(shared_front_matter, document.front_matter)
        document.set_front_matter(merged)
        if document.title_strategy is TitleStrategy.PROMOTE_METADATA and front_matter_has_title(
            merged
        ):
            document.title_strategy = TitleStrategy.KEEP
        base_mapping, _base_options = extract_front_matter_slots(merged)
        document.reset_slots(base_mapping)


def _collect_press_sources(
    documents: list[Document],
    shared_front_matter: Mapping[str, Any] | None,
    request: ConversionRequest,
) -> list[str]:
    sources: list[str] = []
    if shared_front_matter and _front_matter_declares_press(shared_front_matter):
        # Merged configuration files count as a single press source; conflicts
        # between them are already resolved by the merge (later files win).
        if request.front_matter_paths:
            sources.append(", ".join(str(path) for path in request.front_matter_paths))
        else:
            sources.append("front matter")
    for document in documents:
        if _front_matter_declares_press(document.front_matter):
            sources.append(str(document.source_path))
    return sources


def classify_input_source(path: Path) -> InputKind:
    """Determine the document kind based on filename suffix, rejecting unsupported types early."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return InputKind.MARKDOWN
    if suffix in {".yaml", ".yml"}:
        if path.name.lower() in {"mkdocs.yml", "mkdocs.yaml"}:
            raise UnsupportedInputError("MkDocs configuration files are not supported.")
        return InputKind.MARKDOWN
    if suffix in {".html", ".htm"}:
        return InputKind.HTML
    raise UnsupportedInputError(
        f"Unsupported input file type '{suffix or '<none>'}'. "
        "Provide a Markdown source (.md) or HTML document (.html)."
    )


def _deduplicate_paths(values: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in values:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result
