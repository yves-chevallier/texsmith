"""Typst (``.typ``) conversion pipeline.

The Typst analogue of the LaTeX engine in :mod:`texsmith.core.conversion.core`.
The CLI (``--format typst``) and any library caller drive it through
:func:`render_typst_document`, which runs the passes, one ``tmark.resolve`` and
one ``tmark.write(…, "typst")`` per body in
the shared IR pipeline, then assembles a compilable ``.typ``
source — templated (the template's ``[typst.template]`` scaffolding around the
bodies) or standalone (a minimal preamble). What lives here is the document
metadata and bibliography work that surrounds the write: the title and author
views, the label-safe ``.bib``, the acronym backmatter and the template assets.

Optional PDF compilation is delegated to :mod:`texsmith.writers.typst.build`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import contextlib
import copy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.bibliography.inline import (
    InlineBibliographyValidationError,
    extract_front_matter_bibliography,
)
from texsmith.core.bibliography.loading import load_inline_bibliography
from texsmith.core.context import DocumentState
from texsmith.core.conversion_contexts import ConversionContext, GenerationStrategy
from texsmith.core.exceptions import raise_conversion_error
from texsmith.core.metadata import PressMetadataError, normalise_press_metadata
from texsmith.core.mustache import replace_mustaches_in_structure
from texsmith.core.templates import resolve_template_language
from texsmith.core.templates.typst import TypstTemplate, load_typst_template
from texsmith.diagnostics import (
    DiagnosticEmitter,
    NullEmitter,
    ensure_emitter,
)
from texsmith.passes import PassContext, SlotTemplate, build_pipeline, run_pipeline
from texsmith.writers.typst import render_document
from texsmith.writers.typst.build import compile_typst
from texsmith.writers.typst.escaper import citation_label

from .bodies import Body, Requires
from .models import ConversionRequest
from .pipeline import (
    apply_pass_values,
    build_pass_context,
    processed_lang,
    write_slot_bodies,
)
from .resolution import (
    ResolutionChain,
    bibliography_paths,
    numbering_mode,
    resolve_pass,
    tmark_language,
)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


def _front_matter(document: Document) -> dict[str, Any]:
    front_matter = getattr(document, "front_matter", None)
    if isinstance(front_matter, Mapping):
        return copy.deepcopy(dict(front_matter))
    return {}


def _press_overrides(front_matter: Mapping[str, Any]) -> dict[str, Any]:
    """Normalise front matter into a flat overrides mapping (press hoisted)."""
    payload = dict(front_matter)
    with contextlib.suppress(PressMetadataError):
        normalise_press_metadata(payload)
    return payload


def _document_title(document: Document, overrides: Mapping[str, Any]) -> str:
    title = overrides.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    extracted = getattr(document, "extracted_title", None)
    if isinstance(extracted, str) and extracted.strip():
        return extracted.strip()
    return ""


def _author_views(overrides: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Return ``(author_names, author_blocks)`` from normalised press metadata."""
    authors = overrides.get("authors")
    names: list[str] = []
    blocks: list[str] = []
    if isinstance(authors, Sequence) and not isinstance(authors, (str, bytes)):
        for entry in authors:
            if isinstance(entry, Mapping):
                name = str(entry.get("name") or "").strip()
                affiliation = str(entry.get("affiliation") or "").strip()
            else:
                name = str(entry).strip()
                affiliation = ""
            if not name:
                continue
            names.append(name)
            # Author blocks are emitted into Typst *markup* (not a function
            # call), where ``[…]`` would render literally; so the name is plain
            # markup and only the affiliation footnote keeps its ``#`` call.
            if affiliation:
                blocks.append(
                    f"{_escape_typst_content(name)}#footnote[{_escape_typst_content(affiliation)}]"
                )
            else:
                blocks.append(_escape_typst_content(name))
    elif isinstance(authors, str) and authors.strip():
        names.append(authors.strip())
        blocks.append(_escape_typst_content(authors.strip()))
    return names, blocks


def _escape_typst_content(text: str) -> str:
    from texsmith.writers.typst.escaper import escape_typst_chars

    return escape_typst_chars(text)


