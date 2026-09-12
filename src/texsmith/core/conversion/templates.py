"""Template orchestration helpers powering the conversion pipeline."""

from __future__ import annotations

from collections.abc import Mapping
import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pybtex.exceptions import PybtexError
from slugify import slugify
import yaml

from ..bibliography.collection import BibliographyCollection
from ..bibliography.parsing import (
    bibliography_data_from_inline_entry,
    bibliography_data_from_string,
)
from ..config import BookConfig
from ..conversion_contexts import ConversionContext
from ..diagnostics import DiagnosticEmitter
from ..templates import TemplateBinding, TemplateError, resolve_template_binding
from .debug import debug_enabled, ensure_emitter, raise_conversion_error, record_event
from .inputs import InlineBibliographyEntry


if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..bibliography.doi import DoiBibliographyFetcher


_DOI_SUPPORT: dict[str, Any] | None = None


def _resolve_callout_style(*contexts: Mapping[str, Any] | None) -> str | None:
    for context in contexts:
        if not isinstance(context, Mapping):
            continue
        callouts = context.get("callouts")
        if isinstance(callouts, Mapping):
            style = callouts.get("style")
            if isinstance(style, str) and style.strip():
                return style.strip()
        press_section = context.get("press")
        if isinstance(press_section, Mapping):
            press_callouts = press_section.get("callouts")
            if isinstance(press_callouts, Mapping):
                style = press_callouts.get("style")
                if isinstance(style, str) and style.strip():
                    return style.strip()
            for key in ("callout_style", "callouts_style"):
                style = press_section.get(key)
                if isinstance(style, str) and style.strip():
                    return style.strip()
        for key in ("callout_style", "callouts_style"):
            style = context.get(key)
            if isinstance(style, str) and style.strip():
                return style.strip()
    return None


def _build_mustache_defaults(*contexts: Mapping[str, Any] | None) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    callout_style = _resolve_callout_style(*contexts) or "fancy"
    defaults["callouts"] = {"style": callout_style}
    return defaults


def bind_template(
    *,
    context: ConversionContext,
    template: str | None,
    emitter: DiagnosticEmitter | None,
    legacy_latex_accents: bool,
) -> ConversionContext:
    """Resolve the template binding and attach it to ``context``.

    The incoming :class:`ConversionContext` has its template-bound fields
    unset; this function selects the template, builds a :class:`BookConfig`
    from the resolved language, and stores both back on the context. The
    same object is returned (mutated in place) so callers can chain.
    """
    emitter = ensure_emitter(emitter)
    document = context.document

    config = BookConfig(
        project_dir=document.source_path.parent,
        language=context.language,
        legacy_latex_accents=legacy_latex_accents,
    )

    active_slot_requests: dict[str, str] = {}
    binding: TemplateBinding | None = None
    try:
        binding, active_slot_requests = resolve_template_binding(
            template=template,
            template_runtime=context.template_runtime,
            template_overrides=context.template_overrides,
            slot_requests=context.slot_requests,
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

    context.config = config
    context.template_binding = binding
    context.slot_requests = active_slot_requests
    return context


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
                lookup_error_cls, normalise_doi_fn = _ensure_doi_support()
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
    """Return the default DOI fetcher.

    The single seam for substituting the fetcher: tests patch this function
    rather than a module-level cache. The import is lazy so ``requests`` is only
    pulled in when a document actually resolves a DOI.
    """
    from ..bibliography.doi import DoiBibliographyFetcher

    return DoiBibliographyFetcher()


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
                    lookup_error_cls, normalise_fn = _ensure_doi_support()
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


def _ensure_doi_support() -> tuple[type[Exception], Any]:
    """Lazily import DOI helpers (error type + normaliser) to avoid pulling in requests unless required."""
    global _DOI_SUPPORT

    if _DOI_SUPPORT is None:
        from ..bibliography.doi import DoiLookupError, normalise_doi

        _DOI_SUPPORT = {
            "lookup_error": DoiLookupError,
            "normalise": normalise_doi,
        }
    return _DOI_SUPPORT["lookup_error"], _DOI_SUPPORT["normalise"]


__all__ = ["bind_template"]
