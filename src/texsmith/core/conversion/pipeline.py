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

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from texsmith.core.context import DocumentState
from texsmith.core.fragments.activation import apply_requires
from texsmith.diagnostics import Diagnostic, DiagnosticSink
from texsmith.passes import IdAllocator, PassContext, SlotTemplate, build_pipeline, run_pipeline
from texsmith.readers.loader import TexsmithLoader

from ..diagnostics import DiagnosticEmitter
from .bodies import Body, Requires, build_writer_options, write_body
from .resolution import ResolutionChain, bibliography_paths, resolve_pass
from .templates import _build_mustache_defaults


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

    from texsmith.core.conversion_contexts import ConversionContext
    from texsmith.core.documents import Document
    from texsmith.core.templates import TemplateBinding


__all__ = ["IrRenderResult", "build_pass_context", "render_ir_document", "slot_template_of"]


@dataclass(slots=True)
class IrRenderResult:
    """What the IR path hands back to the conversion core."""

    #: The document after the passes: ``ir`` rewritten, ``resolved`` and ``bodies`` set.
    document: Document
    slot_outputs: dict[str, str] = field(default_factory=dict)
    bodies: dict[str, Body] = field(default_factory=dict)
    requires: Requires = field(default_factory=Requires)
    document_state: DocumentState = field(default_factory=DocumentState)


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
) -> PassContext:
    """A ``PassContext`` over the conversion context (files, ids, loader, mustache contexts)."""
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
    ctx = build_pass_context(context, emitter, template=template, backend=backend, sink=sink)
    if chain is None:
        chain = ResolutionChain(bibliography=bibliography_paths(request.bibliography_files))

    processed = run_pipeline(document, ctx, build_pipeline(), resolve=resolve_pass(chain))
    assert processed.ir is not None

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
    apply_requires(
        state,
        requires,
        abbreviations=processed.ir.abbreviations,
        template_shell_escape=bool(binding.requires_shell_escape) if binding else False,
    )

    processed.diagnostics.extend(record for record in sink if record not in processed.diagnostics)
    return IrRenderResult(
        document=processed,
        slot_outputs=slot_outputs,
        bodies=bodies,
        requires=requires,
        document_state=state,
    )