def _build_bibliography(
    document: Document,
    bibliography_files: Sequence[Path],
    output_dir: Path | None,
    emitter: DiagnosticEmitter | None = None,
) -> tuple[BibliographyCollection, str | None]:
    """Build the bibliography collection (files + inline DOI) for ``document``.

    Returns the collection and the basename of the ``.bib`` written into
    ``output_dir`` (``None`` when there is nothing to cite or no output dir).

    ``emitter`` is the render's, not a fresh one: an invalid inline entry is
    an error on this path exactly as it is on the LaTeX path.
    """
    emitter = ensure_emitter(emitter)
    collection = BibliographyCollection()
    if bibliography_files:
        collection.load_files(list(bibliography_files))

    try:
        inline = extract_front_matter_bibliography(document.front_matter)
    except InlineBibliographyValidationError as exc:
        raise_conversion_error(emitter, str(exc), exc)
        inline = {}
    if inline and output_dir is not None:
        load_inline_bibliography(
            collection,
            inline,
            source_label=document.source_path.stem,
            output_dir=output_dir,
            emitter=emitter,
        )

    if not collection.to_dict():
        return collection, None
    if output_dir is None:
        return collection, None

    output_dir.mkdir(parents=True, exist_ok=True)
    resource = f"{document.source_path.stem}-refs.bib"
    _write_label_safe_bibtex(collection, output_dir / resource)
    return collection, resource


def _write_label_safe_bibtex(collection: BibliographyCollection, target: Path) -> None:
    """Write the collection to ``target`` with Typst-label-safe entry keys.

    Typst ``#cite(<label>)`` requires the bibliography key to be a valid label,
    so the written ``.bib`` keys are sanitised the same way ``citation_label``
    sanitises citation markers, keeping ``@key`` and ``<key>`` in agreement.
    """
    raw = _collection_to_bibtex(collection)
    target.write_text(_relabel_bibtex(raw), encoding="utf-8")


def _collection_to_bibtex(collection: BibliographyCollection) -> str:
    return collection.to_bibliography_data().to_string("bibtex")


def _relabel_bibtex(text: str) -> str:
    import re

    def _sub(match: re.Match[str]) -> str:
        kind, key = match.group(1), match.group(2)
        return f"@{kind}{{{citation_label(key)},"

    return re.sub(r"@(\w+)\{([^,]+),", _sub, text)


def _slot_titles(document: Document) -> dict[str, str]:
    from texsmith.core.documents import extract_front_matter_slots

    titles = extract_front_matter_slots(_press_overrides(_front_matter(document)))[0]
    return {key: str(value) for key, value in titles.items() if isinstance(value, str)}


def _copy_template_asset(value: Any, source_dir: Path, output_dir: Path | None) -> str:
    """Copy a source-relative file referenced by an attribute into ``output_dir``.

    Returns the emitted relative name (so a template can ``#image(...)`` it), or
    an empty string when ``value`` is not a usable local file. Powers the Jinja
    ``asset()`` helper used by data-driven templates (e.g. a letter signature).
    """
    import shutil

    if not isinstance(value, str) or not value.strip() or output_dir is None:
        return ""
    candidate = (source_dir / value.strip()).resolve()
    if not candidate.is_file():
        return ""
    rel = Path(value.strip()).name
    destination = (output_dir / rel).resolve()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, destination)
    except OSError:
        return ""
    return rel


def _acronym_backmatter(abbreviations: Mapping[str, str]) -> str:
    """Render the collected abbreviations as a Typst 'Acronyms' backmatter list.

    Mirrors the LaTeX glossary fragment's inline acronym section: an unnumbered
    'Acronyms' heading followed by a term list of ``short -> long``, sorted
    alphabetically. Empty when the document used no ``<abbr>`` definitions.
    """
    if not abbreviations:
        return ""
    from texsmith.writers.typst.escaper import escape_typst_chars

    lines = ["#heading(numbering: none)[Acronyms]", ""]
    for term in sorted(abbreviations, key=str.casefold):
        lines.append(f"/ {term}: {escape_typst_chars(abbreviations[term])}")
    return "\n".join(lines)


def build_typst_pdf(source: Path) -> tuple[bool, str]:
    """Compile ``source`` to PDF when a Typst compiler is available (graceful otherwise)."""
    result = compile_typst(source)
    return result.ok, result.message


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
    emitter: DiagnosticEmitter | None = None,
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
    collection, resource = _build_bibliography(document, bibliography_files, output_dir, emitter)
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


@dataclass(slots=True)
class _Rendered:
    """One document through the passes and the writers, before the wrapping."""

    document: Document
    processed: Document
    bodies: dict[str, Body]
    requires: Requires
    front_matter: dict[str, Any]
    overrides: dict[str, Any]
    template_overrides: dict[str, Any]
    default_slot: str
    declared_slots: dict[str, Any]
    #: The ``.bib`` files the passes wrote (fetched DOIs).
    pass_bibliography: list[Path]


