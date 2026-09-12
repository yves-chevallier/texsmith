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

Two more options come from the CLI (design 06 §Site-wide resolution):
``lang``, the document language TeXSmith resolved (``--language`` or the
front matter, a babel name such as ``french``) mapped to its BCP 47 primary
subtag by :func:`tmark_language`; and ``numbering``, ``--numbering
{backend,tmark}``: under ``tmark`` every predeclared series is numbered by
tmark (``ResolveOptions.numbering = "all"``) and the writers print those
numbers (``WriterOptions.numbering``), so ``.tex`` and ``.typ`` carry the
same figure and table numbers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tmark

from texsmith.core.templates.languages import _map_bcp47_language
from texsmith.diagnostics import DiagnosticSink
from texsmith.ir import codec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document
    from texsmith.passes import PassContext


__all__ = [
    "NUMBERING_MODES",
    "NUMBERING_OVERRIDE_KEY",
    "PREDECLARED_SERIES",
    "ResolutionChain",
    "ResolveOptions",
    "bibliography_paths",
    "numbering_mode",
    "resolve_document",
    "resolve_numbering",
    "resolve_pass",
    "tmark_language",
    "writer_numbering",
]

#: ``--numbering``: who allocates the numbers of the predeclared series.
NUMBERING_MODES: tuple[str, ...] = ("backend", "tmark")

#: The template-override key the CLI stores ``--numbering`` under (the same
#: private channel as ``_texsmith_latex_engine``), read by both IR backends.
NUMBERING_OVERRIDE_KEY = "_texsmith_numbering"

#: The predeclared series with a scope (design 06 §Numbering every series);
#: ``gls`` and ``doi`` number nothing.
PREDECLARED_SERIES: tuple[str, ...] = (
    "part",
    "chap",
    "sec",
    "app",
    "fig",
    "tbl",
    "lst",
    "eq",
    "thm",
    "note",
)


def tmark_language(language: str | None) -> str | None:
    """The BCP 47 primary subtag of a TeXSmith language name, for tmark's ``lang``.

    ``french`` → ``fr``, ``ngerman``/``german`` → ``de``, ``english`` → ``en``,
    ``italian`` → ``it``, … (the inverse of the babel alias table); a tag such
    as ``fr`` or ``fr-CH`` passes through as its primary subtag; an unknown
    name is ``None`` so tmark falls back to the front matter's ``lang``.
    """
    return _map_bcp47_language(language)


def numbering_mode(*sources: Mapping[str, Any] | None) -> str:
    """The ``--numbering`` mode carried by the first of ``sources`` naming one (``backend`` else).

    The sources are the template overrides of the conversion context and the
    request's ``template_options`` — the latter reaches the context only when
    a template is selected, so the fragment path reads it directly.
    """
    for overrides in sources:
        if not isinstance(overrides, Mapping):
            continue
        value = overrides.get(NUMBERING_OVERRIDE_KEY)
        if isinstance(value, str):
            candidate = value.strip().lower()
            if candidate in NUMBERING_MODES:
                return candidate
    return "backend"


def resolve_numbering(mode: str | None) -> str | None:
    """``ResolveOptions.numbering`` for a ``--numbering`` mode: ``all`` under ``tmark``."""
    return "all" if mode == "tmark" else None


def writer_numbering(mode: str | None) -> dict[str, str] | None:
    """``WriterOptions.numbering`` for a ``--numbering`` mode: every predeclared series."""
    if mode != "tmark":
        return None
    return dict.fromkeys(PREDECLARED_SERIES, "tmark")


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
        return payload


@dataclass(slots=True)
class ResolutionChain:
    """The counter state carried from one document of a batch to the next."""

    bibliography: tuple[Path, ...] = ()
    start: dict[str, int] = field(default_factory=dict)
    #: Batch defaults; :meth:`options_for` takes the per-document values.
    lang: str | None = None
    #: A ``--numbering`` mode (``backend`` | ``tmark``), not tmark's spelling.
    numbering: str | None = None

    def options_for(
        self,
        document: Document,
        *,
        lang: str | None = None,
        numbering: str | None = None,
    ) -> ResolveOptions:
        """The options of this document's ``resolve``; explicit values win over the chain's."""
        mode = numbering if numbering is not None else self.numbering
        return ResolveOptions(
            path=document.source_path.resolve(),
            bibliography=self.bibliography,
            start=dict(self.start),
            lang=lang if lang is not None else self.lang,
            numbering=resolve_numbering(mode),
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


def resolve_pass(
    chain: ResolutionChain,
    *,
    lang: str | None = None,
    numbering: str | None = None,
) -> Any:
    """The ``resolve`` step of :func:`texsmith.passes.run_pipeline`, bound to a chain.

    ``lang`` is the document's language as tmark wants it (:func:`tmark_language`)
    and ``numbering`` the ``--numbering`` mode; both default to the chain's.
    """

    def run(document: Document, ctx: PassContext) -> Document:
        """Resolve ``document``; the ``.bib`` files written by the passes join the CLI ones."""
        options = chain.options_for(document, lang=lang, numbering=numbering)
        if ctx.bibliography:
            # The ``.bib`` files the passes wrote (``doi``) follow the CLI ones.
            options.bibliography = bibliography_paths((*options.bibliography, *ctx.bibliography))
        resolved = resolve_document(
            document, loader=ctx.loader, options=options, sink=ctx.diagnostics
        )
        chain.advance(resolved)
        return document.evolve(resolved=resolved)

    return run
