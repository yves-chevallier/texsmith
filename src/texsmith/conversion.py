"""High-level document conversion utilities shared across the project."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import copy
import dataclasses
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, FeatureNotFound
from bs4.element import NavigableString, Tag
from pybtex.exceptions import PybtexError
from slugify import slugify

from .bibliography import (
    BibliographyCollection,
    DoiBibliographyFetcher,
    DoiLookupError,
    bibliography_data_from_string,
)
from .config import BookConfig
from .context import DocumentState
from .conversion_contexts import (
    BinderContext,
    DocumentContext,
    GenerationStrategy,
    SegmentContext,
)
from .docker import is_docker_available
from .exceptions import LatexRenderingError, TransformerExecutionError
from .latex.formatter import LaTeXFormatter
from .latex.renderer import LaTeXRenderer
from .templates import (
    DEFAULT_TEMPLATE_LANGUAGE,
    TemplateBinding,
    TemplateError,
    TemplateRuntime,
    TemplateSlot,
    build_template_overrides,
    copy_template_assets,
    load_template_runtime,
    resolve_template_binding,
    resolve_template_language,
)
from .transformers import has_converter, register_converter


__all__ = [
    "DEFAULT_TEMPLATE_LANGUAGE",
    "DOCUMENT_SELECTOR_SENTINEL",
    "BinderContext",
    "ConversionCallbacks",
    "ConversionError",
    "ConversionResult",
    "DocumentContext",
    "GenerationStrategy",
    "SegmentContext",
    "TemplateBinding",
    "TemplateRuntime",
    "UnsupportedInputError",
    "attempt_transformer_fallback",
    "build_binder_context",
    "build_document_context",
    "build_template_overrides",
    "coerce_slot_selector",
    "convert_document",
    "copy_document_state",
    "ensure_fallback_converters",
    "extract_content",
    "extract_front_matter_bibliography",
    "extract_front_matter_slots",
    "extract_slot_fragments",
    "format_rendering_error",
    "heading_level_for",
    "load_template_runtime",
    "parse_slot_mapping",
    "persist_debug_artifacts",
    "render_with_fallback",
    "resolve_template_language",
]


logger = logging.getLogger(__name__)


DOCUMENT_SELECTOR_SENTINEL = "@document"


@dataclass(slots=True)
class ConversionCallbacks:
    """Optional hooks used to surface conversion diagnostics."""

    emit_warning: Callable[[str, Exception | None], None] | None = None
    emit_error: Callable[[str, Exception | None], None] | None = None
    debug_enabled: bool = False


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
    document_context: DocumentContext | None = None
    binder_context: BinderContext | None = None


class ConversionError(Exception):
    """Raised when a conversion fails and cannot recover."""


class UnsupportedInputError(Exception):
    """Raised when a CLI input argument cannot be processed."""


class InputKind(Enum):
    """Supported input modalities handled by the conversion pipeline."""

    MARKDOWN = "markdown"
    HTML = "html"


@dataclass(slots=True)
class SlotFragment:
    """HTML fragment mapped to a template slot with position metadata."""

    name: str
    html: str
    position: int


def _emit_warning(
    callbacks: ConversionCallbacks | None,
    message: str,
    exception: Exception | None = None,
) -> None:
    if callbacks and callbacks.emit_warning is not None:
        callbacks.emit_warning(message, exception)
    else:  # pragma: no cover - fallback logging
        logger.warning(message)


def _emit_error(
    callbacks: ConversionCallbacks | None,
    message: str,
    exception: Exception | None = None,
) -> None:
    if callbacks and callbacks.emit_error is not None:
        callbacks.emit_error(message, exception)
    else:  # pragma: no cover - fallback logging
        logger.error(message)


def _debug_enabled(callbacks: ConversionCallbacks | None) -> bool:
    return bool(callbacks and callbacks.debug_enabled)


def _load_inline_bibliography(
    collection: BibliographyCollection,
    entries: Mapping[str, str],
    *,
    source_label: str,
    callbacks: ConversionCallbacks | None,
    fetcher: DoiBibliographyFetcher | None = None,
) -> None:
    if not entries:
        return

    resolver = fetcher or DoiBibliographyFetcher()
    source_path = _inline_bibliography_source_path(source_label)

    for key, doi_value in entries.items():
        try:
            payload = resolver.fetch(doi_value)
        except DoiLookupError as exc:
            _emit_warning(
                callbacks,
                f"Failed to resolve DOI '{doi_value}' for '{key}': {exc}",
            )
            continue
        try:
            data = bibliography_data_from_string(payload, key)
        except PybtexError as exc:
            _emit_warning(
                callbacks,
                f"Failed to parse bibliography entry '{key}': {exc}",
            )
            continue
        collection.load_data(data, source=source_path)


def _inline_bibliography_source_path(label: str) -> Path:
    slug = slugify(label, separator="-")
    if not slug:
        slug = "frontmatter"
    return Path(f"frontmatter-{slug}.bib")


def _fail(
    callbacks: ConversionCallbacks | None,
    message: str,
    exc: Exception,
) -> None:
    _emit_error(callbacks, message, exception=exc)
    raise ConversionError(message) from exc


def build_document_context(
    *,
    name: str,
    source_path: Path,
    html: str,
    front_matter: Mapping[str, Any] | None,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
) -> DocumentContext:
    """Construct a document context enriched with metadata and slot requests."""
    metadata = dict(front_matter or {})
    slot_requests = extract_front_matter_slots(metadata)

    return DocumentContext(
        name=name,
        source_path=source_path,
        html=html,
        base_level=base_level,
        heading_level=heading_level,
        numbered=numbered,
        drop_title=drop_title,
        front_matter=metadata,
        slot_requests=slot_requests,
    )


def convert_document(
    document: DocumentContext,
    output_dir: Path,
    parser: str | None,
    disable_fallback_converters: bool,
    copy_assets: bool,
    manifest: bool,
    template: str | None,
    persist_debug_html: bool,
    language: str | None,
    slot_overrides: Mapping[str, str] | None,
    bibliography_files: list[Path],
    legacy_latex_accents: bool,
    *,
    state: DocumentState | None = None,
    template_runtime: TemplateRuntime | None = None,
    wrap_document: bool = True,
    callbacks: ConversionCallbacks | None = None,
) -> ConversionResult:
    """Orchestrate the full HTML-to-LaTeX conversion for a single document."""
    strategy = GenerationStrategy(
        copy_assets=copy_assets,
        prefer_inputs=False,
        persist_manifest=manifest,
    )

    output_dir = output_dir.resolve()

    binder_context = build_binder_context(
        document_context=document,
        template=template,
        template_runtime=template_runtime,
        requested_language=language,
        bibliography_files=bibliography_files,
        slot_overrides=slot_overrides,
        output_dir=output_dir,
        strategy=strategy,
        callbacks=callbacks,
        legacy_latex_accents=legacy_latex_accents,
    )

    renderer_kwargs: dict[str, Any] = {
        "output_root": output_dir,
        "copy_assets": strategy.copy_assets,
        "parser": parser or "html.parser",
    }

    return _render_document(
        document_context=document,
        binder_context=binder_context,
        renderer_kwargs=renderer_kwargs,
        strategy=strategy,
        disable_fallback_converters=disable_fallback_converters,
        persist_debug_html=persist_debug_html,
        callbacks=callbacks,
        initial_state=state,
        wrap_document=wrap_document,
        legacy_latex_accents=legacy_latex_accents,
    )


def build_binder_context(
    *,
    document_context: DocumentContext,
    template: str | None,
    template_runtime: TemplateRuntime | None,
    requested_language: str | None,
    bibliography_files: list[Path],
    slot_overrides: Mapping[str, str] | None,
    output_dir: Path,
    strategy: GenerationStrategy,
    callbacks: ConversionCallbacks | None,
    legacy_latex_accents: bool,
) -> BinderContext:
    """Prepare template bindings, bibliography data, and slot mappings."""
    resolved_language = resolve_template_language(requested_language, document_context.front_matter)
    document_context.language = resolved_language

    config = BookConfig(
        project_dir=document_context.source_path.parent,
        language=resolved_language,
        legacy_latex_accents=legacy_latex_accents,
    )

    inline_bibliography = extract_front_matter_bibliography(document_context.front_matter)

    bibliography_collection: BibliographyCollection | None = None
    bibliography_map: dict[str, dict[str, Any]] = {}

    if bibliography_files or inline_bibliography:
        bibliography_collection = BibliographyCollection()
        if bibliography_files:
            bibliography_collection.load_files(bibliography_files)
        if inline_bibliography:
            _load_inline_bibliography(
                bibliography_collection,
                inline_bibliography,
                source_label=document_context.source_path.stem,
                callbacks=callbacks,
            )

    if bibliography_collection is not None:
        bibliography_map = bibliography_collection.to_dict()
        for issue in bibliography_collection.issues:
            prefix = f"[{issue.key}] " if issue.key else ""
            source_hint = f" ({issue.source})" if issue.source else ""
            _emit_warning(callbacks, f"{prefix}{issue.message}{source_hint}")

    document_context.bibliography = bibliography_map

    slot_requests = dict(document_context.slot_requests)
    if slot_overrides:
        slot_requests.update(dict(slot_overrides))

    template_overrides = build_template_overrides(document_context.front_matter)
    template_overrides["language"] = resolved_language
    meta_section = template_overrides.get("meta")
    if isinstance(meta_section, dict):
        meta_section.setdefault("language", resolved_language)

    active_slot_requests: dict[str, str] = {}
    binding: TemplateBinding | None = None
    try:
        binding, active_slot_requests = resolve_template_binding(
            template=template,
            template_runtime=template_runtime,
            template_overrides=template_overrides,
            slot_requests=slot_requests,
            warn=lambda message: _emit_warning(callbacks, message),
        )
    except TemplateError as exc:
        if _debug_enabled(callbacks):
            raise
        _fail(callbacks, str(exc), exc)
    if binding is None:  # pragma: no cover - defensive
        raise RuntimeError("Failed to resolve template binding.")

    binder_context = BinderContext(
        output_dir=output_dir,
        config=config,
        strategy=strategy,
        language=resolved_language,
        slot_requests=active_slot_requests,
        template_overrides=dict(template_overrides),
        bibliography_map=bibliography_map,
        bibliography_collection=bibliography_collection,
        template_binding=binding,
    )
    binder_context.documents.append(document_context)

    return binder_context


def _render_document(
    *,
    document_context: DocumentContext,
    binder_context: BinderContext,
    renderer_kwargs: dict[str, Any],
    strategy: GenerationStrategy,
    disable_fallback_converters: bool,
    persist_debug_html: bool,
    callbacks: ConversionCallbacks | None,
    initial_state: DocumentState | None,
    wrap_document: bool,
    legacy_latex_accents: bool,
) -> ConversionResult:
    if persist_debug_html:
        persist_debug_artifacts(
            binder_context.output_dir,
            document_context.source_path,
            document_context.html,
        )

    binding = binder_context.template_binding
    if binding is None:  # pragma: no cover - defensive safeguard
        raise RuntimeError("BinderContext is missing a template binding.")

    effective_base_level = binding.base_level or 0
    slot_base_levels = binding.slot_levels()

    runtime_common: dict[str, object] = {
        "numbered": document_context.numbered,
        "source_dir": document_context.source_path.parent,
        "document_path": document_context.source_path,
        "copy_assets": strategy.copy_assets,
        "language": binder_context.language,
    }
    if binder_context.bibliography_map:
        runtime_common["bibliography"] = binder_context.bibliography_map
    if binding.name is not None:
        runtime_common["template"] = binding.name
    if strategy.persist_manifest:
        runtime_common["generate_manifest"] = True

    active_slot_requests = binder_context.slot_requests

    parser_backend = str(renderer_kwargs.get("parser", "html.parser"))
    slot_fragments, missing_slots = extract_slot_fragments(
        document_context.html,
        active_slot_requests,
        binding.default_slot,
        slot_definitions=binding.slots,
        parser_backend=parser_backend,
    )
    for message in missing_slots:
        _emit_warning(callbacks, message)

    segment_registry: dict[str, list[SegmentContext]] = {}
    for fragment in slot_fragments:
        base_value = slot_base_levels.get(fragment.name, effective_base_level)
        segment_registry.setdefault(fragment.name, []).append(
            SegmentContext(
                name=fragment.name,
                html=fragment.html,
                base_level=base_value + document_context.base_level,
                metadata=document_context.front_matter,
                bibliography=binder_context.bibliography_map,
            )
        )

    formatter = LaTeXFormatter()
    formatter.legacy_latex_accents = legacy_latex_accents
    binding.apply_formatter_overrides(formatter)
    renderer: LaTeXRenderer | None = None

    def renderer_factory() -> LaTeXRenderer:
        nonlocal renderer
        if renderer is None:
            renderer = LaTeXRenderer(
                config=binder_context.config,
                formatter=formatter,
                **renderer_kwargs,
            )
        return renderer

    if not disable_fallback_converters:
        ensure_fallback_converters()

    slot_outputs: dict[str, str] = {}
    document_state: DocumentState | None = initial_state
    drop_title_flag = bool(document_context.drop_title)
    for fragment in slot_fragments:
        runtime_fragment = dict(runtime_common)
        base_value = slot_base_levels.get(fragment.name, effective_base_level)
        runtime_fragment["base_level"] = (
            base_value + document_context.base_level + document_context.heading_level
        )
        if drop_title_flag:
            runtime_fragment["drop_title"] = True
            drop_title_flag = False
        fragment_output = ""
        try:
            fragment_output, document_state = render_with_fallback(
                renderer_factory,
                fragment.html,
                runtime_fragment,
                binder_context.bibliography_map,
                state=document_state,
            )
        except LatexRenderingError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(callbacks, format_rendering_error(exc), exc)
        existing_fragment = slot_outputs.get(fragment.name, "")
        slot_outputs[fragment.name] = f"{existing_fragment}{fragment_output}"

    if document_state is None:
        document_state = DocumentState(bibliography=dict(binder_context.bibliography_map))

    default_content = slot_outputs.get(binding.default_slot)
    if default_content is None:
        default_content = ""
        slot_outputs[binding.default_slot] = default_content
    latex_output = default_content

    document_context.segments = segment_registry
    for slot_name, segments in segment_registry.items():
        binder_context.bound_segments.setdefault(slot_name, []).extend(segments)

    citations = list(document_state.citations)
    bibliography_output: Path | None = None
    if (
        citations
        and binder_context.bibliography_collection is not None
        and binder_context.bibliography_map
    ):
        try:
            binder_context.output_dir.mkdir(parents=True, exist_ok=True)
            bibliography_output = binder_context.output_dir / "texsmith-bibliography.bib"
            binder_context.bibliography_collection.write_bibtex(
                bibliography_output,
                keys=citations,
            )
        except OSError as exc:
            if _debug_enabled(callbacks):
                raise
            _emit_warning(callbacks, f"Failed to write bibliography file: {exc}")
            bibliography_output = None

    tex_path: Path | None = None
    template_instance = binding.instance
    if template_instance is not None and wrap_document:
        template_context: dict[str, Any] | None = None
        try:
            template_context = template_instance.prepare_context(
                latex_output,
                overrides=binder_context.template_overrides
                if binder_context.template_overrides
                else None,
            )
            for slot_name, fragment_output in slot_outputs.items():
                if slot_name == binding.default_slot:
                    continue
                template_context[slot_name] = fragment_output
            template_context["index_entries"] = document_state.has_index_entries
            template_context["acronyms"] = document_state.acronyms.copy()
            template_context["citations"] = citations
            template_context["bibliography_entries"] = document_state.bibliography
            if citations and bibliography_output is not None:
                template_context["bibliography"] = bibliography_output.stem
                template_context["bibliography_resource"] = bibliography_output.name
                if not template_context.get("bibliography_style"):
                    template_context["bibliography_style"] = "plain"
            latex_output = template_instance.wrap_document(
                latex_output,
                context=template_context,
            )
        except TemplateError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(callbacks, str(exc), exc)
        try:
            copy_template_assets(
                template_instance,
                binder_context.output_dir,
                context=template_context,
                overrides=binder_context.template_overrides
                if binder_context.template_overrides
                else None,
            )
        except TemplateError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(callbacks, str(exc), exc)

        try:
            binder_context.output_dir.mkdir(parents=True, exist_ok=True)
            tex_path = binder_context.output_dir / f"{document_context.source_path.stem}.tex"
            tex_path.write_text(latex_output, encoding="utf-8")
        except OSError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(
                callbacks,
                f"Failed to write LaTeX output to '{binder_context.output_dir}': {exc}",
                exc,
            )

    return ConversionResult(
        latex_output=latex_output,
        tex_path=tex_path,
        template_engine=binding.engine,
        template_shell_escape=binding.requires_shell_escape,
        language=binder_context.language,
        has_bibliography=bool(citations),
        slot_outputs=dict(slot_outputs),
        default_slot=binding.default_slot,
        document_state=document_state,
        bibliography_path=bibliography_output,
        template_overrides=dict(binder_context.template_overrides),
        document_context=document_context,
        binder_context=binder_context,
    )


def coerce_slot_selector(payload: Any) -> str | None:
    """Normalise a selector definition coming from front matter."""
    if isinstance(payload, str):
        candidate = payload.strip()
        return candidate or None
    if isinstance(payload, Mapping):
        for key in ("label", "title", "section"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def parse_slot_mapping(raw: Any) -> dict[str, str]:
    """Parse slot mappings declared in front matter structures."""
    overrides: dict[str, str] = {}
    if not raw:
        return overrides

    if isinstance(raw, Mapping):
        for slot_name, payload in raw.items():
            if not isinstance(slot_name, str):
                continue
            selector = coerce_slot_selector(payload)
            if selector:
                key = slot_name.strip()
                if key:
                    overrides[key] = selector
        return overrides

    if isinstance(raw, Iterable) and not isinstance(raw, str | bytes):
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            slot_name = entry.get("target") or entry.get("slot")
            if not isinstance(slot_name, str):
                continue
            selector = entry.get("label") or entry.get("title") or entry.get("section")
            selector_value = coerce_slot_selector(selector)
            if not selector_value:
                selector_value = coerce_slot_selector(entry)
            slot_key = slot_name.strip()
            if slot_key and selector_value:
                overrides[slot_key] = selector_value
        return overrides

    if isinstance(raw, str):
        entry = raw.strip()
        if entry and ":" in entry:
            name, selector = entry.split(":", 1)
            name = name.strip()
            selector = selector.strip()
            if name and selector:
                overrides[name] = selector
        return overrides

    return overrides


def extract_front_matter_slots(front_matter: Mapping[str, Any]) -> dict[str, str]:
    """Collect slot overrides defined in document front matter."""
    overrides: dict[str, str] = {}

    meta_section = front_matter.get("meta")
    if isinstance(meta_section, Mapping):
        meta_slots = meta_section.get("slots") or meta_section.get("entrypoints")
        overrides.update(parse_slot_mapping(meta_slots))

    root_slots = front_matter.get("slots") or front_matter.get("entrypoints")
    overrides.update(parse_slot_mapping(root_slots))

    return overrides


def extract_front_matter_bibliography(front_matter: Mapping[str, Any] | None) -> dict[str, str]:
    """Return DOI mappings declared in the document front matter."""
    if not isinstance(front_matter, Mapping):
        return {}

    bibliography: dict[str, str] = {}
    containers: list[Any] = []
    meta_section = front_matter.get("meta")
    if isinstance(meta_section, Mapping):
        containers.append(meta_section.get("bibliography"))
    containers.append(front_matter.get("bibliography"))

    for candidate in containers:
        if not isinstance(candidate, Mapping):
            continue
        for key, value in candidate.items():
            if not isinstance(key, str):
                continue
            doi = _coerce_bibliography_doi(value)
            if not doi:
                continue
            bibliography[key] = doi

    return bibliography


def _coerce_bibliography_doi(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, Mapping):
        candidate = value.get("doi")
        if isinstance(candidate, str):
            stripped = candidate.strip()
            if stripped:
                return stripped
    return None


def extract_slot_fragments(
    html: str,
    requests: Mapping[str, str],
    default_slot: str,
    *,
    slot_definitions: Mapping[str, TemplateSlot],
    parser_backend: str,
) -> tuple[list[SlotFragment], list[str]]:
    """Split the HTML document into fragments mapped to template slots."""
    try:
        soup = BeautifulSoup(html, parser_backend)
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")

    container = soup.body or soup
    document_html = "".join(str(node) for node in container.contents)

    wildcard_values = {
        DOCUMENT_SELECTOR_SENTINEL,
        DOCUMENT_SELECTOR_SENTINEL.lower(),
        "*",
    }
    full_document_slots: list[str] = []
    filtered_requests: dict[str, str] = {}
    for slot_name, selector in requests.items():
        if not selector:
            continue
        token = selector.strip()
        if token.lower() in wildcard_values:
            full_document_slots.append(slot_name)
            continue
        filtered_requests[slot_name] = selector

    headings: list[tuple[int, Tag]] = []
    for index, heading in enumerate(container.find_all(re.compile(r"^h[1-6]$"), recursive=True)):
        headings.append((index, heading))

    matched: dict[str, tuple[int, Tag]] = {}
    missing: list[str] = []
    occupied_nodes: set[int] = set()

    for slot_name, selector in filtered_requests.items():
        if not selector:
            continue
        target_label = selector.lstrip("#")
        matched_heading: tuple[int, Tag] | None = None
        for index, heading in headings:
            if id(heading) in occupied_nodes:
                continue
            node_id = heading.get("id")
            if isinstance(node_id, str) and node_id == target_label:
                matched_heading = (index, heading)
                break
        if matched_heading is None:
            for index, heading in headings:
                if id(heading) in occupied_nodes:
                    continue
                if heading.get_text(strip=True) == selector:
                    matched_heading = (index, heading)
                    break
        if matched_heading is None:
            missing.append(f"unable to locate section '{selector}' for slot '{slot_name}'")
            continue
        matched_index, heading = matched_heading
        occupied_nodes.add(id(heading))
        matched[slot_name] = (matched_index, heading)

    fragments: list[SlotFragment] = []

    for offset, slot_name in enumerate(full_document_slots):
        fragments.append(
            SlotFragment(
                name=slot_name,
                html=document_html,
                position=-(len(full_document_slots) - offset),
            )
        )

    for slot_name, (order, heading) in sorted(matched.items(), key=lambda item: item[1][0]):
        section_nodes = collect_section_nodes(heading)
        slot_config = slot_definitions.get(slot_name)
        strip_heading = bool(slot_config.strip_heading) if slot_config else False
        render_nodes = list(section_nodes)
        if strip_heading and render_nodes:
            render_nodes = render_nodes[1:]
            while render_nodes and isinstance(render_nodes[0], NavigableString):
                if str(render_nodes[0]).strip():
                    break
                render_nodes.pop(0)
        html_fragment = "".join(str(node) for node in render_nodes)
        fragments.append(SlotFragment(name=slot_name, html=html_fragment, position=order))
        for node in section_nodes:
            if hasattr(node, "extract"):
                node.extract()

    container = soup.body or soup
    if full_document_slots:
        remainder_html = ""
    else:
        remainder_html = "".join(str(node) for node in container.contents)

    remainder_position = min(fragment.position for fragment in fragments) - 1 if fragments else -1

    fragments.append(
        SlotFragment(name=default_slot, html=remainder_html, position=remainder_position)
    )

    fragments.sort(key=lambda fragment: fragment.position)
    return fragments, missing


def collect_section_nodes(heading: Tag) -> list[Any]:
    """Collect a heading node and its associated section content."""
    nodes: list[Any] = [heading]
    heading_level = heading_level_for(heading)
    for sibling in heading.next_siblings:
        if isinstance(sibling, NavigableString):
            nodes.append(sibling)
            continue
        if isinstance(sibling, Tag):
            if re.fullmatch(r"h[1-6]", sibling.name or ""):
                sibling_level = heading_level_for(sibling)
                if sibling_level <= heading_level:
                    break
            nodes.append(sibling)
    return nodes


def heading_level_for(node: Tag) -> int:
    """Return the numeric level of a heading element."""
    name = node.name or ""
    if not re.fullmatch(r"h[1-6]", name):
        raise ValueError(f"Expected heading element, got '{name}'.")
    return int(name[1])


def copy_document_state(target: DocumentState, source: DocumentState) -> None:
    """Synchronise ``target`` with a source ``DocumentState`` instance."""
    for metadata_field in dataclasses.fields(DocumentState):
        setattr(target, metadata_field.name, copy.deepcopy(getattr(source, metadata_field.name)))


def extract_content(html: str, selector: str) -> str:
    """Extract and return the inner HTML for the first element matching selector."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")

    element = soup.select_one(selector)
    if element is None:
        raise ValueError(f"Unable to locate content using selector '{selector}'.")
    return element.decode_contents()