def _callout_style(overrides: Mapping[str, Any]) -> str:
    """The ``callouts.style`` of the document, as the LaTeX fragment resolves it."""
    from texsmith.fragments.callouts import CalloutsFragment

    spec = CalloutsFragment.attributes["callout_style"]
    value, found = spec.fetch_override(overrides)
    if not found:
        return str(spec.default)
    resolved = spec.coerce_value(value, from_override=True)
    return str(resolved or spec.default)


def _typst_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _run_document(
    document: Document,
    request: ConversionRequest,
    *,
    typst_template: TypstTemplate | None,
    output_dir: Path | None,
    emitter: DiagnosticEmitter,
    chain: ResolutionChain,
    state: DocumentState,
) -> _Rendered:
    """Run the passes and the writers on one document."""
    if document.ir is None:
        raise ValueError("render_typst_document needs a document parsed into the IR")
    front_matter = _front_matter(document)
    overrides = _press_overrides(dict(front_matter))
    options = dict(request.template_options)

    declared_slots: dict[str, Any] = {}
    default_slot = "mainmatter"
    requests: dict[str, str] = {}
    strip: set[str] = set()
    if typst_template is not None:
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

    context = ConversionContext(
        document=document,
        request=request,
        output_dir=output_dir if output_dir is not None else document.source_path.parent,
        # The LaTeX path resolves the language in ``resolve_conversion_context``;
        # the Typst entry point gets the document straight from ``prepare_documents``.
        language=document.language or resolve_template_language(request.language, front_matter),
        generation=GenerationStrategy.from_request(request),
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
    ctx: PassContext = build_pass_context(context, emitter, template=slot_template, backend="typst")
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

    bodies, _slot_outputs, requires = write_slot_bodies(
        processed,
        backend="typst",
        language=language,
        mode=mode,
        loader=ctx.loader,
        sink=ctx.diagnostics,
    )
    processed.diagnostics.extend(
        record for record in ctx.diagnostics if record not in processed.diagnostics
    )
    apply_pass_values(ctx, state, context.template_overrides)
    return _Rendered(
        document=document,
        processed=processed,
        bodies=bodies,
        requires=requires,
        front_matter=front_matter,
        overrides=overrides,
        template_overrides=context.template_overrides,
        default_slot=default_slot,
        declared_slots=declared_slots,
        pass_bibliography=[Path(path) for path in ctx.bibliography],
    )


def render_typst_document(
    document: Document,
    request: ConversionRequest,
    *,
    output_dir: Path | None = None,
    emitter: DiagnosticEmitter | None = None,
    chain: ResolutionChain | None = None,
    state: DocumentState | None = None,
) -> str:
    """Render one tmark-read document to a ``.typ`` source (standalone or templated)."""
    return render_typst_documents(
        [document], request, output_dir=output_dir, emitter=emitter, chain=chain, state=state
    )


def render_typst_documents(
    documents: Sequence[Document],
    request: ConversionRequest,
    *,
    output_dir: Path | None = None,
    emitter: DiagnosticEmitter | None = None,
    chain: ResolutionChain | None = None,
    state: DocumentState | None = None,
) -> str:
    """Render the documents to one ``.typ`` source (standalone or templated).

    Several documents make one document, as the LaTeX ``main.tex`` does: the
    bodies of each slot follow each other in argument order, the requirements
    are the union, the front matter of the first document (which carries the
    shared configuration files) names the title and the template attributes.

    ``request`` is the one the caller assembled, not a reconstruction of it:
    the template, the bibliography, the diagram backend and the template
    options are read from it, and so are the flags the passes need — the asset
    strategy and ``include_paths``, which a rebuilt request silently reset to
    their defaults.

    ``state``, when given, receives what the passes computed (script usage,
    fallback summary, ``fonts_scanned``) through ``apply_pass_values``; the
    same values reach the template context (``fonts``, ``emoji``).
    """
    if not documents:
        raise ValueError("render_typst_documents needs at least one document")
    active_emitter = emitter or NullEmitter()
    template = request.template
    bibliography_files = list(request.bibliography_files)
    typst_template = load_typst_template(template) if template is not None else None
    if chain is None:
        chain = ResolutionChain(bibliography=bibliography_paths(bibliography_files))
    pass_state = state if state is not None else DocumentState()

    rendered = [
        _run_document(
            document,
            request,
            typst_template=typst_template,
            output_dir=output_dir,
            emitter=active_emitter,
            chain=chain,
            state=pass_state,
        )
        for document in documents
    ]
    first = rendered[0]
    requires = Requires.union(item.requires for item in rendered)
    default_slot = first.default_slot

    def slot_text(name: str) -> str:
        parts = [item.bodies.get(name, Body(text="")).text.strip() for item in rendered]
        return "\n\n".join(part for part in parts if part)

    title = _document_title(first.document, first.overrides)
    callout_style = _callout_style(first.template_overrides)
    has_index = bool(requires.index) or "ts-index" in requires.fragments
    # The contract definitions, then the document's choices among them.
    preamble = f"{typst_prelude()}\n\n#ts-callout-style.update({_typst_string(callout_style)})"
    mainmatter = f"{preamble}\n\n{slot_text(default_slot)}"

    if typst_template is None:
        return render_document(
            mainmatter,
            title=title,
            uses_mitex=_uses_mitex(requires),
            uses_eqnref=_uses_eqnref(requires),
            has_index=has_index,
        )

    if not title:
        # The ``title`` pass has already dropped the promoted heading from the
        # body, so the title has to come from the document's own promotion
        # decision — without it the template renders ``title: ""``, no title
        # block, and (in ``letter``) no salutation.
        title = first.document.promoted_title()

    resources: list[str] = []
    for item in rendered:
        _collection, resource = typst_bibliography(
            item.document, bibliography_files, item.pass_bibliography, output_dir, active_emitter
        )
        if resource and resource not in resources:
            resources.append(resource)

    source_dir = first.document.source_path.parent
    # The attributes are prose: a moustache in a subtitle names a value of the
    # front matter or of a ``-a`` option, resolved before the attribute is
    # rendered, as the LaTeX path does in ``resolve_conversion_context``.
    attribute_overrides = replace_mustaches_in_structure(
        first.template_overrides,
        (first.template_overrides, first.front_matter),
        emitter=active_emitter,
        source="template attributes",
    )
    template_context = dict(typst_template.resolve_attributes(attribute_overrides))
    for key in ("fonts", "emoji"):
        value = first.template_overrides.get(key)
        if value is not None:
            template_context.setdefault(key, value)
    author_names, author_blocks = _author_views(first.overrides)
    template_context["title"] = title
    template_context["author_names"] = author_names
    template_context["author_blocks"] = author_blocks
    # The language the context resolved (``--language`` or the front matter);
    # the scaffolding's ``lang:`` and the date filter read it.
    template_context.setdefault(
        "language",
        first.document.language or resolve_template_language(request.language, first.front_matter),
    )
    date_value = template_context.get("date")
    if date_value:
        from texsmith.core.document_date import format_date

        template_context["date"] = format_date(
            date_value, language=template_context.get("language"), cwd=source_dir
        )
    template_context["front_matter"] = first.front_matter
    template_context["asset"] = lambda value: _copy_template_asset(value, source_dir, output_dir)
    template_context["mainmatter"] = mainmatter
    template_context["abstract"] = slot_text("abstract")
    for name in first.declared_slots:
        if name in (default_slot, "abstract"):
            continue
        template_context[name] = slot_text(name)
    if "paper" not in template_context:
        paper = first.overrides.get("paper")
        if isinstance(paper, str) and paper.strip():
            template_context["paper"] = paper.strip()
    template_context["acronyms"] = _render_acronyms([item.processed for item in rendered], requires)
    template_context["callout_style"] = callout_style
    template_context["has_index"] = has_index
    template_context["has_bibliography"] = bool(requires.bibliography and resources)
    template_context["bibliography_resource"] = resources[0] if resources else ""
    # What ``#bibliography()`` takes: one path, or an array of them.
    template_context["bibliography_sources"] = (
        _typst_string(resources[0])
        if len(resources) == 1
        else "(" + ", ".join(_typst_string(item) for item in resources) + ",)"
    )
    template_context["uses_mitex"] = _uses_mitex(requires)
    template_context["uses_eqnref"] = _uses_eqnref(requires)
    return typst_template.render(template_context)


def _render_acronyms(documents: Sequence[Document], requires: Requires) -> str:
    """The acronym backmatter of the written keys, over every document's abbreviations."""
    from texsmith.core.fragments.activation import apply_requires

    abbreviations: dict[str, str] = {}
    for document in documents:
        assert document.ir is not None
        state = apply_requires(DocumentState(), requires, abbreviations=document.ir.abbreviations)
        abbreviations.update(state.abbreviations)
    return _acronym_backmatter(abbreviations)


__all__ = [
    "TYPST_PRELUDE",
    "build_typst_pdf",
    "render_typst_document",
    "render_typst_documents",
    "typst_bibliography",
    "typst_prelude",
]
