"""CLI emission of Typst (``.typ``) documents.

This is the ``--format typst`` short-circuit: it bypasses the LaTeX-specific
template/fragment/engine machinery (none of which has a Typst counterpart yet)
and runs the shared ``HTML → IR → writer`` path with the Typst backend, wrapping
each document body into a standalone, compilable ``.typ`` source. Optional PDF
compilation is delegated to :mod:`texsmith.writers.typst.build` and is graceful
when the ``typst`` binary is absent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from texsmith.readers.html import HtmlReader
from texsmith.writers.typst import TypstWriter, TypstWriterState, render_document
from texsmith.writers.typst.build import compile_typst, typst_available


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping
    from pathlib import Path

    from texsmith.core.documents import Document


def _document_title(document: Document) -> str:
    front_matter: Mapping[str, Any] = getattr(document, "_front_matter", {}) or {}
    title = front_matter.get("title") if isinstance(front_matter, dict) else None
    if isinstance(title, str) and title.strip():
        return title.strip()
    extracted = getattr(document, "extracted_title", None)
    if isinstance(extracted, str) and extracted.strip():
        return extracted.strip()
    return ""


def render_typst_document(document: Document) -> str:
    """Render one prepared document's HTML to a standalone ``.typ`` source."""
    ir_document = HtmlReader().read(document.html)
    title = _document_title(document)
    body = TypstWriter(TypstWriterState(title=title)).write(ir_document)
    return render_document(body, title=title)


def build_typst_pdf(source: Path) -> tuple[bool, str]:
    """Compile ``source`` to PDF when ``typst`` is available (graceful otherwise)."""
    if not typst_available():
        return False, "typst binary not found on PATH; skipping PDF compilation."
    result = compile_typst(source)
    return result.ok, result.message


__all__ = ["build_typst_pdf", "render_typst_document"]
