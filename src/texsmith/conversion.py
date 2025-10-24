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
from typing import Any

from bs4 import BeautifulSoup, FeatureNotFound, NavigableString, Tag

from .bibliography import BibliographyCollection
from .config import BookConfig
from .context import DocumentState
from .docker import is_docker_available
from .exceptions import LatexRenderingError, TransformerExecutionError
from .formatter import LaTeXFormatter
from .markdown import (
    DEFAULT_MARKDOWN_EXTENSIONS,
    MarkdownConversionError,
    MarkdownDocument,
    normalize_markdown_extensions,
    render_markdown,
)
from .renderer import LaTeXRenderer
from .templates import (
    TemplateError,
    TemplateSlot,
    WrappableTemplate,
    copy_template_assets,
    load_template,
)
from .transformers import register_converter


__all__ = [
    "ConversionCallbacks",
    "ConversionError",
    "ConversionResult",
    "MarkdownConversionError",
    "TemplateRuntime",
    "UnsupportedInputError",
    "DEFAULT_TEMPLATE_LANGUAGE",
    "DOCUMENT_SELECTOR_SENTINEL",
    "attempt_transformer_fallback",
    "build_template_overrides",
    "coerce_base_level",
    "coerce_slot_selector",
    "convert_document",
    "copy_document_state",
    "extract_base_level_override",
    "extract_content",
    "extract_front_matter_slots",
    "extract_language_from_front_matter",
    "extract_slot_fragments",
    "format_rendering_error",
    "heading_level_for",
    "load_template_runtime",
    "normalise_template_language",
    "parse_slot_mapping",
    "persist_debug_artifacts",
    "ensure_fallback_converters",
    "render_with_fallback",
    "resolve_template_language",
]


logger = logging.getLogger(__name__)


DEFAULT_TEMPLATE_LANGUAGE = "english"

_BABEL_LANGUAGE_ALIASES = {
    "ad": "catalan",
    "ca": "catalan",
    "cs": "czech",
    "da": "danish",
    "de": "ngerman",
    "de-de": "ngerman",
    "en": "english",
    "en-gb": "british",
    "en-us": "english",
    "en-au": "australian",
    "en-ca": "canadian",
    "es": "spanish",
    "es-es": "spanish",
    "es-mx": "mexican",
    "fi": "finnish",
    "fr": "french",
    "fr-fr": "french",
    "fr-ca": "canadien",
    "it": "italian",
    "nl": "dutch",
    "nb": "norwegian",
    "nn": "nynorsk",
    "pl": "polish",
    "pt": "portuguese",
    "pt-br": "brazilian",
    "ro": "romanian",
    "ru": "russian",
    "sk": "slovak",
    "sl": "slovene",
    "sv": "swedish",
    "tr": "turkish",
}


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


@dataclass(slots=True)
class TemplateRuntime:
    """Resolved template metadata reused across conversions."""

    instance: WrappableTemplate
    name: str
    engine: str | None
    requires_shell_escape: bool
    slots: dict[str, TemplateSlot]
    default_slot: str
    formatter_overrides: dict[str, Path]
    base_level: int | None


class ConversionError(Exception):
    """Raised when a conversion fails and cannot recover."""


class UnsupportedInputError(Exception):
    """Raised when a CLI input argument cannot be processed."""


class InputKind(Enum):
    MARKDOWN = "markdown"
    HTML = "html"


def coerce_base_level(value: Any, *, allow_none: bool = True) -> int | None:
    if value is None:
        if allow_none:
            return None
        raise TemplateError("Base level value is missing.")

    if isinstance(value, bool):
        raise TemplateError(
            "Base level must be an integer, booleans are not supported."
        )

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            if allow_none:
                return None
            raise TemplateError("Base level value cannot be empty.")
        try:
            return int(candidate)
        except ValueError as exc:  # pragma: no cover - defensive
            raise TemplateError(
                f"Invalid base level '{value}'. Expected an integer value."
            ) from exc

    raise TemplateError(
        "Base level should be provided as an integer value, "
        f"got type '{type(value).__name__}'."
    )


def extract_base_level_override(overrides: Mapping[str, Any] | None) -> Any:
    if not overrides:
        return None

    direct_candidate = overrides.get("base_level")
    meta_section = overrides.get("meta")
    meta_candidate = None
    if isinstance(meta_section, Mapping):
        meta_candidate = meta_section.get("base_level")

    # Prefer explicit meta entry as it mirrors template attributes closely.
    return meta_candidate if meta_candidate is not None else direct_candidate


