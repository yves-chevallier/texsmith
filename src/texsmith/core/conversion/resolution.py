"""``tmark.resolve`` on the Python side (``python-ir-and-passes.md`` §7, task 3.4).

One ``resolve`` per document, on the full IR, after the ``pre`` passes: the
per-slot ``write`` calls then share the same ``Resolved`` (its ``handle``), so
numbering does not restart per slot (T1). :class:`ResolveOptions` carries
what tmark needs: the document path (includes and front-matter sources load
relative to it), the CLI ``.bib`` files made absolute against the cwd and
deduplicated in CLI order, and ``start`` — per counter prefix, the first free
value after the previous document of the batch. :class:`ResolutionChain`
threads that ``start`` through a batch (``ConversionService.execute`` in input
order, MkDocs in nav order), replacing the shared global ``CounterRegistry``
of the legacy path.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tmark

from texsmith.diagnostics import DiagnosticSink
from texsmith.ir import codec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document
    from texsmith.passes import PassContext


__all__ = [
    "ResolutionChain",
    "ResolveOptions",
    "bibliography_paths",
    "resolve_document",
    "resolve_pass",
]


def bibliography_paths(files: Iterable[Path | str]) -> tuple[Path, ...]:
    """CLI ``.bib`` files as absolute paths, first occurrence kept, CLI order."""
    seen: set[Path] = set()
    result: list[Path] = []
    for entry in files:
        path = Path(entry)
        if not path.is_absolute():
            path = Path.cwd() / path
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return tuple(result)


@dataclass(slots=True)
class ResolveOptions:
    """The ``options`` of ``tmark.resolve`` (and of ``write`` when it resolves itself)."""

    path: Path
    bibliography: tuple[Path, ...] = ()
    start: dict[str, int] = field(default_factory=dict)
    lang: str | None = None
    #: ``backend`` (the default) or ``all`` (design 06 §Site-wide resolution).
    numbering: str | None = None
    #: The labels of the other documents of the build (``BookLabel`` dicts:
    #: ``key``, ``prefix``, ``number``, ``kind``, ``title``, ``location``); a
    #: key defined in none of the document's registries resolves to a sibling.
    book: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"path": str(self.path)}
        if self.bibliography:
            payload["bibliography"] = [str(path) for path in self.bibliography]
        if self.start:
            payload["start"] = dict(self.start)
        if self.lang:
            payload["lang"] = self.lang
        if self.numbering:
            payload["numbering"] = self.numbering
        if self.book:
            payload["book"] = [dict(label) for label in self.book]
        return payload


@dataclass(slots=True)
class ResolutionChain:
    """The counter state carried from one document of a batch to the next."""

    bibliography: tuple[Path, ...] = ()
    start: dict[str, int] = field(default_factory=dict)
    lang: str | None = None
    #: Sibling labels handed to the next ``resolve`` (a MkDocs book sets them
    #: per page to the labels of the other pages of the book).
    book: list[dict[str, Any]] = field(default_factory=list)

    def options_for(self, document: Document) -> ResolveOptions:
        return ResolveOptions(
            path=document.source_path.resolve(),
            bibliography=self.bibliography,
            start=dict(self.start),
            lang=self.lang,
            book=[dict(label) for label in self.book],
        )

    def advance(self, resolved: Mapping[str, Any]) -> None:
        """Record where the next document's counters start."""
        next_start = resolved.get("next_start")
        if isinstance(next_start, Mapping):
            for prefix, value in next_start.items():
                if isinstance(value, int) and not isinstance(value, bool):
                    self.start[str(prefix)] = value


def document_payload(document: Document) -> dict[str, Any]:
    """The JSON of the document's IR as ``tmark.resolve`` / ``tmark.write`` expect it."""
    if document.ir is None:
        raise ValueError("the document carries no tmark IR (reader is not 'tmark')")
    payload = codec.encode_document(document.ir)
    payload["tmark"] = tmark.version()
    return payload


def resolve_document(
    document: Document,
    *,
    loader: Any,
    options: ResolveOptions,
    sink: DiagnosticSink | None = None,
) -> dict[str, Any]:
    """Run ``tmark.resolve`` on the document; its diagnostics go to ``sink`` (origin ``tmark``)."""
    resolved = tmark.resolve(document_payload(document), loader, options.to_json())
    if sink is not None:
        sink.extend_from_tmark(resolved.get("diagnostics") or ())
    return resolved


def resolve_pass(chain: ResolutionChain) -> Any:
    """The ``resolve`` step of :func:`texsmith.passes.run_pipeline`, bound to a chain."""

    def run(document: Document, ctx: PassContext) -> Document:
        """Resolve ``document``; the ``.bib`` files written by the passes join the CLI ones."""
        options = chain.options_for(document)
        if ctx.bibliography:
            # The ``.bib`` files the passes wrote (``doi``) follow the CLI ones.
            options.bibliography = bibliography_paths((*options.bibliography, *ctx.bibliography))
        resolved = resolve_document(
            document, loader=ctx.loader, options=options, sink=ctx.diagnostics
        )
        chain.advance(resolved)
        return document.evolve(resolved=resolved)

    return run
