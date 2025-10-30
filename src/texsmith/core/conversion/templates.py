"""Template orchestration helpers powering the conversion pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, FeatureNotFound
from bs4.element import NavigableString, Tag
from pybtex.exceptions import PybtexError
from slugify import slugify

from ..bibliography import (
    BibliographyCollection,
    DoiBibliographyFetcher,
    DoiLookupError,
    bibliography_data_from_inline_entry,
    bibliography_data_from_string,
)
from ..config import BookConfig
from ..conversion_contexts import BinderContext, DocumentContext, GenerationStrategy
from ..diagnostics import DiagnosticEmitter
from ..templates import (
    TemplateBinding,
    TemplateError,
    TemplateRuntime,
    TemplateSlot,
    build_template_overrides,
    resolve_template_binding,
    resolve_template_language,
)
from .debug import debug_enabled, ensure_emitter, raise_conversion_error, record_event
from .inputs import (
    DOCUMENT_SELECTOR_SENTINEL,
    InlineBibliographyEntry,
    InlineBibliographyValidationError,
    extract_front_matter_bibliography,
    extract_front_matter_slots,
)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..bibliography import DoiBibliographyFetcher


@dataclass(slots=True)
class SlotFragment:
    """HTML fragment mapped to a template slot with position metadata."""

    name: str
    html: str
    position: int


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
    emitter: DiagnosticEmitter | None,
    legacy_latex_accents: bool,
) -> BinderContext:
    """Prepare template bindings, bibliography data, and slot mappings."""
    emitter = ensure_emitter(emitter)
    resolved_language = resolve_template_language(requested_language, document_context.front_matter)
    document_context.language = resolved_language

    config = BookConfig(
        project_dir=document_context.source_path.parent,
        language=resolved_language,
        legacy_latex_accents=legacy_latex_accents,
    )

    try:
        inline_bibliography = extract_front_matter_bibliography(document_context.front_matter)
    except InlineBibliographyValidationError as exc:
        raise_conversion_error(emitter, str(exc), exc)

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
                emitter=emitter,
            )

    if bibliography_collection is not None:
        bibliography_map = bibliography_collection.to_dict()
        for issue in bibliography_collection.issues:
            prefix = f"[{issue.key}] " if issue.key else ""
            source_hint = f" ({issue.source})" if issue.source else ""
            emitter.warning(f"{prefix}{issue.message}{source_hint}")

    document_context.bibliography = bibliography_map

    slot_requests = dict(document_context.slot_requests)
    if slot_overrides:
        slot_requests.update(dict(slot_overrides))

    template_overrides = build_template_overrides(document_context.front_matter)
    if document_context.extracted_title:
        press_section = template_overrides.setdefault("press", {})
        if isinstance(press_section, dict):
            press_section.setdefault("title", document_context.extracted_title)
    template_overrides["language"] = resolved_language
    press_section = template_overrides.get("press")
    if isinstance(press_section, dict):
        press_section.setdefault("language", resolved_language)

    active_slot_requests: dict[str, str] = {}
    binding: TemplateBinding | None = None
    try:
        binding, active_slot_requests = resolve_template_binding(
            template=template,
            template_runtime=template_runtime,
            template_overrides=template_overrides,
            slot_requests=slot_requests,
            warn=lambda message: emitter.warning(message),
        )
    except TemplateError as exc:
        if debug_enabled(emitter):
            raise
        raise_conversion_error(emitter, str(exc), exc)
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


def _load_inline_bibliography(
    collection: BibliographyCollection,
    entries: Mapping[str, InlineBibliographyEntry],
    *,
    source_label: str,
    emitter: DiagnosticEmitter,
    fetcher: DoiBibliographyFetcher | None = None,
) -> None:
    if not entries:
        return

    resolver = fetcher
    source_path = _inline_bibliography_source_path(source_label)

    for key, entry in entries.items():
        if entry.doi:
            if resolver is None:
                resolver = _resolve_bibliography_fetcher()
            doi_value = entry.doi
            try:
                payload = resolver.fetch(doi_value)
            except DoiLookupError as exc:
                emitter.warning(f"Failed to resolve DOI '{doi_value}' for '{key}': {exc}")
                continue
            try:
                data = bibliography_data_from_string(payload, key)
            except PybtexError as exc:
                emitter.warning(f"Failed to parse bibliography entry '{key}': {exc}")
                continue
            collection.load_data(data, source=source_path)
            record_event(
                emitter,
                "doi_fetch",
                {
                    "key": key,
                    "value": doi_value,
                    "mode": "doi",
                    "source": source_label,
                    "resolved_source": str(source_path),
                },
            )
            continue

        if entry.is_manual:
            try:
                data = bibliography_data_from_inline_entry(key, entry)
            except (ValueError, PybtexError) as exc:
                emitter.warning(f"Failed to materialise bibliography entry '{key}': {exc}")
                continue
            collection.load_data(data, source=source_path)
            record_event(
                emitter,
                "inline_bibliography",
                {
                    "key": key,
                    "mode": "manual",
                    "source": source_label,
                    "resolved_source": str(source_path),
                },
            )
            continue

        emitter.warning(
            f"Bibliography entry '{key}' does not provide a DOI or manual fields; skipping."
        )


def _inline_bibliography_source_path(label: str) -> Path:
    slug = slugify(label, separator="-")
    if not slug:
        slug = "frontmatter"
    return Path(f"frontmatter-{slug}.bib")


def _resolve_bibliography_fetcher() -> DoiBibliographyFetcher:
    return DoiBibliographyFetcher()


__all__ = [
    "SlotFragment",
    "build_binder_context",
    "collect_section_nodes",
    "extract_slot_fragments",
    "heading_level_for",
]
