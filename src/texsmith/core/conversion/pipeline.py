"""The IR path of the conversion core: passes → ``tmark.resolve`` → ``tmark.write`` per slot.

Used by :func:`texsmith.core.conversion.core._render_document` when the
document was read with ``reader="tmark"`` (``specs/tmark-migration.md`` §2,
phase 3.5). The legacy HTML path is untouched: this module produces the same
``slot_outputs`` / :class:`DocumentState` pair it does, so bibliography
writing and :func:`wrap_template_document` run unchanged afterwards.

Diagnostics: every pass, ``resolve`` and ``write`` record emits into one
per-render :class:`DiagnosticSink` over the document's :class:`FileTable`
(deduplicated), which forwards each new record to the conversion emitter and
is appended to ``Document.diagnostics`` at the end.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.context import DocumentState
from texsmith.core.fragments.activation import apply_requires
from texsmith.diagnostics import Diagnostic, DiagnosticSink
from texsmith.fonts.fallback import merge_fallback_summaries
from texsmith.fonts.scripts import merge_script_usage
from texsmith.passes import IdAllocator, PassContext, SlotTemplate, build_pipeline, run_pipeline
from texsmith.readers.loader import TexsmithLoader

from ..diagnostics import DiagnosticEmitter
from .bodies import Body, Requires, build_writer_options, write_body
from .resolution import ResolutionChain, bibliography_paths, resolve_pass
from .templates import _build_mustache_defaults


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Mapping

    from texsmith.core.conversion_contexts import ConversionContext
    from texsmith.core.documents import Document
    from texsmith.core.templates import TemplateBinding


__all__ = [
    "IrRenderResult",
    "absorb_pass_bibliography",
    "apply_pass_values",
    "build_pass_context",
    "render_ir_document",
    "slot_template_of",
]


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
        raise ValueError("render_ir_document needs a document read with reader='tmark'")
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

    processed = run_pipeline(document, ctx, build_pipeline(), resolve=resolve_pass(chain))
    assert processed.ir is not None
    absorb_pass_bibliography(context, ctx.bibliography)

    language = processed.keys.lang or None
    slot_outputs: dict[str, str] = {}
    bodies: dict[str, Body] = {}
    requires = Requires()
    for slot_body in processed.bodies:
        options = build_writer_options(
            backend=backend,
            language=language,
            code_options=code_options,
            legacy_accents=request.legacy_latex_accents,
            base_level=slot_body.base_level,
            numbered=slot_body.numbered,
        )
        body = write_body(
            processed.ir,
            backend,
            options,
            blocks=slot_body.blocks,
            loader=ctx.loader,
            resolved=processed.resolved,
            sink=sink,
        )
        bodies[slot_body.name] = body
        slot_outputs[slot_body.name] = slot_outputs.get(slot_body.name, "") + body.text
        requires.merge(body.requires)

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
