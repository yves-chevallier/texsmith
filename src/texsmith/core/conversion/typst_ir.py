"""The Typst backend on the IR path (task 3.7, minimal for this wave).

``render_typst_document`` (``core/conversion/typst.py``) delegates here when
the document was read with ``reader="tmark"``: the same passes as the LaTeX
path, one ``tmark.resolve``, one ``tmark.write(…, "typst")`` per slot body,
and either the standalone preamble or the template's ``[typst.template]``
scaffolding around the bodies. The ``#ts-*`` contract functions the writer
calls come from :data:`TYPST_PRELUDE` (``templates/common/texsmith.typ``),
inlined ahead of the bodies until the Typst side of the fragments exists.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from texsmith.core.conversion_contexts import ConversionContext, GenerationStrategy
from texsmith.core.diagnostics import DiagnosticEmitter, NullEmitter
from texsmith.core.templates.typst import TypstTemplate, load_typst_template
from texsmith.passes import PassContext, SlotTemplate, build_pipeline, run_pipeline
from texsmith.writers.typst import render_document

from .bodies import Body, Requires, build_writer_options, write_body
from .models import ConversionRequest
from .pipeline import build_pass_context
from .resolution import ResolutionChain, bibliography_paths, resolve_pass


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["TYPST_PRELUDE", "render_typst_from_ir", "typst_prelude"]

_PRELUDE_PATH = Path(__file__).resolve().parents[2] / "templates" / "common" / "texsmith.typ"


@lru_cache(maxsize=1)
def typst_prelude() -> str:
    """The ``#ts-*`` contract definitions inlined ahead of every body."""
    return _PRELUDE_PATH.read_text(encoding="utf-8").strip()


TYPST_PRELUDE = _PRELUDE_PATH


def _uses_mitex(requires: Requires) -> bool:
    return any("mitex" in package for package in requires.packages)


def render_typst_from_ir(
    document: Document,
    *,
    template: str | None = None,
    bibliography_files: Sequence[Path] = (),
    output_dir: Path | None = None,
    template_options: Mapping[str, Any] | None = None,
    emitter: DiagnosticEmitter | None = None,
    chain: ResolutionChain | None = None,
) -> str:
    """Render a tmark-read document to a ``.typ`` source (standalone or templated)."""
    from .typst import (
        _author_views,
        _build_bibliography,
        _copy_template_asset,
        _document_title,
        _front_matter,
        _press_overrides,
        _slot_titles,
    )

    if document.ir is None:
        raise ValueError("render_typst_from_ir needs a document read with reader='tmark'")
    active_emitter = emitter or NullEmitter()
    front_matter = _front_matter(document)
    overrides = _press_overrides(dict(front_matter))
    options = dict(template_options or {})
    title = _document_title(document, overrides)

    typst_template: TypstTemplate | None = None
    declared_slots: dict[str, Any] = {}
    default_slot = "mainmatter"
    requests: dict[str, str] = {}
    strip: set[str] = set()
    if template is not None:
        typst_template = load_typst_template(template)
        declared_slots, default_slot = typst_template.info.resolve_slots()
        titles = _slot_titles(document)
        for name, slot in declared_slots.items():
            if name == default_slot:
                continue
            selector = titles.get(name)
            if selector:
                requests[name] = selector
            if getattr(slot, "strip_heading", False):
                strip.add(name)

    request = ConversionRequest(
        documents=[document.source_path],
        bibliography_files=list(bibliography_files),
        template=template,
    )
    context = ConversionContext(
        document=document,
        request=request,
        output_dir=output_dir if output_dir is not None else document.source_path.parent,
        language=document.language or "english",
        generation=GenerationStrategy(),
        template_overrides={**overrides, **options},
        slot_requests=requests,
    )
    slot_template = SlotTemplate(
        default_slot=default_slot,
        requests=requests,
        levels={},
        strip_heading=frozenset(strip),
        # Same convention as the LaTeX binding: a template's slots sit at the
        # section level (1); without one the CLI's ``--base-level`` default
        # (``section``) carried by ``document.base_level`` provides it. Either
        # way the body's shallowest heading becomes ``=`` (the legacy
        # ``1 - min_level`` offset) and the scaffolding decides the rest.
        base_level=1 if typst_template is not None else 0,
    )
    ctx: PassContext = build_pass_context(
        context, active_emitter, template=slot_template, backend="typst"
    )
    if chain is None:
        chain = ResolutionChain(bibliography=bibliography_paths(bibliography_files))
    processed = run_pipeline(document, ctx, build_pipeline(), resolve=resolve_pass(chain))
    assert processed.ir is not None

    bodies: dict[str, Body] = {}
    requires = Requires()
    language = processed.keys.lang or None
    for slot_body in processed.bodies:
        writer_options = build_writer_options(
            backend="typst",
            language=language,
            base_level=slot_body.base_level,
            numbered=slot_body.numbered,
        )
        body = write_body(
            processed.ir,
            "typst",
            writer_options,
            blocks=slot_body.blocks,
            loader=ctx.loader,
            resolved=processed.resolved,
            sink=ctx.diagnostics,
        )
        bodies[slot_body.name] = body
        requires.merge(body.requires)
    processed.diagnostics.extend(
        record for record in ctx.diagnostics if record not in processed.diagnostics
    )

    if not title and processed.extracted_title:
        title = processed.extracted_title
    mainmatter = bodies.get(default_slot, Body(text="")).text
    prelude = typst_prelude()

    if typst_template is None:
        return render_document(
            f"{prelude}\n\n{mainmatter}",
            title=title,
            uses_mitex=_uses_mitex(requires),
        )

    _collection, bib_resource = _build_bibliography(document, bibliography_files, output_dir)
    source_dir = document.source_path.parent
    template_context = dict(typst_template.resolve_attributes(overrides))
    author_names, author_blocks = _author_views(overrides)
    template_context["title"] = title
    template_context["author_names"] = author_names
    template_context["author_blocks"] = author_blocks
    date_value = template_context.get("date")
    if date_value:
        from texsmith.core.document_date import format_date

        template_context["date"] = format_date(
            date_value, language=template_context.get("language"), cwd=source_dir
        )
    template_context["front_matter"] = front_matter
    template_context["asset"] = lambda value: _copy_template_asset(value, source_dir, output_dir)
    template_context["mainmatter"] = f"{prelude}\n\n{mainmatter}"
    template_context["abstract"] = bodies.get("abstract", Body(text="")).text
    for name in declared_slots:
        if name in (default_slot, "abstract"):
            continue
        template_context[name] = bodies.get(name, Body(text="")).text
    if "paper" not in template_context:
        paper = overrides.get("paper")
        if isinstance(paper, str) and paper.strip():
            template_context["paper"] = paper.strip()
    template_context["acronyms"] = _render_acronyms(processed, requires)
    template_context["has_bibliography"] = bool(requires.bibliography and bib_resource)
    template_context["bibliography_resource"] = bib_resource or ""
    template_context["uses_mitex"] = _uses_mitex(requires)
    template_context["uses_eqnref"] = False
    return typst_template.render(template_context)


def _render_acronyms(document: Document, requires: Requires) -> str:
    """The acronym backmatter of the written keys (``typst._render_acronyms`` on the IR)."""
    from texsmith.core.context import DocumentState
    from texsmith.core.fragments.activation import apply_requires

    from .typst import _render_acronyms as render_legacy

    assert document.ir is not None
    state = apply_requires(DocumentState(), requires, abbreviations=document.ir.abbreviations)
    return render_legacy(state.abbreviations)
