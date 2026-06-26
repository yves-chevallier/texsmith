"""CLI emission of Typst (``.typ``) documents.

The ``--format typst`` path runs the shared ``HTML → IR → TypstWriter`` pipeline
and assembles a compilable ``.typ`` source. Two modes:

* **templated** (``--template`` / front-matter ``press.template``) — load the
  template's ``[typst.template]`` manifest section and render its
  ``template.typ`` scaffolding (title/authors/date/abstract/toc/numbering/
  bibliography) around the writer body. Mirrors the LaTeX template path but with
  a lean, Typst-native wrapper (no fragment/glossary/index-engine machinery).
* **standalone** (no template) — wrap the body in a minimal preamble.

Optional PDF compilation is delegated to :mod:`texsmith.writers.typst.build`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import contextlib
import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.conversion.debug import ensure_emitter
from texsmith.core.conversion.inputs import (
    InlineBibliographyValidationError,
    extract_front_matter_bibliography,
)
from texsmith.core.metadata import PressMetadataError, normalise_press_metadata
from texsmith.core.templates.typst import TypstTemplate, load_typst_template
from texsmith.ir import nodes as ir
from texsmith.readers.html import HtmlReader
from texsmith.writers.typst import TypstWriter, TypstWriterState, render_document
from texsmith.writers.typst.build import compile_typst
from texsmith.writers.typst.writer import _citation_label


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


def _min_heading_level(document: ir.Document) -> int | None:
    """Return the shallowest heading level in the body, or ``None`` if heading-free."""
    levels = [block.level for block in document.content if isinstance(block, ir.Header)]
    return min(levels) if levels else None


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
) -> tuple[BibliographyCollection, str | None]:
    """Build the bibliography collection (files + inline DOI) for ``document``.

    Returns the collection and the basename of the ``.bib`` written into
    ``output_dir`` (``None`` when there is nothing to cite or no output dir).
    """
    emitter = ensure_emitter(None)
    collection = BibliographyCollection()
    if bibliography_files:
        collection.load_files(list(bibliography_files))

    try:
        inline = extract_front_matter_bibliography(document.front_matter)
    except InlineBibliographyValidationError:
        inline = {}
    if inline and output_dir is not None:
        from texsmith.core.conversion.templates import _load_inline_bibliography

        _load_inline_bibliography(
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
    so the written ``.bib`` keys are sanitised the same way ``_citation_label``
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
        return f"@{kind}{{{_citation_label(key)},"

    return re.sub(r"@(\w+)\{([^,]+),", _sub, text)


def _extract_slots(
    document: ir.Document,
    declared_slots: Mapping[str, Any],
    default_slot: str,
    slot_titles: Mapping[str, str],
) -> tuple[ir.Document, dict[str, tuple[ir.Block, ...]]]:
    """Split the body into named slots by matching section headings to titles.

    Generalises abstract extraction to any declared, non-default slot that has a
    configured title (front-matter ``slots:`` mapping). Each matching section is
    pulled out of the body — heading stripped when the slot declares
    ``strip_heading`` — and the remaining blocks form the default (mainmatter)
    sink. Returns ``(mainmatter_document, {slot_name: blocks})``.
    """
    wanted: dict[str, tuple[str, Any]] = {}
    for name, slot in declared_slots.items():
        if name == default_slot:
            continue
        title = (slot_titles.get(name) or "").strip().casefold()
        if title:
            wanted[title] = (name, slot)
    if not wanted:
        return document, {}

    blocks = list(document.content)
    n = len(blocks)
    consumed = [False] * n
    extracted: dict[str, tuple[ir.Block, ...]] = {}
    index = 0
    while index < n:
        block = blocks[index]
        if isinstance(block, ir.Header):
            key = _header_text(block).strip().casefold()
            match = wanted.get(key)
            if match is not None and match[0] not in extracted:
                name, slot = match
                level = block.level
                end = index + 1
                while end < n and not (
                    isinstance(blocks[end], ir.Header) and blocks[end].level <= level
                ):
                    end += 1
                start = index + 1 if getattr(slot, "strip_heading", False) else index
                extracted[name] = tuple(blocks[start:end])
                for cursor in range(index, end):
                    consumed[cursor] = True
                index = end
                continue
        index += 1

    remaining = tuple(block for pos, block in enumerate(blocks) if not consumed[pos])
    return ir.Document(content=remaining), extracted


def _build_image_map(
    ir_document: ir.Document, source_dir: Path, output_dir: Path | None
) -> dict[str, str]:
    """Resolve + copy image assets, returning ``{original src: emitted path}``.

    Local files are copied next to the ``.typ`` (preserving the relative path);
    the emitted path points at the copy. Remote URLs and missing files map to an
    empty string so the writer drops the reference (keeping the document
    compilable without a fetch/toolchain dependency).
    """
    import shutil
    from urllib.parse import urlparse

    from texsmith.ir.visitor import walk

    mapping: dict[str, str] = {}
    for node in walk(ir_document):
        if not isinstance(node, ir.Image):
            continue
        src = node.src
        if src in mapping:
            continue
        scheme = urlparse(src).scheme
        if scheme in {"http", "https", "data"}:
            mapping[src] = ""
            continue
        candidate = (source_dir / src).resolve()
        if not candidate.is_file() or output_dir is None:
            mapping[src] = ""
            continue
        rel = src if not Path(src).is_absolute() else candidate.name
        destination = (output_dir / rel).resolve()
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, destination)
        except OSError:
            mapping[src] = ""
            continue
        mapping[src] = rel
    return mapping


def _promote_title(document: ir.Document) -> tuple[str, ir.Document]:
    """Lift a leading top-level heading out of the body to use as the title."""
    blocks = list(document.content)
    if not blocks or not isinstance(blocks[0], ir.Header):
        return "", document
    head = blocks[0]
    min_level = min(
        (b.level for b in blocks if isinstance(b, ir.Header)),
        default=head.level,
    )
    if head.level != min_level:
        return "", document
    return _header_text(head).strip(), ir.Document(content=tuple(blocks[1:]))


def _header_text(header: ir.Header) -> str:
    parts: list[str] = []
    for node in header.content:
        if isinstance(node, ir.Str):
            parts.append(node.text)
        elif isinstance(node, ir.Space):
            parts.append(" ")
    return "".join(parts)


def _slot_titles(document: Document) -> dict[str, str]:
    from texsmith.core.documents import extract_front_matter_slots

    titles = extract_front_matter_slots(_press_overrides(_front_matter(document)))[0]
    return {key: str(value) for key, value in titles.items() if isinstance(value, str)}


def _prepare_callouts(
    document: Document, template_options: Mapping[str, Any] | None
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Resolve mustaches and callout styling for the Typst path.

    ``prepare_documents`` (the shared input normalisation) does *not* run the
    mustache substitution / callout resolution that the LaTeX
    ``resolve_conversion_context`` performs — those happen during ``execute``,
    which the Typst path bypasses. This mirrors that step for Typst: it
    substitutes ``{{…}}`` placeholders in the document front matter and HTML
    (so e.g. ``{{callouts.style}}`` resolves) and returns the resolved callout
    style plus the merged definitions (built-in palette + custom callouts).
    """
    from texsmith.core.callouts import DEFAULT_CALLOUTS, merge_callouts, normalise_callouts
    from texsmith.core.conversion.debug import ensure_emitter
    from texsmith.core.conversion.templates import (
        _build_mustache_defaults,
        _replace_mustaches_in_html,
        _resolve_callout_style,
    )
    from texsmith.core.mustache import replace_mustaches_in_structure

    front_matter = _front_matter(document)
    overrides = _press_overrides(dict(front_matter))
    options = dict(template_options or {})

    callout_style = _resolve_callout_style(options, overrides, front_matter) or "fancy"
    mustache_defaults = _build_mustache_defaults(options, overrides, front_matter)
    contexts = (options, overrides, front_matter, mustache_defaults)

    resolved_fm = replace_mustaches_in_structure(dict(front_matter), contexts)
    document.set_front_matter(resolved_fm)
    document.set_html(
        _replace_mustaches_in_html(
            document.html,
            (options, overrides, resolved_fm, mustache_defaults),
            emitter=ensure_emitter(None),
            source=str(document.source_path),
        )
    )

    custom: Mapping[str, Any] | None = None
    for context in (overrides, resolved_fm):
        candidate = context.get("callouts") if isinstance(context, Mapping) else None
        if isinstance(candidate, Mapping):
            custom = candidate
            break
    callouts = normalise_callouts(merge_callouts(DEFAULT_CALLOUTS, custom))
    return callout_style, callouts


