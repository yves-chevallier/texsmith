"""Turn inline bibliography entries into a ``.bib`` the backends can cite.

A front-matter entry is either a complete record or a DOI to fetch. The fetch
is cached twice: in the user cache directory, and in a
``texsmith-doi-cache.yaml`` beside the output so a rebuild of the same
document is offline. ``passes/doi.py`` reuses the two cache helpers, which is
why they live here and not in the template layer they were written in.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pybtex.exceptions import PybtexError
from slugify import slugify
import yaml

from texsmith.core.diagnostics import DiagnosticEmitter, record_event

from .collection import BibliographyCollection
from .inline import InlineBibliographyEntry
from .parsing import bibliography_data_from_inline_entry, bibliography_data_from_string


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .doi import DoiBibliographyFetcher


_DOI_SUPPORT: tuple[type[Exception], Any] | None = None

__all__ = [
    "initialise_doi_cache",
    "inline_bibliography_source_path",
    "load_inline_bibliography",
    "resolve_bibliography_fetcher",
    "write_doi_cache",
]


def load_inline_bibliography(
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
    source_path = inline_bibliography_source_path(source_label)
    cache_entries, cache_path = initialise_doi_cache(output_dir)
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
                    resolver = resolve_bibliography_fetcher()
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
        write_doi_cache(cache_path, cache_entries)


def inline_bibliography_source_path(label: str) -> Path:
    slug = slugify(label, separator="-")
    if not slug:
        slug = "frontmatter"
    return Path(f"frontmatter-{slug}.bib")


def resolve_bibliography_fetcher() -> DoiBibliographyFetcher:
    """Return the default DOI fetcher.

    The single seam for substituting the fetcher: tests patch this function
    rather than a module-level cache. The import is lazy so ``requests`` is only
    pulled in when a document actually resolves a DOI.
    """
    from .doi import DoiBibliographyFetcher

    return DoiBibliographyFetcher()


_DOI_CACHE_FILENAME = "texsmith-doi-cache.yaml"


def initialise_doi_cache(output_dir: Path | None) -> tuple[dict[str, str], Path | None]:
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


def write_doi_cache(path: Path, entries: dict[str, str]) -> None:
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
        from .doi import DoiLookupError, normalise_doi

        _DOI_SUPPORT = {
            "lookup_error": DoiLookupError,
            "normalise": normalise_doi,
        }
    return _DOI_SUPPORT["lookup_error"], _DOI_SUPPORT["normalise"]
