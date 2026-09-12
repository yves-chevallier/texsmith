"""The tmark reader, the loader and the ``Document`` of the IR path."""

from __future__ import annotations

from pathlib import Path

from texsmith.core.conversion.inputs import InputKind
from texsmith.core.diagnostics import LoggingEmitter
from texsmith.core.documents import Document, SlotPlan, TitleStrategy
from texsmith.diagnostics import DiagnosticSink, FileTable
from texsmith.ir import model
from texsmith.ir.model import MISSING
from texsmith.readers import tmark as tmark_reader
from texsmith.readers.loader import MemoryLoader, TexsmithLoader, join


SOURCE = """---
title: Firmware notes
author: Ada Lovelace
counters:
  fw:
    name: Finding
---

# Scope

A finding #{fw:first} and a reference @fw:first.

## Detail

*[HTML]: HyperText Markup Language

Uses HTML.
"""


def _write(tmp_path: Path, text: str = SOURCE, name: str = "notes.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# readers.tmark
# ---------------------------------------------------------------------------


def test_read_returns_models_and_tmark_diagnostics() -> None:
    document, diagnostics = tmark_reader.read(SOURCE, file_id=3, name="notes.md")
    assert isinstance(document, model.Document)
    assert document.file == 3
    header = document.blocks[0]
    assert isinstance(header, model.Header)
    assert header.span.file == 3
    assert document.front_matter.keys.title == "Firmware notes"
    assert "fw" in document.front_matter.keys.press.declare.counters
    assert [a.key for a in document.abbreviations] == ["HTML"]
    # The deprecated ``counters`` root key and the ``#{...}`` spelling are reported.
    codes = {record.code for record in diagnostics}
    assert "deprecated-frontmatter-key" in codes
    assert all(record.origin == "tmark" for record in diagnostics)
    assert all(record.span.file == 3 for record in diagnostics)


def test_read_never_fails_on_odd_input() -> None:
    document, _diagnostics = tmark_reader.read("::: unclosed\n\n# only", name="x.md")
    assert isinstance(document, model.Document)


# ---------------------------------------------------------------------------
# readers.loader
# ---------------------------------------------------------------------------


def test_join_follows_tmark_rules() -> None:
    assert join("/docs/book/chapter.md", "figs/a.md") == "/docs/book/figs/a.md"
    assert join("/docs/book/chapter.md", "../other.md") == "/docs/other.md"
    assert join("/docs/book", "part.md") == "/docs/book/part.md"  # no extension: a directory
    assert join("/docs/book/chapter.md", "/abs/file.md") == "/abs/file.md"
    assert join("/docs/book/chapter.md", "./same.md") == "/docs/book/same.md"
    assert join("chapter.md", "../../up.md") == "../../up.md"


def test_texsmith_loader_registers_files_and_reports_unreadable(tmp_path: Path) -> None:
    files = FileTable()
    sink = DiagnosticSink(files)
    main = _write(tmp_path)
    files.add(main, SOURCE)
    (tmp_path / "part.md").write_text("# Part\n", encoding="utf-8")
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00bad")
    loader = TexsmithLoader(files, sink)

    assert loader.load(str(main), "part.md") == "# Part\n"
    assert loader.load(str(main), "missing.md") is None
    assert loader.load(str(main), "bad.md") is None
    assert files.path(1) == tmp_path / "part.md"
    assert loader.served == {str(tmp_path / "part.md"): 1}
    assert [record.code for record in sink] == ["file-unreadable"]
    # Serving the same file again does not register it twice.
    loader.load(str(main), "part.md")
    assert len(files) == 2


def test_memory_loader_joins_like_the_file_system() -> None:
    loader = MemoryLoader({"/docs/part.md": "# Part\n", "loose.md": "loose\n"})
    assert loader.load("/docs/main.md", "part.md") == "# Part\n"
    assert loader.load("/docs/main.md", "loose.md") == "loose\n"
    assert loader.load("/docs/main.md", "nope.md") is None
    assert loader.requests[0] == ("/docs/main.md", "part.md")


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


def test_from_markdown_with_the_tmark_reader(tmp_path: Path) -> None:
    path = _write(tmp_path)
    document = Document.from_markdown(path)

    assert document.reader == "tmark"
    assert document.kind is InputKind.MARKDOWN
    assert document.html == ""
    assert isinstance(document.ir, model.Document)
    assert document.files.path(0) == path
    assert document.files.text(0) == SOURCE
    assert document.keys.title == "Firmware notes"
    assert document.front_matter["title"] == "Firmware notes"
    assert document.front_matter["author"] == "Ada Lovelace"
    assert document.press["authors"][0]["name"] == "Ada Lovelace"
    assert any(record.code == "deprecated-frontmatter-key" for record in document.diagnostics)
    assert document.title_strategy is TitleStrategy.KEEP  # a title is declared
    assert isinstance(document.slots, SlotPlan)
    assert document.slots.selectors is document.slot_selectors


def test_parse_diagnostics_reach_the_emitter_with_their_file(tmp_path: Path) -> None:
    emitter = LoggingEmitter()
    path = _write(tmp_path)
    document = Document.from_markdown(path, emitter=emitter)
    assert document.files is emitter.files
    assert emitter.files.path(0) == path
    codes = [record.code for record in emitter.sink]
    assert "deprecated-frontmatter-key" in codes
    # A second document of the batch gets the next file id.
    second = Document.from_markdown(_write(tmp_path, "# Second\n", "second.md"), emitter=emitter)
    assert second.ir is not None
    assert second.ir.file == 1
    assert emitter.files.path(1) == tmp_path / "second.md"


def test_prepare_for_conversion_reads_headings_from_the_ir(tmp_path: Path) -> None:
    path = _write(tmp_path, "# Only Title\n\nBody.\n\n## Sub\n\nMore.\n")
    document = Document.from_markdown(path, promote_title=True)
    assert document.title_strategy is TitleStrategy.PROMOTE_METADATA
    assert document.first_heading_level() == 1
    prepared = document.prepare_for_conversion()
    assert prepared.extracted_title == "Only Title"
    assert prepared.drop_title is True
    assert prepared.slot_requests == {}


def test_title_promotion_needs_a_unique_level(tmp_path: Path) -> None:
    path = _write(tmp_path, "# One\n\n# Two\n")
    document = Document.from_markdown(path, promote_title=True)
    prepared = document.prepare_for_conversion()
    assert prepared.extracted_title is None
    assert prepared.drop_title is False


def test_front_matter_flags_and_slots(tmp_path: Path) -> None:
    text = "---\ntitle: T\nnumbered: false\nslots:\n  abstract: Summary\n---\n# Summary\n\nx\n"
    document = Document.from_markdown(_write(tmp_path, text))
    assert document.numbered is False
    assert document.slot_selectors == {"abstract": "Summary"}
    prepared = document.prepare_for_conversion()
    assert prepared.slot_requests == {"abstract": "Summary"}


def test_copy_shares_ir_and_files(tmp_path: Path) -> None:
    document = Document.from_markdown(_write(tmp_path))
    clone = document.copy()
    assert clone.ir is document.ir
    assert clone.files is document.files
    assert clone.diagnostics == document.diagnostics
    assert clone.diagnostics is not document.diagnostics
    assert clone.reader == "tmark"


def test_evolve_keeps_the_prepared_decision(tmp_path: Path) -> None:
    path = _write(tmp_path, "# Title\n\nBody.\n")
    document = Document.from_markdown(path, promote_title=True)
    prepared = document.prepare_for_conversion()
    assert prepared.ir is not None
    evolved = prepared.evolve(ir=model.Document(blocks=prepared.ir.blocks[1:]))
    assert evolved.drop_title is True
    assert evolved.extracted_title == "Title"
    assert evolved.files is prepared.files
    assert prepared.ir.blocks[0] is not None  # the input is untouched


def test_from_html_reads_the_fragment_into_the_ir(tmp_path: Path) -> None:
    path = tmp_path / "page.html"
    path.write_text("<article class='md-content__inner'><h1>Hi</h1><p>x</p></article>", "utf-8")
    document = Document.from_html(path)
    assert document.reader == "html"
    assert isinstance(document.ir, model.Document)
    assert document.files.path(document.ir.file) == path
    assert document.files.text(document.ir.file) == ""
    assert document.keys is not None and document.keys.title is MISSING
    assert "<h1>Hi</h1>" in document.html  # the extracted fragment, kept on the document
    assert [header.level for header in document.top_level_headers()] == [1]
