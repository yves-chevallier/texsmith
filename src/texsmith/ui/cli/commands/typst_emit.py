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
            if affiliation:
                blocks.append(
                    f"[{_escape_typst_content(name)}#footnote[{_escape_typst_content(affiliation)}]]"
                )
            else:
                blocks.append(f"[{_escape_typst_content(name)}]")
    elif isinstance(authors, str) and authors.strip():
        names.append(authors.strip())
        blocks.append(f"[{_escape_typst_content(authors.strip())}]")
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


def _split_abstract(
    document: ir.Document, slot_titles: Mapping[str, str]
) -> tuple[ir.Document, tuple[ir.Block, ...]]:
    """Pull the section matching the abstract slot title out of the body.

    Returns ``(mainmatter_document, abstract_blocks)``. When no abstract slot is
    declared or no matching section exists, the body is returned unchanged.
    """
    title = (slot_titles.get("abstract") or "").strip().casefold()
    if not title:
        return document, ()

    blocks = list(document.content)
    for index, block in enumerate(blocks):
        if not isinstance(block, ir.Header):
            continue
        if _header_text(block).strip().casefold() != title:
            continue
        level = block.level
        end = index + 1
        while end < len(blocks):
            nxt = blocks[end]
            if isinstance(nxt, ir.Header) and nxt.level <= level:
                break
            end += 1
        abstract = tuple(blocks[index + 1 : end])
        remaining = tuple(blocks[:index] + blocks[end:])
        return ir.Document(content=remaining), abstract
    return document, ()


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


def render_typst_document(
    document: Document,
    *,
    template: str | None = None,
    bibliography_files: Sequence[Path] = (),
    output_dir: Path | None = None,
) -> str:
    """Render one prepared document's HTML to a standalone ``.typ`` source.

    When ``template`` names a template that declares a ``[typst.template]``
    section, the body is wrapped in that scaffolding; otherwise a minimal
    standalone preamble is used.
    """
    overrides = _press_overrides(_front_matter(document))
    title = _document_title(document, overrides)

    collection, bib_resource = _build_bibliography(document, bibliography_files, output_dir)
    bib_keys = frozenset(_citation_label(key) for key in collection.to_dict())

    ir_document = HtmlReader().read(document.html)
    image_map = _build_image_map(ir_document, document.source_path.parent, output_dir)

    if template is None:
        state = TypstWriterState(
            title=title, bibliography=bib_keys, runtime={"image_map": image_map}
        )
        body = TypstWriter(state).write(ir_document)
        return render_document(body, title=title, uses_mitex=bool(state.runtime.get("uses_mitex")))

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
    )


def _render_templated(
    typst_template: TypstTemplate,
    document: Document,
    ir_document: ir.Document,
    overrides: Mapping[str, Any],
    title: str,
    bib_keys: frozenset[str],
    bib_resource: str | None,
    image_map: dict[str, str],
) -> str:
    context = typst_template.resolve_attributes(overrides)

    # Promote a leading top-level heading to the document title when front matter
    # declares none (mirrors the LaTeX title-promotion behaviour).
    if not title:
        title, ir_document = _promote_title(ir_document)

    slot_titles = _slot_titles(document)
    mainmatter_doc, abstract_blocks = _split_abstract(ir_document, slot_titles)

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
        runtime={"image_map": image_map},
    )
    writer = TypstWriter(state)
    mainmatter = writer.write(mainmatter_doc)
    abstract = writer.render_inline_blocks(abstract_blocks) if abstract_blocks else ""

    author_names, author_blocks = _author_views(overrides)

    context = dict(context)
    context["title"] = title
    context["author_names"] = author_names
    context["author_blocks"] = author_blocks
    context["mainmatter"] = mainmatter
    context["abstract"] = abstract
    if "paper" not in context:
        paper = overrides.get("paper")
        if isinstance(paper, str) and paper.strip():
            context["paper"] = paper.strip()
    context["has_bibliography"] = bool(state.citations and bib_resource)
    context["bibliography_resource"] = bib_resource or ""
    context["uses_mitex"] = bool(state.runtime.get("uses_mitex"))

    return typst_template.render(context)


def build_typst_pdf(source: Path) -> tuple[bool, str]:
    """Compile ``source`` to PDF when a Typst compiler is available (graceful otherwise)."""
    result = compile_typst(source)
    return result.ok, result.message


__all__ = ["build_typst_pdf", "render_typst_document"]
