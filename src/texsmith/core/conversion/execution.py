"""Execution context resolution for conversion workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.conversion_contexts import GenerationStrategy
from texsmith.core.documents import Document
from texsmith.core.execution import ExecutionContext
from texsmith.core.templates.runtime import (
    TemplateRuntime,
    build_template_overrides,
    resolve_template_language,
)

from .debug import ensure_emitter, raise_conversion_error
from .inputs import InlineBibliographyValidationError, extract_front_matter_bibliography
from .models import ConversionRequest
from .templates import (
    _build_mustache_defaults,
    _merge_template_overrides,
    _replace_mustaches_in_html,
)


def resolve_execution_context(
    document: Document,
    request: ConversionRequest,
    *,
    template_runtime: TemplateRuntime | None = None,
    output_dir: Path | None = None,
    slot_overrides: Mapping[str, str] | None = None,
    template_overrides: Mapping[str, Any] | None = None,
    bibliography_files: Sequence[Path] | None = None,
    preloaded_bibliography: BibliographyCollection | None = None,
    seen_bibliography_issues: set[tuple[str, str | None, str | None]] | None = None,
) -> ExecutionContext:
    """Resolve all inputs into a single execution context for conversion."""
    emitter = ensure_emitter(request.emitter)
    document = document.prepare_for_conversion()

    generation = GenerationStrategy(
        copy_assets=request.copy_assets,
        convert_assets=request.convert_assets,
        hash_assets=request.hash_assets,
        prefer_inputs=False,
        persist_manifest=request.manifest,
    )

    resolved_language = resolve_template_language(request.language, document.front_matter)
    document.language = resolved_language

    slot_requests = dict(document.slot_requests)
    if slot_overrides:
        slot_requests.update(dict(slot_overrides))

    overrides = build_template_overrides(document.front_matter)
    if template_overrides:
        overrides = _merge_template_overrides(overrides, template_overrides)

    press_section = overrides.get("press")
    if not isinstance(press_section, dict):
        press_section = None

    def _ensure_press_section() -> dict[str, Any]:
        nonlocal press_section
        if press_section is None:
            press_section = {}
            overrides["press"] = press_section
        return press_section

    if document.extracted_title:
        overrides.setdefault("title", document.extracted_title)
        _ensure_press_section().setdefault("title", document.extracted_title)

    if press_section:
        if isinstance(press_section.get("fragments"), list):
            overrides["fragments"] = list(press_section["fragments"])
        if isinstance(press_section.get("callouts"), dict):
            overrides["callouts"] = dict(press_section["callouts"])

    overrides.setdefault("language", resolved_language)
    if press_section is not None or "press" in overrides:
        _ensure_press_section().setdefault("language", resolved_language)

    callouts_section = overrides.get("callouts")
    if isinstance(callouts_section, dict):
        style_value = callouts_section.get("style")
        if isinstance(style_value, str) and style_value.strip():
            overrides.setdefault("callout_style", style_value.strip())

    overrides.setdefault("_source_dir", str(document.source_path.parent))
    overrides.setdefault("_source_path", str(document.source_path))
    overrides.setdefault("source_dir", str(document.source_path.parent))
    if output_dir is not None:
        overrides["output_dir"] = str(output_dir)

    mustache_defaults = _build_mustache_defaults(overrides, document.front_matter)
    raw_contexts = (overrides, document.front_matter, mustache_defaults)
    overrides = _replace_mustaches_in_structure(
        overrides, raw_contexts, emitter, "template attributes"
    )
    document.set_front_matter(
        _replace_mustaches_in_structure(
            document.front_matter,
            raw_contexts,
            emitter,
            str(document.source_path),
        )
    )
    merged_contexts = (overrides, document.front_matter)
    document.set_html(
        _replace_mustaches_in_html(
            document.html,
            merged_contexts,
            emitter=emitter,
            source=str(document.source_path),
        )
    )

    bibliography_paths = list(bibliography_files or request.bibliography_files)
    issue_signatures = seen_bibliography_issues if seen_bibliography_issues is not None else set()
    bibliography_collection: BibliographyCollection | None = (
        preloaded_bibliography.clone() if preloaded_bibliography is not None else None
    )
    bibliography_map: dict[str, dict[str, Any]] = {}

    if bibliography_collection is None:
        bibliography_collection = BibliographyCollection()
        if bibliography_paths:
            bibliography_collection.load_files(bibliography_paths)

    try:
        inline_bibliography = extract_front_matter_bibliography(document.front_matter)
    except InlineBibliographyValidationError as exc:
        raise_conversion_error(emitter, str(exc), exc)
        inline_bibliography = []

    if inline_bibliography:
        source_label = document.source_path.stem
        output = output_dir or document.source_path.parent
        from .templates import _load_inline_bibliography

        _load_inline_bibliography(
            bibliography_collection,
            inline_bibliography,
            source_label=source_label,
            output_dir=Path(output),
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

    document.bibliography = bibliography_map

    fragments_list = _resolve_fragments_list(
        template_runtime,
        overrides.get("fragments"),
        request.enable_fragments,
        request.disable_fragments,
    )

    runtime_common: dict[str, object] = {
        "language": resolved_language,
        "copy_assets": generation.copy_assets,
        "convert_assets": generation.convert_assets,
        "hash_assets": generation.hash_assets,
        "diagrams_backend": request.diagrams_backend or "playwright",
    }

    return ExecutionContext(
        document=document,
        request=request,
        output_dir=Path(output_dir) if output_dir is not None else None,
        template_runtime=template_runtime,
        template_overrides=dict(overrides),
        slot_requests=slot_requests,
        fragments=fragments_list,
        language=resolved_language,
        bibliography_collection=bibliography_collection,
        bibliography_map=bibliography_map,
        runtime_common=runtime_common,
        generation=generation,
    )


def _replace_mustaches_in_structure(
    payload: Mapping[str, Any],
    contexts: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    emitter: Any,
    source: str,
) -> dict[str, Any]:
    # Local adapter to preserve existing behavior in build_binder_context.
    from texsmith.core.mustache import replace_mustaches_in_structure

    return replace_mustaches_in_structure(payload, contexts, emitter=emitter, source=source)


def _resolve_fragments_list(
    runtime: TemplateRuntime | None,
    override_fragments: Any,
    enable: Sequence[str],
    disable: Sequence[str],
) -> list[str]:
    """Compute the final fragment list after applying enable/disable toggles."""

    def _clean_list(values: Sequence[str] | None) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        if not values:
            return cleaned
        for entry in values:
            name = str(entry).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        return cleaned

    base: list[str] = []
    if isinstance(override_fragments, list):
        base = _clean_list(override_fragments)
    elif runtime and runtime.extras:
        fragments = runtime.extras.get("fragments")
        if isinstance(fragments, list):
            base = _clean_list(fragments)

    enable_list = _clean_list(enable)
    disable_list = _clean_list(disable)

    if not base and not enable_list and not disable_list:
        return []

    result = [entry for entry in base if entry not in disable_list]
    for entry in enable_list:
        if entry not in result:
            result.append(entry)
    return result
