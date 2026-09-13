"""The IR path of the conversion core: passes → ``tmark.resolve`` → ``tmark.write`` per slot.

Used by :func:`texsmith.core.conversion.core._render_document` when the
document was parsed into the IR (``specs/tmark-migration.md`` §2,
phase 3.5). The legacy HTML path is untouched: this module produces the same
``slot_outputs`` / :class:`DocumentState` pair it does, so bibliography
writing and :func:`wrap_template_document` run unchanged afterwards.

Diagnostics: every pass, ``resolve`` and ``write`` record emits into one
per-render :class:`DiagnosticSink` over the document's :class:`FileTable`
(deduplicated), which forwards each new record to the conversion emitter and
is appended to ``Document.diagnostics`` at the end.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass, field, replace
import os
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any

from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.context import DocumentState
from texsmith.core.fragments.activation import apply_requires
from texsmith.diagnostics import Diagnostic, DiagnosticSink, Severity
from texsmith.fonts.fallback import merge_fallback_summaries
from texsmith.fonts.scripts import merge_script_usage
from texsmith.passes import IdAllocator, PassContext, SlotTemplate, build_pipeline, run_pipeline
from texsmith.readers.loader import TexsmithLoader

from ..diagnostics import DiagnosticEmitter
from .bodies import Body, Requires, build_writer_options, write_body
from .resolution import (
    ResolutionChain,
    bibliography_paths,
    numbering_mode,
    resolve_pass,
    tmark_language,
    writer_numbering,
)
from .templates import _build_mustache_defaults


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Mapping

    from texsmith.core.conversion_contexts import ConversionContext
    from texsmith.core.documents import Document
    from texsmith.core.templates import TemplateBinding

    from .models import ConversionRequest


__all__ = [
    "DEPRECATED_CODES",
    "DEPRECATED_LEVELS",
    "IrRenderResult",
    "absorb_pass_bibliography",
    "apply_pass_values",
    "build_pass_context",
    "demote_deprecated",
    "deprecated_level",
    "include_search_path",
    "processed_lang",
    "render_ir_document",
    "slot_template_of",
]

#: tmark's records for legacy spellings the ``tmark lint --fix`` rewrite removes.
DEPRECATED_CODES: frozenset[str] = frozenset({"deprecated", "deprecated-frontmatter-key"})

#: ``--deprecated`` / ``press.diagnostics.deprecated``: how those records are reported.
DEPRECATED_LEVELS: tuple[str, ...] = ("warning", "info", "off")


def deprecated_level(front_matter: Mapping[str, Any] | None, explicit: str | None = None) -> str:
    """The level the deprecation records are reported at (``warning`` by default).

    ``explicit`` is the CLI's ``--deprecated``; without it the front matter's
    ``press.diagnostics.deprecated`` decides. (``press.features`` is a boolean
    map in tmark, so the three-valued switch lives beside it.) An unknown
    value is the default.
    """
    for candidate in (explicit, _lookup_deprecated(front_matter)):
        if isinstance(candidate, str) and candidate.strip().lower() in DEPRECATED_LEVELS:
            return candidate.strip().lower()
    return "warning"


def _lookup_deprecated(front_matter: Mapping[str, Any] | None) -> str | None:
    if not isinstance(front_matter, Mapping):
        return None
    press = front_matter.get("press")
    section = press.get("diagnostics") if isinstance(press, Mapping) else None
    if section is None:
        section = front_matter.get("diagnostics")
    if not isinstance(section, Mapping):
        return None
    value = section.get("deprecated")
    if isinstance(value, bool):
        return "warning" if value else "off"
    return value if isinstance(value, str) else None


def demote_deprecated(record: Diagnostic, level: str) -> Diagnostic | None:
    """``record`` as ``level`` reports it: unchanged, lowered to ``info`` or dropped (``None``).

    Only the :data:`DEPRECATED_CODES` are touched; every other record passes
    as is, whatever the level. Applied before the ``--strict`` check, so the
    legacy spellings the examples still carry do not fail a strict run.
    """
    if record.code not in DEPRECATED_CODES or level == "warning":
        return record
    if level == "off":
        return None
    if record.severity <= Severity.INFO:
        return record
    return replace(record, severity=Severity.INFO)


@dataclass(slots=True)
class IrRenderResult:
    """What the IR path hands back to the conversion core."""

    #: The document after the passes: ``ir`` rewritten, ``resolved`` and ``bodies`` set.
    document: Document
    slot_outputs: dict[str, str] = field(default_factory=dict)
    bodies: dict[str, Body] = field(default_factory=dict)
    requires: Requires = field(default_factory=Requires)
    document_state: DocumentState = field(default_factory=DocumentState)
    #: The assets the ``assets``/``emoji`` passes copied next to the output (key → path).
    assets: dict[str, Path] = field(default_factory=dict)


def slot_template_of(
    binding: TemplateBinding | None, requests: Mapping[str, str] | None = None
) -> SlotTemplate:
    """The ``SlotTemplate`` of a template binding (defaults without one)."""
    if binding is None:
        return SlotTemplate(requests=dict(requests or {}))
    return SlotTemplate(
        default_slot=binding.default_slot,
        requests=dict(requests or {}),
        levels=binding.slot_levels(),
        strip_heading=frozenset(
            name for name, slot in binding.slots.items() if getattr(slot, "strip_heading", False)
        ),
        base_level=binding.base_level or 0,
    )


def processed_lang(document: Document) -> str | None:
    """The front matter's ``lang`` key as tmark parsed it (the writer's former source)."""
    keys = getattr(document, "keys", None)
    lang = getattr(keys, "lang", None)
    return lang if isinstance(lang, str) and lang.strip() else None


def _front_matter_include_paths(front_matter: Mapping[str, Any] | None) -> tuple[str, ...]:
    """The ``press.include_paths`` list of the front matter, a lone string accepted."""
    if not isinstance(front_matter, Mapping):
        return ()
    press = front_matter.get("press")
    value = press.get("include_paths") if isinstance(press, Mapping) else None
    if isinstance(value, str | PurePath):
        value = [value]
    if not isinstance(value, Sequence):
        return ()
    return tuple(
        str(item).strip()
        for item in value
        if isinstance(item, str | PurePath) and str(item).strip()
    )


def include_search_path(request: ConversionRequest | None, document: Document) -> tuple[Path, ...]:
    """The directories the ``include`` pass falls back to, most specific first.

    ``--include-path`` leads (``request.include_paths``), then the document's
    own ``press.include_paths``, written relative to it, then whatever the host
    supplied — the MkDocs companion hands over the ``base_path`` of the site's
    ``pymdownx.snippets``, which is what the deprecated ``--8<-- "path"``
    spelling was always resolved against. Entries are made absolute (against
    the current directory for the request's, against the document's directory
    for the front matter's), normalised textually like
    :func:`~texsmith.readers.loader.join` and listed once.
    """
    ordered: list[Path] = []

    def add(raw: str | Path, anchor: Path) -> None:
        path = Path(raw)
        absolute = path if path.is_absolute() else anchor / path
        entry = Path(os.path.normpath(absolute))
        if entry not in ordered:
            ordered.append(entry)

    cwd = Path.cwd()
    source = document.source_path
    base = Path(source).parent if source is not None else cwd
    for raw in request.include_paths if request is not None else ():
        add(raw, cwd)
    for raw in _front_matter_include_paths(document.front_matter):
        add(raw, base)
    for raw in request.default_include_paths if request is not None else ():
        add(raw, cwd)
    return tuple(ordered)


def _forwarding_sink(document: Document, emitter: DiagnosticEmitter) -> DiagnosticSink:
    def forward(record: Diagnostic, cause: BaseException | None) -> None:
        del cause
        emitter.diagnostic(record)

    return DiagnosticSink(document.files, on_emit=forward)


def build_pass_context(
    context: ConversionContext,
    emitter: DiagnosticEmitter,
    *,
    template: SlotTemplate,
    backend: str,
    sink: DiagnosticSink | None = None,
    code_options: Mapping[str, Any] | None = None,
) -> PassContext:
    """A ``PassContext`` over the conversion context (files, ids, loader, mustache contexts).

    ``code_options`` is the merged ``code`` section (``_resolve_code_options``)
    the ``highlight`` pass reads for the engine, the style and the inline rules.
    """
    document = context.document
    active_sink = sink if sink is not None else _forwarding_sink(document, emitter)
    ids = IdAllocator()
    if document.ir is not None:
        ids.observe(document.ir)
    contexts = (
        context.template_overrides,
        document.front_matter,
        _build_mustache_defaults(context.template_overrides, document.front_matter),
    )
    return PassContext(
        files=document.files,
        ids=ids,
        diagnostics=active_sink,
        loader=TexsmithLoader(document.files, active_sink),
        output_dir=context.output_dir,
        include_paths=include_search_path(context.request, document),
        request=context.request,
        contexts=contexts,
        emitter=emitter,
        template=template,
        backend=backend,
        code=dict(code_options or {}),
        copy_assets=context.generation.copy_assets,
        convert_assets=context.generation.convert_assets,
        hash_assets=context.generation.hash_assets,
    )


def absorb_pass_bibliography(context: ConversionContext, paths: Iterable[Path]) -> None:
    """Load the ``.bib`` files the passes wrote into the conversion's bibliography.

    ``core.py`` writes ``texsmith-bibliography.bib`` from the context's
    collection for the cited keys, so an entry the ``doi`` pass fetched must
    be in it or biber sees an undefined citation.
    """
    files = [Path(path) for path in paths]
    if not files:
        return
    collection = context.bibliography_collection
    if collection is None:
        collection = BibliographyCollection()
        context.bibliography_collection = collection
    collection.load_files(files)
    context.bibliography_map.update(collection.to_dict())


def apply_pass_values(
    ctx: PassContext,
    state: DocumentState,
    template_overrides: dict[str, Any] | None = None,
) -> None:
    """Hand what the passes computed (``ctx.values``) to the state and the template context.

    The ``scripts`` pass's ``script_usage``/``fallback_summary`` become the
    ``DocumentState`` fields the wrapper and the multi-document renderer read
    (``fonts_scanned`` tells the renderer its whole-body LaTeX scan is not
    needed), and the ``fonts.script_usage``/``fonts.fallback_summary`` keys
    of the template context that ``ts-fonts`` provisioning reads; the
    ``emoji`` pass's mode becomes the ``emoji`` override, as
    ``_build_runtime_common`` set it on the HTML path.
    """
    values = ctx.values
    usage = values.get("script_usage") or []
    fallback = values.get("fallback_summary") or []
    if usage:
        state.script_usage = merge_script_usage(state.script_usage, usage)
    if fallback:
        state.fallback_summary = merge_fallback_summaries(state.fallback_summary, fallback)
    state.fonts_scanned = True
    if template_overrides is None:
        return
    emoji_mode = values.get("emoji_mode")
    if isinstance(emoji_mode, str) and emoji_mode:
        template_overrides.setdefault("emoji", emoji_mode)
    if usage or fallback:
        fonts = template_overrides.setdefault("fonts", {})
        if isinstance(fonts, dict):
            if usage:
                existing = fonts.get("script_usage")
                fonts["script_usage"] = merge_script_usage(
                    existing if isinstance(existing, list) else [], usage
                )
            if fallback:
                existing = fonts.get("fallback_summary")
                fonts["fallback_summary"] = merge_fallback_summaries(
                    existing if isinstance(existing, list) else [], fallback
                )


def _declare_glossary(state: DocumentState, resolved: Mapping[str, Any] | None) -> None:
    """Declare the document's glossary terms so ``\\tsgls{key}`` has an entry.

    ``resolve`` returns the merged ``press.declare.glossary`` of the document
    and its includes; the writer emits ``\\tsgls{key}`` with the key as
    written, so the entry is declared under that exact key (no slugification)
    and an entry a previous document of the batch declared is left alone.

    tmark case-folds those keys (``tmark-registry``'s ``collect::glossary``,
    and ``@gls:`` resolves against the folded form), while ``\\tsacr`` keeps
    the acronym's own spelling: an acronym that is both declared and written
    would otherwise be declared twice — ``\\newacronym{NMR}`` beside
    ``\\newacronym{nmr}`` — and printed twice in the glossary. So a term a
    cased variant already declares is skipped.
    """
    terms = (resolved or {}).get("glossary")
    if not isinstance(terms, Mapping):
        return
    folded = {name.casefold() for name in state.acronyms}
    for key, description in terms.items():
        name = str(key).strip()
        text = str(description).strip()
        if not name or not text or name.casefold() in folded:
            continue
        folded.add(name.casefold())
        state.acronyms[name] = (name, text)
        state.abbreviations.setdefault(name, text)
        state.acronym_keys.setdefault(name, name)


def write_slot_bodies(
    processed: Document,
    *,
    backend: str,
    language: str | None,
    mode: str,
    loader: Any,
    sink: Any,
    code_options: Mapping[str, Any] | None = None,
    legacy_accents: bool = False,
) -> tuple[dict[str, Body], dict[str, str], Requires]:
    """One ``tmark.write`` per slot body, and the union of what they require.

    Both backends do exactly this after ``resolve``; the only thing that
    differs is what they ask the writer for. The bodies share one ``Resolved``
    (``processed.resolved``), so numbering does not restart per slot.
    """
    assert processed.ir is not None
    bodies: dict[str, Body] = {}
    slot_outputs: dict[str, str] = {}
    requires = Requires()
    for slot_body in processed.bodies:
        options = build_writer_options(
            backend=backend,
            language=language,
            code_options=code_options,
            legacy_accents=legacy_accents,
            base_level=slot_body.base_level,
            numbered=slot_body.numbered,
            numbering=writer_numbering(mode),
        )
        body = write_body(
            processed.ir,
            backend,
            options,
            blocks=slot_body.blocks,
            loader=loader,
            resolved=processed.resolved,
            sink=sink,
        )
        bodies[slot_body.name] = body
        slot_outputs[slot_body.name] = slot_outputs.get(slot_body.name, "") + body.text
        requires.merge(body.requires)
    return bodies, slot_outputs, requires


def render_ir_document(
    *,
    context: ConversionContext,
    binding: TemplateBinding | None,
    emitter: DiagnosticEmitter,
    backend: str = "latex",
    chain: ResolutionChain | None = None,
    initial_state: DocumentState | None = None,
    code_options: Mapping[str, Any] | None = None,
) -> IrRenderResult:
    """Run the passes, resolve once, write every slot body; union the ``Requires``."""
    document = context.document
    if document.ir is None:
        raise ValueError("render_ir_document needs a document parsed into the IR")
    request = context.request

    sink = _forwarding_sink(document, emitter)
    template = slot_template_of(binding, context.slot_requests)
    ctx = build_pass_context(
        context,
        emitter,
        template=template,
        backend=backend,
        sink=sink,
        code_options=code_options,
    )
    if chain is None:
        chain = ResolutionChain(bibliography=bibliography_paths(request.bibliography_files))

    # The resolved document language (``--language`` or the front matter, a
    # babel name) as tmark's BCP 47 ``lang``, for ``resolve`` and the writer
    # alike; the ``--numbering`` mode travels in the template overrides.
    language = tmark_language(context.language) or processed_lang(document)
    mode = numbering_mode(context.template_overrides, request.template_options)
    processed = run_pipeline(
        document,
        ctx,
        build_pipeline(),
        resolve=resolve_pass(chain, lang=language, numbering=mode),
    )
    assert processed.ir is not None
    absorb_pass_bibliography(context, ctx.bibliography)

    bodies, slot_outputs, requires = write_slot_bodies(
        processed,
        backend=backend,
        language=language,
        mode=mode,
        loader=ctx.loader,
        sink=sink,
        code_options=code_options,
        legacy_accents=request.legacy_latex_accents,
    )

    if initial_state is not None:
        state = copy.deepcopy(initial_state)
    else:
        state = DocumentState(bibliography=dict(context.bibliography_map))
    if ctx.pygments_styles:
        # ``\PY`` macros in the bodies: ``ts-code`` prints the style definitions.
        for key, definitions in ctx.pygments_styles.items():
            state.pygments_styles.setdefault(key, definitions)
        if "ts-code" not in requires.fragments:
            requires.fragments.append("ts-code")
    apply_requires(
        state,
        requires,
        abbreviations=processed.ir.abbreviations,
        template_shell_escape=bool(binding.requires_shell_escape) if binding else False,
    )
    _declare_glossary(state, processed.resolved)
    apply_pass_values(ctx, state, context.template_overrides)

    processed.diagnostics.extend(record for record in sink if record not in processed.diagnostics)
    assets = ctx.values.get("assets")
    return IrRenderResult(
        document=processed,
        slot_outputs=slot_outputs,
        bodies=bodies,
        requires=requires,
        document_state=state,
        assets={str(key): Path(path) for key, path in assets.items()}
        if isinstance(assets, Mapping)
        else {},
    )
