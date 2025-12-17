"""Template orchestration helpers powering the conversion pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import contextlib
import copy
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup, FeatureNotFound
from bs4.element import NavigableString, Tag
from pybtex.exceptions import PybtexError
from slugify import slugify
import yaml

from ..bibliography.collection import BibliographyCollection
from ..bibliography.parsing import (
    bibliography_data_from_inline_entry,
    bibliography_data_from_string,
)
from ..config import BookConfig
from ..conversion_contexts import BinderContext, DocumentContext, GenerationStrategy
from ..diagnostics import DiagnosticEmitter
from ..mustache import replace_mustaches, replace_mustaches_in_structure
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
)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..bibliography.doi import DoiBibliographyFetcher


_DOI_SUPPORT: dict[str, Any] | None = None
# Exported for compatibility with existing monkeypatch patterns in tests.
DoiBibliographyFetcher: type[Any] | None = None


@dataclass(slots=True)
class SlotFragment:
    """HTML fragment mapped to a template slot with position metadata."""

    name: str
    html: str
    position: int
    heading_levels: list[int] = field(default_factory=list)


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
    session_overrides: Mapping[str, Any] | None = None,
    preloaded_bibliography: BibliographyCollection | None = None,
    seen_bibliography_issues: set[tuple[str, str | None, str | None]] | None = None,
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

    issue_signatures = seen_bibliography_issues if seen_bibliography_issues is not None else set()
    bibliography_collection: BibliographyCollection | None = (
        preloaded_bibliography.clone() if preloaded_bibliography is not None else None
    )
    bibliography_map: dict[str, dict[str, Any]] = {}

    if bibliography_collection is None:
        bibliography_collection = BibliographyCollection()
        if bibliography_files:
            bibliography_collection.load_files(bibliography_files)

    if inline_bibliography:
        _load_inline_bibliography(
            bibliography_collection,
            inline_bibliography,
            source_label=document_context.source_path.stem,
            output_dir=output_dir,
            emitter=emitter,
        )

    bibliography_map = bibliography_collection.to_dict()
    for issue in bibliography_collection.issues:
        signature = (issue.message, issue.key, str(issue.source) if issue.source else None)
        if signature in issue_signatures:
            continue
        prefix = f"[{issue.key}] " if issue.key else ""
        source_hint = f" ({issue.source})" if issue.source else ""
        emitter.warning(f"{prefix}{issue.message}{source_hint}")
        issue_signatures.add(signature)

    document_context.bibliography = bibliography_map

    slot_requests = dict(document_context.slot_requests)
    if slot_overrides:
        slot_requests.update(dict(slot_overrides))

    template_overrides = build_template_overrides(document_context.front_matter)
    if session_overrides:
        template_overrides = _merge_template_overrides(template_overrides, session_overrides)

    press_section = template_overrides.get("press")
    if not isinstance(press_section, dict):
        press_section = None

    def _ensure_press_section() -> dict[str, Any]:
        nonlocal press_section
        if press_section is None:
            press_section = {}
            template_overrides["press"] = press_section
        return press_section

    if document_context.extracted_title:
        template_overrides.setdefault("title", document_context.extracted_title)
        _ensure_press_section().setdefault("title", document_context.extracted_title)

    template_overrides.setdefault("language", resolved_language)
    if press_section is not None or "press" in template_overrides:
        _ensure_press_section().setdefault("language", resolved_language)

    template_overrides.setdefault("_source_dir", str(document_context.source_path.parent))
    template_overrides.setdefault("_source_path", str(document_context.source_path))
    template_overrides.setdefault("source_dir", str(document_context.source_path.parent))
    template_overrides["output_dir"] = str(output_dir)

    raw_contexts = (template_overrides, document_context.front_matter)
    template_overrides = replace_mustaches_in_structure(
        template_overrides, raw_contexts, emitter=emitter, source="template attributes"
    )
    document_context.front_matter = replace_mustaches_in_structure(
        document_context.front_matter,
        raw_contexts,
        emitter=emitter,
        source=str(document_context.source_path),
    )
    merged_contexts = (template_overrides, document_context.front_matter)
    if isinstance(document_context.html, str):
        document_context.html = replace_mustaches(
            document_context.html,
            merged_contexts,
            emitter=emitter,
            source=str(document_context.source_path),
        )

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

    if binding.runtime and binding.runtime.extras:
        template_mermaid = binding.runtime.extras.get("mermaid_config")
        if template_mermaid and not config.mermaid_config:
            config.mermaid_config = Path(template_mermaid)

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


def _merge_template_overrides(
    base: Mapping[str, Any], overrides: Mapping[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(dict(base))

    def _merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, Mapping):
                existing = target.get(key)
                nested: dict[str, Any] = dict(existing) if isinstance(existing, Mapping) else {}
                _merge(nested, value)
                target[key] = nested
            else:
                target[key] = copy.deepcopy(value)

    _merge(merged, overrides)
    return merged


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
    document_nodes = list(container.contents)

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
                heading_levels=_heading_levels_for_nodes(document_nodes),
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
        fragments.append(
            SlotFragment(
                name=slot_name,
                html=html_fragment,
                position=order,
                heading_levels=_heading_levels_for_nodes(render_nodes),
            )
        )
        for node in section_nodes:
            if hasattr(node, "extract"):
                node.extract()

    container = soup.body or soup
    if full_document_slots:
        remainder_html = ""
    else:
        remainder_html = "".join(str(node) for node in container.contents)

    remainder_position = max(fragment.position for fragment in fragments) + 1 if fragments else 0

    fragments.append(
        SlotFragment(
            name=default_slot,
            html=remainder_html,
            position=remainder_position,
            heading_levels=_heading_levels_for_nodes(container.contents),
        )
    )

    fragments.sort(key=lambda fragment: fragment.position)
    return fragments, missing


def _heading_levels_for_nodes(nodes: Iterable[Any]) -> list[int]:
    """Return heading levels discovered in the given node sequence (document order)."""
    levels: list[int] = []

    def _walk(node: Any) -> None:
        if isinstance(node, Tag):
            if re.fullmatch(r"h[1-6]", node.name or ""):
                with contextlib.suppress(ValueError):
                    levels.append(heading_level_for(node))
            for child in node.children:
                _walk(child)

    for node in nodes:
        _walk(node)

    return levels


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


def compute_heading_offset(
    html: str,
    *,
    drop_first_heading: bool = False,
    parser_backend: str = "html.parser",
) -> int:
    """Return the offset required to align the top heading to level 1.

    The shallowest heading in the fragment counts as offset ``0``; headings
    starting at ``<h2>`` therefore yield ``-1``. When ``drop_first_heading`` is
    true the first heading is ignored to mirror title promotion.
    """
    try:
        soup = BeautifulSoup(html, parser_backend)
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")

    headings = soup.find_all(re.compile(r"^h[1-6]$"), recursive=True)
    if drop_first_heading and headings:
        headings = headings[1:]

    minimum: int | None = None
    for heading in headings:
        try:
            level = heading_level_for(heading)
        except ValueError:
            continue
        if minimum is None or level < minimum:
            minimum = level

    if minimum is None:
        return 0
    return 1 - minimum


def _load_inline_bibliography(
    collection: BibliographyCollection,
    entries: Mapping[str, InlineBibliographyEntry],
    *,
    source_label: str,
    output_dir: Path | None = None,
    emitter: DiagnosticEmitter,
    fetcher: DoiBibliographyFetcher | None = None,
) -> None:
    if not entries:
        return

    resolver = fetcher
    source_path = _inline_bibliography_source_path(source_label)
    cache_entries, cache_path = _initialise_doi_cache(output_dir)
    cache_dirty = False
    doi_support: tuple[type[Exception], Any] | None = None

    for key, entry in entries.items():
        if entry.doi:
            if doi_support is None:
                _, lookup_error_cls, normalise_doi_fn = _ensure_doi_support()
                doi_support = (lookup_error_cls, normalise_doi_fn)
            lookup_error_cls, normalise_doi_fn = doi_support
            doi_value = entry.doi
            try:
                doi_key = normalise_doi_fn(doi_value)
            except lookup_error_cls as exc:
                emitter.warning(f"Failed to resolve DOI '{doi_value}' for '{key}': {exc}")
                continue

            payload = cache_entries.get(doi_key)
            cache_mode = "doi_cache" if payload is not None else "doi"

            if payload is None:
                if resolver is None:
                    resolver = _resolve_bibliography_fetcher()
                try:
                    payload = resolver.fetch(doi_value)
                except lookup_error_cls as exc:
                    emitter.warning(f"Failed to resolve DOI '{doi_value}' for '{key}': {exc}")
                    continue
                cache_entries[doi_key] = payload
                cache_dirty = True

            try:
                data = bibliography_data_from_string(payload, key)
            except PybtexError as exc:
                emitter.warning(f"Failed to parse bibliography entry '{key}': {exc}")
                if cache_mode == "doi":
                    cache_entries.pop(doi_key, None)
                continue
            doi_source = source_path.with_stem(f"{source_path.stem}-doi")
            collection.load_data(data, source=doi_source)
            record_event(
                emitter,
                "doi_fetch",
                {
                    "key": key,
                    "value": doi_value,
                    "mode": cache_mode,
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

    if cache_dirty and cache_path is not None:
        _write_doi_cache(cache_path, cache_entries)


def _inline_bibliography_source_path(label: str) -> Path:
    slug = slugify(label, separator="-")
    if not slug:
        slug = "frontmatter"
    return Path(f"frontmatter-{slug}.bib")


def _resolve_bibliography_fetcher() -> DoiBibliographyFetcher:
    fetcher_cls, _, _ = _ensure_doi_support()
    return fetcher_cls()


_DOI_CACHE_FILENAME = "texsmith-doi-cache.yaml"


def _initialise_doi_cache(output_dir: Path | None) -> tuple[dict[str, str], Path | None]:
    if output_dir is None:
        return {}, None

    cache_path = output_dir / _DOI_CACHE_FILENAME
    try:
        raw_text = cache_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, cache_path
    except OSError:
        return {}, cache_path

    try:
        payload = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError:
        return {}, cache_path

    entries_payload: Any
    if isinstance(payload, dict) and isinstance(payload.get("entries"), dict):
        entries_payload = payload["entries"]
    elif isinstance(payload, dict):
        entries_payload = payload
    else:
        entries_payload = {}

    entries: dict[str, str] = {}
    normalise_fn: Any | None = None
    lookup_error_cls: type[Exception] | None = None
    if isinstance(entries_payload, dict):
        for key, value in entries_payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            try:
                if normalise_fn is None:
                    _, lookup_error_cls, normalise_fn = _ensure_doi_support()
                normalised = normalise_fn(key)
            except Exception as exc:
                if lookup_error_cls is not None and isinstance(exc, lookup_error_cls):
                    continue
                raise
            entries[normalised] = value

    return entries, cache_path


def _write_doi_cache(path: Path, entries: dict[str, str]) -> None:
    document = {
        "version": 1,
        "entries": {key: entries[key] for key in sorted(entries)},
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(
                document,
                sort_keys=True,
                default_flow_style=False,
                encoding=None,
            ),
            encoding="utf-8",
        )
    except OSError:
        return


def _ensure_doi_support() -> tuple[type[Any], type[Exception], Any]:
    """Lazily import DOI helpers to avoid pulling in requests unless required."""
    global _DOI_SUPPORT, DoiBibliographyFetcher

    if _DOI_SUPPORT is None:
        from ..bibliography.doi import DoiLookupError, normalise_doi

        _DOI_SUPPORT = {
            "lookup_error": DoiLookupError,
            "normalise": normalise_doi,
        }
    if DoiBibliographyFetcher is None:
        from ..bibliography.doi import DoiBibliographyFetcher as _Fetcher

        DoiBibliographyFetcher = _Fetcher

    assert _DOI_SUPPORT is not None
    assert DoiBibliographyFetcher is not None
    return (
        DoiBibliographyFetcher,
        _DOI_SUPPORT["lookup_error"],
        _DOI_SUPPORT["normalise"],
    )


__all__ = [
    "SlotFragment",
    "build_binder_context",
    "collect_section_nodes",
    "compute_heading_offset",
    "extract_slot_fragments",
    "heading_level_for",
]