def persist_debug_artifacts(output_dir: Path, source: Path, html: str) -> None:
    """Persist intermediate HTML snapshots to aid debugging."""
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_path = output_dir / f"{source.stem}.debug.html"
    debug_path.write_text(html, encoding="utf-8")


def render_with_fallback(
    renderer_factory: Callable[[], LaTeXRenderer],
    html: str,
    runtime: dict[str, object],
    bibliography: Mapping[str, dict[str, Any]] | None = None,
    *,
    state: DocumentState | None = None,
) -> tuple[str, DocumentState]:
    """Render HTML to LaTeX, retrying with fallback converters when available."""
    attempts = 0
    bibliography_payload = dict(bibliography or {})
    base_state = state

    while True:
        current_state = (
            copy.deepcopy(base_state)
            if base_state is not None
            else DocumentState(bibliography=dict(bibliography_payload))
        )

        renderer = renderer_factory()
        try:
            output = renderer.render(html, runtime=runtime, state=current_state)
        except LatexRenderingError as exc:
            attempts += 1
            if attempts >= 5 or not attempt_transformer_fallback(exc):
                raise
            continue

        if base_state is not None:
            copy_document_state(base_state, current_state)
            return output, base_state

        return output, current_state


def attempt_transformer_fallback(error: LatexRenderingError) -> bool:
    """Register placeholder converters when known transformers are unavailable."""
    cause = error.__cause__
    if not isinstance(cause, TransformerExecutionError):
        return False

    message = str(cause).lower()
    applied = False

    if "drawio" in message:
        return False
    if "mermaid" in message:
        return False
    if ("fetch-image" in message or "fetch image" in message) and not has_converter("fetch-image"):
        register_converter("fetch-image", _FallbackConverter("image"))
        applied = True
    return applied


def ensure_fallback_converters() -> None:
    """Install placeholder converters for optional transformer dependencies."""
    if is_docker_available():
        return

    if not has_converter("fetch-image"):
        register_converter("fetch-image", _FallbackConverter("image"))


class _FallbackConverter:
    def __init__(self, name: str):
        self.name = name

    def __call__(self, source: Path | str, *, output_dir: Path, **_: Any) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        original = str(source) if isinstance(source, Path) else source
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:12]
        suffix = Path(original).suffix or ".txt"
        filename = f"{self.name}-{digest}.pdf"
        target = output_dir / filename
        target.write_text(
            f"Placeholder PDF for {self.name} ({suffix})",
            encoding="utf-8",
        )
        return target


def format_rendering_error(error: LatexRenderingError) -> str:
    """Format a human-readable rendering failure summary."""
    cause = error.__cause__
    if cause is None:
        return str(error)
    return f"LaTeX rendering failed: {cause}"
