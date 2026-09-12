"""Typst (``.typ``) conversion pipeline.

The Typst analogue of the LaTeX engine in :mod:`texsmith.core.conversion.core`.
The CLI (``--format typst``) and any library caller drive it through
:func:`render_typst_document`, which runs the passes, one ``tmark.resolve`` and
one ``tmark.write(…, "typst")`` per body in
:mod:`texsmith.core.conversion.typst_ir`, then assembles a compilable ``.typ``
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
from pathlib import Path
from typing import TYPE_CHECKING, Any

from texsmith.core.bibliography.collection import BibliographyCollection
from texsmith.core.conversion.debug import ensure_emitter
from texsmith.core.conversion.inputs import (
    InlineBibliographyValidationError,
    extract_front_matter_bibliography,
)
from texsmith.core.metadata import PressMetadataError, normalise_press_metadata
from texsmith.writers.typst.build import compile_typst
from texsmith.writers.typst.escaper import citation_label


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


def render_typst_document(
    document: Document,
    *,
    template: str | None = None,
    bibliography_files: Sequence[Path] = (),
    output_dir: Path | None = None,
    diagrams_backend: str | None = None,
    template_options: Mapping[str, Any] | None = None,
) -> str:
    """Render one prepared document's IR to a standalone ``.typ`` source.

    When ``template`` names a template that declares a ``[typst.template]``
    section, the bodies are wrapped in that scaffolding; otherwise a minimal
    standalone preamble is used. ``diagrams_backend`` is honoured by the
    ``assets`` pass, which converts the diagrams before the write.
    """
    from .typst_ir import render_typst_from_ir

    return render_typst_from_ir(
        document,
        template=template,
        bibliography_files=bibliography_files,
        output_dir=output_dir,
        diagrams_backend=diagrams_backend,
        template_options=template_options,
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


def build_typst_pdf(source: Path) -> tuple[bool, str]:
    """Compile ``source`` to PDF when a Typst compiler is available (graceful otherwise)."""
    result = compile_typst(source)
    return result.ok, result.message


__all__ = ["build_typst_pdf", "render_typst_document"]