def render_typst_document(
    document: Document,
    *,
    template: str | None = None,
    bibliography_files: Sequence[Path] = (),
    output_dir: Path | None = None,
    diagrams_backend: str | None = None,
    template_options: Mapping[str, Any] | None = None,
) -> str:
    """Render one prepared document's HTML to a standalone ``.typ`` source.

    When ``template`` names a template that declares a ``[typst.template]``
    section, the body is wrapped in that scaffolding; otherwise a minimal
    standalone preamble is used.
    """
    from texsmith.writers.typst.diagrams import render_diagrams

    callout_style, callouts = _prepare_callouts(document, template_options)

    overrides = _press_overrides(_front_matter(document))
    title = _document_title(document, overrides)

    collection, bib_resource = _build_bibliography(document, bibliography_files, output_dir)
    bib_keys = frozenset(_citation_label(key) for key in collection.to_dict())

    ir_document = HtmlReader().read(document.html)
    source_dir = document.source_path.parent
    # Render Draw.io / Mermaid diagrams to PNGs Typst can embed, rewriting the
    # IR nodes; merge the produced assets over the generic image resolution map.
    ir_document, diagram_map = render_diagrams(
        ir_document, source_dir=source_dir, output_dir=output_dir, backend=diagrams_backend
    )
    image_map = _build_image_map(ir_document, source_dir, output_dir)
    image_map.update(diagram_map)

    if template is None:
        state = TypstWriterState(
            title=title,
            bibliography=bib_keys,
            callout_style=callout_style,
            callouts=callouts,
            runtime={"image_map": image_map},
        )
        body = TypstWriter(state).write(ir_document)
        return render_document(
            body,
            title=title,
            uses_mitex=bool(state.runtime.get("uses_mitex")),
            uses_eqnref=bool(state.runtime.get("uses_eqnref")),
        )

    typst_template = load_typst_template(template)
    return _render_templated(
        typst_template,
        document,
        ir_document,
        overrides,
        title,
        bib_keys,
        bib_resource,
        image_map,
        source_dir=source_dir,
        output_dir=output_dir,
        callout_style=callout_style,
        callouts=callouts,
    )


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


