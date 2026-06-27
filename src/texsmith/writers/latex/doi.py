"""On-demand DOI bibliography resolution used by the LaTeX writer.

When a citation key is a bare DOI, these helpers fetch and register the
corresponding bibliography entry. They are invoked lazily from
:mod:`texsmith.writers.latex.writer` through a duck-typed render context.
"""

from __future__ import annotations

import io
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any
import warnings

from pybtex.database.input import bibtex
from pybtex.exceptions import PybtexError


if TYPE_CHECKING:
    from texsmith.core.bibliography.collection import BibliographyCollection
    from texsmith.core.context import RenderContextLike


_DOI_KEY_PATTERN = r"10\.\d{4,9}/[^\s,\]]+"
_DOI_KEY_RE = re.compile(rf"^{_DOI_KEY_PATTERN}$")
_DEFAULT_DOI_SOURCE = Path("inline-doi-citations.bib")


def _is_doi_key(candidate: str) -> bool:
    """Return True when a citation key matches a DOI shape."""
    return bool(_DOI_KEY_RE.match(candidate.strip()))


def _emit_bibliography_warning(context: RenderContextLike, message: str) -> None:
    emitter = context.runtime.get("emitter")
    if emitter is not None:
        emitter.warning(message)
        return
    warnings.warn(message, stacklevel=2)


def _inline_doi_source_path(context: RenderContextLike) -> Path:
    """Return a synthetic source path for inline DOI citations."""
    document_path = context.runtime.get("document_path")
    if isinstance(document_path, Path):
        return Path(f"inline-doi-{document_path.stem}.bib")
    try:
        return Path(f"inline-doi-{Path(str(document_path)).stem}.bib")
    except Exception:
        return _DEFAULT_DOI_SOURCE


def _ensure_bibliography_runtime(
    context: RenderContextLike,
) -> tuple[dict[str, dict[str, object]], BibliographyCollection]:
    from texsmith.core.bibliography.collection import BibliographyCollection

    runtime_bibliography = context.runtime.get("bibliography")
    if not isinstance(runtime_bibliography, dict):
        runtime_bibliography = {}
        context.runtime["bibliography"] = runtime_bibliography

    collection = context.runtime.get("bibliography_collection")
    if not isinstance(collection, BibliographyCollection):
        collection = BibliographyCollection()
        context.runtime["bibliography_collection"] = collection

    return runtime_bibliography, collection


def _resolve_doi_fetcher(context: RenderContextLike) -> Any:
    from texsmith.core.bibliography.doi import DoiBibliographyFetcher

    fetcher = context.runtime.get("doi_fetcher")
    if fetcher is not None:
        return fetcher

    fetcher = DoiBibliographyFetcher()
    context.runtime["doi_fetcher"] = fetcher
    return fetcher


def _materialise_doi_entry(key: str, context: RenderContextLike) -> dict[str, object] | None:
    """Fetch and register a bibliography entry for a DOI citation."""
    from texsmith.core.bibliography.doi import DoiLookupError

    bibliography = context.state.bibliography
    runtime_bibliography, collection = _ensure_bibliography_runtime(context)

    fetcher = _resolve_doi_fetcher(context)
    fetch = getattr(fetcher, "fetch", None)
    if not callable(fetch):
        raise DoiLookupError("Configured DOI fetcher is missing a 'fetch' method.")

    try:
        payload = str(fetch(key))
    except DoiLookupError as exc:
        _emit_bibliography_warning(context, f"Failed to resolve DOI '{key}': {exc}")
        return None
    except Exception as exc:  # pragma: no cover - defensive fallback
        _emit_bibliography_warning(context, f"Failed to resolve DOI '{key}': {exc}")
        return None

    parser = bibtex.Parser()
    try:
        parsed = parser.parse_stream(io.StringIO(payload))
    except (OSError, PybtexError) as exc:
        _emit_bibliography_warning(context, f"Failed to parse bibliography entry '{key}': {exc}")
        return None
    if not parsed.entries:
        _emit_bibliography_warning(context, f"Bibliography entry for DOI '{key}' is empty.")
        return None
    if len(parsed.entries) > 1:
        _emit_bibliography_warning(
            context,
            f"Bibliography entry for DOI '{key}' contains multiple records; using the first.",
        )
    resolved_key, _entry_obj = next(iter(parsed.entries.items()))

    source = _inline_doi_source_path(context)
    collection.load_data(parsed, source=source)
    entry = collection.find(resolved_key)
    if entry is None:
        return None

    bibliography[resolved_key] = entry
    runtime_bibliography[resolved_key] = entry
    doi_map: dict[str, str] = context.runtime.setdefault("doi_citation_keys", {})
    doi_map[key] = resolved_key
    return entry


def _ensure_doi_entries(keys: list[str], context: RenderContextLike) -> None:
    """Materialise bibliography entries for any DOI keys not yet loaded."""
    doi_map: dict[str, str] = context.runtime.setdefault("doi_citation_keys", {})
    for key in list(keys):
        if key in context.state.bibliography:
            continue
        if not _is_doi_key(key):
            continue
        if key in doi_map:
            continue
        resolved = _materialise_doi_entry(key, context)
        if resolved is None:
            continue
        resolved_key = doi_map.get(key)
        if resolved_key:
            # replace original DOI key in-place for downstream handling
            try:
                index = keys.index(key)
                keys[index] = resolved_key
            except ValueError:
                continue