def load_template_runtime(template: str) -> TemplateRuntime:
    """Resolve template metadata for repeated conversions."""

    template_instance = load_template(template)

    template_base = coerce_base_level(
        template_instance.info.attributes.get("base_level"),
    )

    slots, default_slot = template_instance.info.resolve_slots()
    formatter_overrides = dict(template_instance.iter_formatter_overrides())

    return TemplateRuntime(
        instance=template_instance,
        name=template_instance.info.name,
        engine=template_instance.info.engine,
        requires_shell_escape=bool(template_instance.info.shell_escape),
        slots=slots,
        default_slot=default_slot,
        formatter_overrides=formatter_overrides,
        base_level=template_base,
    )


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


def _fail(
    callbacks: ConversionCallbacks | None,
    message: str,
    exc: Exception,
) -> None:
    _emit_error(callbacks, message, exception=exc)
    raise ConversionError(message) from exc


def convert_document(
    input_path: Path,
    output_dir: Path,
    selector: str,
    full_document: bool,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
    parser: str | None,
    disable_fallback_converters: bool,
    copy_assets: bool,
    manifest: bool,
    template: str | None,
    persist_debug_html: bool,
    language: str | None,
    slot_overrides: Mapping[str, str] | None,
    markdown_extensions: list[str],
    bibliography_files: list[Path],
    *,
    input_format: InputKind,
    state: DocumentState | None = None,
    template_runtime: TemplateRuntime | None = None,
    wrap_document: bool = True,
    callbacks: ConversionCallbacks | None = None,
) -> ConversionResult:
    try:
        output_dir = output_dir.resolve()
        input_payload = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        if _debug_enabled(callbacks):
            raise
        _fail(callbacks, f"Failed to read input document: {exc}", exc)

    front_matter: dict[str, Any] = {}
    html = input_payload
    is_markdown = input_format is InputKind.MARKDOWN
    if is_markdown:
        normalized_extensions = normalize_markdown_extensions(markdown_extensions)
        if not normalized_extensions:
            normalized_extensions = list(DEFAULT_MARKDOWN_EXTENSIONS)
        try:
            markdown_output: MarkdownDocument = render_markdown(
                input_payload, normalized_extensions
            )
        except MarkdownConversionError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(callbacks, str(exc), exc)
        html = markdown_output.html
        front_matter = markdown_output.front_matter

    if not full_document and not is_markdown:
        try:
            html = extract_content(html, selector)
        except ValueError:
            # Fallback to the entire document when the selector cannot be resolved.
            html = input_payload

    slot_requests = extract_front_matter_slots(front_matter)
    if slot_overrides:
        slot_requests.update(dict(slot_overrides))

    if persist_debug_html:
        persist_debug_artifacts(output_dir, input_path, html)

    resolved_language = resolve_template_language(language, front_matter)

    config = BookConfig(project_dir=input_path.parent, language=resolved_language)

    bibliography_collection: BibliographyCollection | None = None
    bibliography_map: dict[str, dict[str, Any]] = {}
    if bibliography_files:
        bibliography_collection = BibliographyCollection()
        bibliography_collection.load_files(bibliography_files)
        bibliography_map = bibliography_collection.to_dict()
        for issue in bibliography_collection.issues:
            prefix = f"[{issue.key}] " if issue.key else ""
            source_hint = f" ({issue.source})" if issue.source else ""
            _emit_warning(callbacks, f"{prefix}{issue.message}{source_hint}")

    renderer_kwargs: dict[str, Any] = {
        "output_root": output_dir,
        "copy_assets": copy_assets,
    }
    renderer_kwargs["parser"] = parser or "html.parser"

    template_overrides = build_template_overrides(front_matter)
    template_overrides["language"] = resolved_language
    meta_section = template_overrides.get("meta")
    if isinstance(meta_section, dict):
        meta_section.setdefault("language", resolved_language)

    try:
        override_base_level = extract_base_level_override(template_overrides)
        template_base_level = coerce_base_level(override_base_level)
    except TemplateError as exc:
        if _debug_enabled(callbacks):
            raise
        _fail(callbacks, str(exc), exc)

    template_info_engine: str | None = None
    template_requires_shell_escape = False
    template_instance: WrappableTemplate | None = None
    template_name: str | None = None
    formatter_overrides: dict[str, Path] = {}
    runtime = template_runtime
    if runtime is None and template:
        try:
            runtime = load_template_runtime(template)
        except TemplateError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(callbacks, str(exc), exc)

    if runtime is not None:
        template_instance = runtime.instance
        template_name = runtime.name
        template_info_engine = runtime.engine
        template_requires_shell_escape = runtime.requires_shell_escape
        formatter_overrides = dict(runtime.formatter_overrides)
        template_slots = runtime.slots
        default_slot = runtime.default_slot
        if template_base_level is None:
            template_base_level = runtime.base_level
    else:
        template_slots = {"mainmatter": TemplateSlot(default=True)}
        default_slot = "mainmatter"
        if slot_requests:
            for slot_name in slot_requests:
                _emit_warning(
                    callbacks,
                    (
                        f"slot '{slot_name}' was requested "
                        "but no template is selected; "
                        "ignoring."
                    ),
                )
            slot_requests = {}

    effective_base_level = template_base_level or 0
    slot_base_levels: dict[str, int] = {
        name: slot.resolve_level(effective_base_level)
        for name, slot in template_slots.items()
    }
    runtime_common: dict[str, object] = {
        "numbered": numbered,
        "source_dir": input_path.parent,
        "document_path": input_path,
        "copy_assets": copy_assets,
        "language": resolved_language,
    }
    if bibliography_map:
        runtime_common["bibliography"] = bibliography_map
    if template_name is not None:
        runtime_common["template"] = template_name
    if manifest:
        runtime_common["generate_manifest"] = True

    active_slot_requests: dict[str, str] = {}
    for slot_name, selector_value in slot_requests.items():
        if slot_name not in template_slots:
            template_hint = (
                f"template '{template_name}'" if template_name else "the template"
            )
            _emit_warning(
                callbacks,
                (
                    f"slot '{slot_name}' is not defined by {template_hint}; "
                    f"content will remain in '{default_slot}'."
                ),
            )
            continue
        active_slot_requests[slot_name] = selector_value

    parser_backend = str(renderer_kwargs.get("parser", "html.parser"))
    slot_fragments, missing_slots = extract_slot_fragments(
        html,
        active_slot_requests,
        default_slot,
        slot_definitions=template_slots,
        parser_backend=parser_backend,
    )
    for message in missing_slots:
        _emit_warning(callbacks, message)

    def renderer_factory() -> LaTeXRenderer:
        formatter = LaTeXFormatter()
        for key, override_path in formatter_overrides.items():
            formatter.override_template(key, override_path)
        return LaTeXRenderer(config=config, formatter=formatter, **renderer_kwargs)

    if not disable_fallback_converters:
        ensure_fallback_converters()

    slot_outputs: dict[str, str] = {}
    document_state: DocumentState | None = state
    drop_title_flag = bool(drop_title)
    for fragment in slot_fragments:
        runtime_fragment = dict(runtime_common)
        base_value = slot_base_levels.get(fragment.name, effective_base_level)
        runtime_fragment["base_level"] = base_value + base_level + heading_level
        if drop_title_flag:
            runtime_fragment["drop_title"] = True
            drop_title_flag = False
        try:
            fragment_output, document_state = render_with_fallback(
                renderer_factory,
                fragment.html,
                runtime_fragment,
                bibliography_map,
                state=document_state,
            )
        except LatexRenderingError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(callbacks, format_rendering_error(exc), exc)
        existing_fragment = slot_outputs.get(fragment.name, "")
        slot_outputs[fragment.name] = f"{existing_fragment}{fragment_output}"

    if document_state is None:
        document_state = DocumentState(bibliography=dict(bibliography_map))

    default_content = slot_outputs.get(default_slot)
    if default_content is None:
        default_content = ""
        slot_outputs[default_slot] = default_content
    latex_output = default_content

    citations = list(document_state.citations)
    bibliography_output: Path | None = None
    if citations and bibliography_collection is not None and bibliography_map:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            bibliography_output = output_dir / "texsmith-bibliography.bib"
            bibliography_collection.write_bibtex(bibliography_output, keys=citations)
        except OSError as exc:
            if _debug_enabled(callbacks):
                raise
            _emit_warning(callbacks, f"Failed to write bibliography file: {exc}")
            bibliography_output = None

    tex_path: Path | None = None
    if template_instance is not None and wrap_document:
        try:
            template_context = template_instance.prepare_context(
                latex_output,
                overrides=template_overrides if template_overrides else None,
            )
            for slot_name, fragment_output in slot_outputs.items():
                if slot_name == default_slot:
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
                output_dir,
                context=template_context,
                overrides=template_overrides if template_overrides else None,
            )
        except TemplateError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(callbacks, str(exc), exc)

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            tex_path = output_dir / f"{input_path.stem}.tex"
            tex_path.write_text(latex_output, encoding="utf-8")
        except OSError as exc:
            if _debug_enabled(callbacks):
                raise
            _fail(
                callbacks,
                f"Failed to write LaTeX output to '{output_dir}': {exc}",
                exc,
            )

    return ConversionResult(
        latex_output=latex_output,
        tex_path=tex_path,
        template_engine=template_info_engine,
        template_shell_escape=template_requires_shell_escape,
        language=resolved_language,
        has_bibliography=bool(citations),
        slot_outputs=dict(slot_outputs),
        default_slot=default_slot,
        document_state=document_state,
        bibliography_path=bibliography_output,
        template_overrides=dict(template_overrides),
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

    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
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
    for index, heading in enumerate(
        container.find_all(re.compile(r"^h[1-6]$"), recursive=True)
    ):
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
            missing.append(
                f"unable to locate section '{selector}' for slot '{slot_name}'"
            )
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

    for slot_name, (order, heading) in sorted(
        matched.items(), key=lambda item: item[1][0]
    ):
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
        fragments.append(
            SlotFragment(name=slot_name, html=html_fragment, position=order)
        )
        for node in section_nodes:
            if hasattr(node, "extract"):
                node.extract()

    container = soup.body or soup
    if full_document_slots:
        remainder_html = ""
    else:
        remainder_html = "".join(str(node) for node in container.contents)

    if fragments:
        remainder_position = min(fragment.position for fragment in fragments) - 1
    else:
        remainder_position = -1

    fragments.append(
        SlotFragment(
            name=default_slot, html=remainder_html, position=remainder_position
        )
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

    for field in dataclasses.fields(DocumentState):
        setattr(target, field.name, copy.deepcopy(getattr(source, field.name)))


def extract_content(html: str, selector: str) -> str:
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")

    element = soup.select_one(selector)
    if element is None:
        raise ValueError(f"Unable to locate content using selector '{selector}'.")
    return element.decode_contents()


def persist_debug_artifacts(output_dir: Path, source: Path, html: str) -> None:
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
    cause = error.__cause__
    if not isinstance(cause, TransformerExecutionError):
        return False

    message = str(cause).lower()
    applied = False

    if "drawio" in message:
        register_converter("drawio", _FallbackConverter("drawio"))
        applied = True
    if "mermaid" in message:
        register_converter("mermaid", _FallbackConverter("mermaid"))
        applied = True
    if "fetch-image" in message or "fetch image" in message:
        register_converter("fetch-image", _FallbackConverter("image"))
        applied = True
    return applied


def ensure_fallback_converters() -> None:
    if is_docker_available():
        return

    for name in ("drawio", "mermaid", "fetch-image"):
        register_converter(name, _FallbackConverter(name))


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
    cause = error.__cause__
    if cause is None:
        return str(error)
    return f"LaTeX rendering failed: {cause}"


def build_template_overrides(front_matter: Mapping[str, Any] | None) -> dict[str, Any]:
    if not front_matter:
        return {}

    if not isinstance(front_matter, Mapping):
        return {}

    meta_section = front_matter.get("meta")
    if isinstance(meta_section, Mapping):
        return {"meta": dict(meta_section)}

    return {"meta": dict(front_matter)}


def resolve_template_language(
    explicit: str | None,
    front_matter: Mapping[str, Any] | None,
) -> str:
    candidates = (
        normalise_template_language(explicit),
        normalise_template_language(extract_language_from_front_matter(front_matter)),
    )

    for candidate in candidates:
        if candidate:
            return candidate

    return DEFAULT_TEMPLATE_LANGUAGE


def extract_language_from_front_matter(
    front_matter: Mapping[str, Any] | None,
) -> str | None:
    if not isinstance(front_matter, Mapping):
        return None

    meta_entry = front_matter.get("meta")
    containers: tuple[Mapping[str, Any] | None, ...] = (
        meta_entry if isinstance(meta_entry, Mapping) else None,
        front_matter,
    )

    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for key in ("language", "lang"):
            value = container.get(key)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
    return None


def normalise_template_language(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    lowered = stripped.lower().replace("_", "-")
    alias = _BABEL_LANGUAGE_ALIASES.get(lowered)
    if alias:
        return alias

    primary = lowered.split("-", 1)[0]
    alias = _BABEL_LANGUAGE_ALIASES.get(primary)
    if alias:
        return alias

    if lowered.isalpha():
        return lowered

    return None