def _render_acronyms(abbreviations: Mapping[str, str]) -> str:
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


def _render_templated(
    typst_template: TypstTemplate,
    document: Document,
    ir_document: ir.Document,
    overrides: Mapping[str, Any],
    title: str,
    bib_keys: frozenset[str],
    bib_resource: str | None,
    image_map: dict[str, str],
    *,
    source_dir: Path,
    output_dir: Path | None = None,
    callout_style: str = "fancy",
    callouts: dict[str, dict[str, Any]] | None = None,
) -> str:
    context = typst_template.resolve_attributes(overrides)

    # Promote a leading top-level heading to the document title when front matter
    # declares none (mirrors the LaTeX title-promotion behaviour).
    if not title:
        title, ir_document = _promote_title(ir_document)

    slot_titles = _slot_titles(document)
    declared_slots, default_slot = typst_template.info.resolve_slots()
    mainmatter_doc, slot_blocks = _extract_slots(
        ir_document, declared_slots, default_slot, slot_titles
    )

    # Map the body's top-level headings onto Typst heading level 1, so numbering
    # starts at "1" (not "0.1") whatever the source depth — the title (h1) is
    # carried as document metadata, so content sections typically start at h2.
    # Mirrors the LaTeX path's ``1 - min(levels)`` offset; the scaffolding decides
    # whether level 1 renders as a section (article) or a chapter (book).
    min_level = _min_heading_level(mainmatter_doc)
    offset = (1 - min_level) if min_level is not None else 0

    state = TypstWriterState(
        title=title,
        heading_offset=offset,
        bibliography=bib_keys,
        callout_style=callout_style,
        callouts=callouts or {},
        runtime={"image_map": image_map},
    )
    writer = TypstWriter(state)
    mainmatter = writer.write(mainmatter_doc)
    rendered_slots = {name: writer.render_blocks(blocks) for name, blocks in slot_blocks.items()}

    author_names, author_blocks = _author_views(overrides)

    context = dict(context)
    context["title"] = title
    context["author_names"] = author_names
    context["author_blocks"] = author_blocks
    # Render the date in long, language-aware form ("November 16, 2025") via the
    # shared resolver, matching the LaTeX backend (the Typst attribute is raw).
    date_value = context.get("date")
    if date_value:
        from texsmith.core.document_date import format_date

        context["date"] = format_date(date_value, language=context.get("language"), cwd=source_dir)
    # Raw front matter, for data-driven templates (e.g. the recipe card) that
    # render structured front-matter fields rather than the document body.
    context["front_matter"] = _front_matter(document)
    # ``asset(path)`` copies a source-relative file next to the ``.typ`` and
    # returns its name, so a template can embed it (e.g. a letter signature SVG).
    context["asset"] = lambda value: _copy_template_asset(value, source_dir, output_dir)
    context["mainmatter"] = mainmatter
    context["abstract"] = rendered_slots.get("abstract", "")
    # Expose every declared non-default slot (e.g. a poster's quadrants) to the
    # scaffolding, defaulting to empty so the template can rely on the variable.
    for name in declared_slots:
        if name in (default_slot, "abstract"):
            continue
        context[name] = rendered_slots.get(name, "")
    if "paper" not in context:
        paper = overrides.get("paper")
        if isinstance(paper, str) and paper.strip():
            context["paper"] = paper.strip()
    context["acronyms"] = _render_acronyms(state.abbreviations)
    context["has_bibliography"] = bool(state.citations and bib_resource)
    context["bibliography_resource"] = bib_resource or ""
    context["uses_mitex"] = bool(state.runtime.get("uses_mitex"))
    context["uses_eqnref"] = bool(state.runtime.get("uses_eqnref"))

    return typst_template.render(context)


def build_typst_pdf(source: Path) -> tuple[bool, str]:
    """Compile ``source`` to PDF when a Typst compiler is available (graceful otherwise)."""
    result = compile_typst(source)
    return result.ok, result.message


__all__ = ["build_typst_pdf", "render_typst_document"]
