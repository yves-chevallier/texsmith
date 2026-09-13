"""The ``doi`` pass: pending DOIs → bibliography entries before ``resolve``.

Two sources of pending DOIs (``writers-and-passes.md`` §3 row 5):

* citation items whose key is ``doi:<DOI>`` (tmark's ``@doi:10.…`` spelling,
  ``Resolution::Doi``) or a bare DOI (``10\\.\\d{4,9}/…``, the legacy
  ``writers/latex/doi.py`` rule);
* front-matter ``bibliography:`` entries that are a DOI or URL string, or a
  mapping with a ``doi`` field (``press.sources.bibliography`` in the IR).

Each DOI is fetched once through ``ctx.doi_fetcher`` (a
:class:`~texsmith.core.bibliography.doi.DoiBibliographyFetcher` by default,
whose user cache is honoured) after the output directory's
``texsmith-doi-cache.yaml`` (the legacy inline-bibliography cache, kept in
step). The entries are written to ``inline-doi-<stem>.bib`` in
``ctx.output_dir`` and the file is appended to ``ctx.bibliography``, which
``resolve_pass`` adds to ``ResolveOptions.bibliography`` and the pipeline
loads into the conversion's collection. A front-matter entry keeps its own
key (the author cites it); a citation item takes the fetched entry's key
(or the front-matter key declaring the same DOI) and the ``RefItem.key`` is
rewritten so that ``tmark.resolve`` finds it in the ``.bib``. A DOI that
cannot be fetched or parsed emits ``doi-fetch-failed`` at the item's key span
(the front matter's span for an entry) and the item stays as written, so the
writer prints ``[?key]``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import io
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from pybtex.database import BibliographyData, Entry
from pybtex.database.input import bibtex
from pybtex.exceptions import PybtexError

from texsmith.core.bibliography.loading import initialise_doi_cache, write_doi_cache
from texsmith.diagnostics import Span
from texsmith.ir import model
from texsmith.ir.walk import map_tree, walk
from texsmith.passes import PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["doi_of_key", "run"]

_DOI_SHAPE = re.compile(r"^10\.\d{4,9}/\S+$")


def doi_of_key(key: str) -> str | None:
    """The DOI a citation key names: ``doi:10.…`` (tmark) or a bare ``10.…/…`` (legacy)."""
    candidate = key.strip()
    if candidate.lower().startswith("doi:"):
        candidate = candidate[4:].strip()
        return candidate or None
    if _DOI_SHAPE.match(candidate):
        return candidate
    return None


def _first_entry(payload: str) -> tuple[str, Entry]:
    parsed = bibtex.Parser().parse_stream(io.StringIO(payload))
    entries = list(parsed.entries.items())
    if not entries:
        raise PybtexError("the BibTeX payload contains no entry")
    return entries[0]


@dataclass(slots=True)
class _Pending:
    """One DOI to fetch, where it was asked for, and the key its entry takes."""

    doi: str
    span: Span
    #: The front-matter key declaring it, ``None`` for a citation item.
    key: str | None = None
    #: The citation items (by their written key) waiting for it.
    items: list[str] = field(default_factory=list)


class _Resolver:
    """Fetch, cache and parse the pending DOIs of one document."""

    __slots__ = ("cache", "cache_path", "ctx", "dirty", "fetcher")

    def __init__(self, ctx: PassContext) -> None:
        self.ctx = ctx
        self.fetcher = ctx.doi_fetcher
        self.cache, self.cache_path = initialise_doi_cache(ctx.output_dir)
        self.dirty = False

    def _fetch(self, doi: str) -> str:
        from texsmith.core.bibliography.doi import DoiBibliographyFetcher, normalise_doi

        normalised = normalise_doi(doi)
        cached = self.cache.get(normalised)
        if cached is not None:
            return cached
        if self.fetcher is None:
            self.fetcher = DoiBibliographyFetcher()
            self.ctx.doi_fetcher = self.fetcher
        payload = str(self.fetcher.fetch(doi))
        self.cache[normalised] = payload
        self.dirty = True
        return payload

    def entry(self, pending: _Pending) -> tuple[str, Entry] | None:
        """The ``(key, entry)`` of a pending DOI, ``None`` (reported) when it cannot be had."""
        try:
            payload = self._fetch(pending.doi)
            key, entry = _first_entry(payload)
        except Exception as exc:
            self.ctx.diagnostics.emit(
                "doi-fetch-failed", pending.span, f"Failed to resolve DOI '{pending.doi}': {exc}"
            )
            return None
        return (pending.key or key, entry)

    def flush_cache(self) -> None:
        if self.dirty and self.cache_path is not None:
            write_doi_cache(self.cache_path, self.cache)


def _front_matter_dois(ir: model.Document) -> list[_Pending]:
    """The ``bibliography:`` entries of the front matter that name a DOI."""
    declared = ir.front_matter.keys.press.sources.bibliography
    if not isinstance(declared, Mapping):
        return []
    span = ir.front_matter.span
    pending: list[_Pending] = []
    for key, value in declared.items():
        doi: Any = None
        if isinstance(value, str):
            doi = value
        elif isinstance(value, Mapping) and "type" not in value:
            doi = value.get("doi")
        if isinstance(doi, str) and doi.strip():
            pending.append(_Pending(doi=doi.strip(), span=span, key=str(key)))
    return pending


def _pending_dois(ir: model.Document) -> list[_Pending]:
    """Front-matter entries first, then the citation items, one record per DOI."""
    from texsmith.core.bibliography.doi import DoiLookupError, normalise_doi

    pending = _front_matter_dois(ir)
    by_doi: dict[str, _Pending] = {}
    for record in pending:
        try:
            by_doi.setdefault(normalise_doi(record.doi), record)
        except DoiLookupError:
            continue
    for node in walk(ir):
        if not isinstance(node, model.Ref):
            continue
        for item in node.items:
            doi = doi_of_key(item.key)
            if doi is None:
                continue
            try:
                normalised = normalise_doi(doi)
            except DoiLookupError:
                continue
            record = by_doi.get(normalised)
            if record is None:
                record = _Pending(doi=doi, span=item.key_span)
                by_doi[normalised] = record
                pending.append(record)
            if item.key not in record.items:
                record.items.append(item.key)
    return pending


def _rewrite_keys(ir: model.Document, mapping: Mapping[str, str]) -> model.Document:
    if not mapping:
        return ir

    def rewrite(node: model.Node) -> model.Node:
        if not isinstance(node, model.Ref):
            return node
        items = tuple(
            replace(item, key=mapping[item.key]) if item.key in mapping else item
            for item in node.items
        )
        return node if items == node.items else replace(node, items=items)

    return map_tree(ir, rewrite)


def _bib_path(document: Document, ctx: PassContext) -> Path:
    target = Path(ctx.output_dir) / f"inline-doi-{document.source_path.stem}.bib"
    return target if target.is_absolute() else Path.cwd() / target


@spec("doi", stage="pre", after=("include",), needs_io=True)
def run(document: Document, ctx: PassContext) -> Document:
    ir = document.ir
    if ir is None:
        return document
    pending = _pending_dois(ir)
    if not pending:
        return document

    resolver = _Resolver(ctx)
    entries: dict[str, Entry] = {}
    key_map: dict[str, str] = {}
    for record in pending:
        resolved = resolver.entry(record)
        if resolved is None:
            continue
        key, entry = resolved
        entries.setdefault(key, entry)
        for written in record.items:
            if written != key:
                key_map[written] = key
    resolver.flush_cache()

    if entries:
        target = _bib_path(document, ctx)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(BibliographyData(entries=entries).to_string("bibtex"), "utf-8")
        except OSError as exc:
            ctx.diagnostics.emit(
                "doi-fetch-failed",
                ir.front_matter.span,
                f"Failed to write the DOI bibliography '{target}': {exc}",
            )
        else:
            if target not in ctx.bibliography:
                ctx.bibliography.append(target)

    rebuilt = _rewrite_keys(ir, key_map)
    if rebuilt is ir:
        return document
    return document.evolve(ir=rebuilt)
