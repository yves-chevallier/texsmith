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

from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.context import DocumentState
from texsmith.core.conversion_contexts import ConversionContext, GenerationStrategy
from texsmith.core.diagnostics import DiagnosticEmitter, NullEmitter
from texsmith.core.templates import resolve_template_language
from texsmith.core.templates.typst import TypstTemplate, load_typst_template
from texsmith.passes import PassContext, SlotTemplate, build_pipeline, run_pipeline
from texsmith.writers.typst import render_document

from .bodies import Body, Requires, build_writer_options, write_body
from .models import ConversionRequest
from .pipeline import apply_pass_values, build_pass_context, processed_lang
from .resolution import (
    ResolutionChain,
    bibliography_paths,
    numbering_mode,
    resolve_pass,
    tmark_language,
    writer_numbering,
)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["TYPST_PRELUDE", "render_typst_from_ir", "typst_bibliography", "typst_prelude"]

_PRELUDE_PATH = Path(__file__).resolve().parents[2] / "templates" / "common" / "texsmith.typ"


@lru_cache(maxsize=1)
def typst_prelude() -> str:
    """The ``#ts-*`` contract definitions inlined ahead of every body."""
    return _PRELUDE_PATH.read_text(encoding="utf-8").strip()


TYPST_PRELUDE = _PRELUDE_PATH


def _uses_mitex(requires: Requires) -> bool:
    return any("mitex" in package for package in requires.packages)


def _uses_eqnref(requires: Requires) -> bool:
    """Whether a display equation carries a label the document references.

    The Typst writer names ``ts-equations`` when it emits an equation label or
    a ``#ref`` to one (``writers-and-passes.md`` §4); the scaffolding turns
    ``math.equation(numbering)`` on for it. The legacy path read the same
    thing from ``TypstWriterState.runtime["uses_eqnref"]``.
    """
    return "ts-equations" in requires.fragments


def typst_bibliography(
    document: Document,
    bibliography_files: Sequence[Path],
    pass_files: Sequence[Path],
    output_dir: Path | None,
) -> tuple[BibliographyCollection, str | None]:
    """The ``.bib`` the Typst scaffolding cites, with the passes' entries in it.

    The legacy ``_build_bibliography`` loads the CLI files and the front-matter
    inline entries; on the IR path the ``doi`` pass has already fetched every
    DOI (front-matter entries and ``@doi:`` citations, whose keys it rewrote
    to the fetched entries') into ``inline-doi-<stem>.bib`` — those files are
    ``pass_files`` and must reach the written bibliography the way
    ``absorb_pass_bibliography`` feeds the LaTeX path, or ``#cite(<key>)``
    names a key Typst does not know. Keys are label-safe, as before.
    """
    from .typst import _build_bibliography, _write_label_safe_bibtex

    collection, resource = _build_bibliography(document, bibliography_files, output_dir)
    files = [Path(path) for path in pass_files if Path(path).is_file()]
    if not files:
        return collection, resource
    collection.load_files(files)
    if output_dir is None or not collection.to_dict():
        return collection, resource
    output_dir.mkdir(parents=True, exist_ok=True)
    resource = resource or f"{document.source_path.stem}-refs.bib"
    _write_label_safe_bibtex(collection, output_dir / resource)
    return collection, resource


def render_typst_from_ir(
    document: Document,
    *,
    template: str | None = None,
    bibliography_files: Sequence[Path] = (),
    output_dir: Path | None = None,
    template_options: Mapping[str, Any] | None = None,
    emitter: DiagnosticEmitter | None = None,
    chain: ResolutionChain | None = None,
    state: DocumentState | None = None,
) -> str:
    """Render a tmark-read document to a ``.typ`` source (standalone or templated).

    ``state``, when given, receives what the passes computed (script usage,
    fallback summary, ``fonts_scanned``) through ``apply_pass_values``; the
    same values reach the template context (``fonts``, ``emoji``).
    """
    from .typst import (
        _author_views,
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
        # The LaTeX path resolves the language in ``resolve_conversion_context``;
        # the Typst entry point gets the document straight from ``prepare_documents``.
        language=document.language or resolve_template_language(None, front_matter),
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
    # Same inputs as the LaTeX path: the resolved language as tmark's BCP 47
    # ``lang`` and the ``--numbering`` mode from the template overrides.
    language = tmark_language(context.language) or processed_lang(document)
    mode = numbering_mode(context.template_overrides)
    processed = run_pipeline(
        document,
        ctx,
        build_pipeline(),
        resolve=resolve_pass(chain, lang=language, numbering=mode),
    )
    assert processed.ir is not None

    bodies: dict[str, Body] = {}
    requires = Requires()
    for slot_body in processed.bodies:
        writer_options = build_writer_options(
            backend="typst",
            language=language,
            base_level=slot_body.base_level,
            numbered=slot_body.numbered,
            numbering=writer_numbering(mode),
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
    pass_state = state if state is not None else DocumentState()
    apply_pass_values(ctx, pass_state, context.template_overrides)

    if not title and typst_template is not None:
        # The legacy Typst path promotes the leading top-level heading in
        # ``_render_templated``/``_promote_title``; on the IR path the ``title``
        # pass has already dropped that heading from the body, so the title has
        # to come from the document's own promotion decision — without it the
        # template renders ``title: ""``, no title block, and (in ``letter``) no
        # salutation. Standalone keeps the heading in the body, as legacy does.
        title = document.promoted_title()
    mainmatter = bodies.get(default_slot, Body(text="")).text
    prelude = typst_prelude()

    if typst_template is None:
        return render_document(
            f"{prelude}\n\n{mainmatter}",
            title=title,
            uses_mitex=_uses_mitex(requires),
            uses_eqnref=_uses_eqnref(requires),
        )

    _collection, bib_resource = typst_bibliography(
        document, bibliography_files, ctx.bibliography, output_dir
    )
    source_dir = document.source_path.parent
    template_context = dict(typst_template.resolve_attributes(overrides))
    for key in ("fonts", "emoji"):
        value = context.template_overrides.get(key)
        if value is not None:
            template_context.setdefault(key, value)
    author_names, author_blocks = _author_views(overrides)
    template_context["title"] = title
    template_context["author_names"] = author_names
    template_context["author_blocks"] = author_blocks
    # The language the context resolved (``--language`` or the front matter);
    # the scaffolding's ``lang:`` and the date filter read it. The legacy path
    # only ever saw the front-matter attribute, so this is a ``setdefault``.
    template_context.setdefault("language", context.language)
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
    template_context["uses_eqnref"] = _uses_eqnref(requires)
    return typst_template.render(template_context)


def _render_acronyms(document: Document, requires: Requires) -> str:
    """The acronym backmatter of the written keys (``typst._render_acronyms`` on the IR)."""
    from texsmith.core.context import DocumentState
    from texsmith.core.fragments.activation import apply_requires

    from .typst import _render_acronyms as render_legacy

    assert document.ir is not None
    state = apply_requires(DocumentState(), requires, abbreviations=document.ir.abbreviations)
    return render_legacy(state.abbreviations)
