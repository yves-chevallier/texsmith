"""The tmark reader, the loader and the ``Document`` of the IR path."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

import pytest
from tmark.ir import model

from texsmith.core.documents import Document, SlotPlan, TitleStrategy
from texsmith.diagnostics import DiagnosticSink, FileTable, LoggingEmitter, NullEmitter
from texsmith.readers import loader as loader_module, tmark as tmark_reader
from texsmith.readers.loader import MemoryLoader, TexsmithLoader, join, join_dir


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


def test_wheel_schema_mismatch_raises_naming_both_hashes(monkeypatch) -> None:
    monkeypatch.setattr(tmark_reader, "_wheel_schema_checked", False)
    monkeypatch.setattr(
        tmark_reader.codec,
        "wheel_schema_mismatch",
        lambda: "tmark.ir.model was generated for tmark 0.1.0 (schema abc123), "
        "but the installed tmark 0.2.0 ships schema def456",
    )
    try:
        with pytest.raises(RuntimeError) as excinfo:
            tmark_reader.read("# hi", name="x.md")
        assert "abc123" in str(excinfo.value)
        assert "def456" in str(excinfo.value)
    finally:
        monkeypatch.setattr(tmark_reader, "_wheel_schema_checked", False)


def test_wheel_schema_match_checks_once_and_does_not_raise(monkeypatch) -> None:
    monkeypatch.setattr(tmark_reader, "_wheel_schema_checked", False)
    calls = 0

    def _no_mismatch() -> str | None:
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(tmark_reader.codec, "wheel_schema_mismatch", _no_mismatch)
    try:
        tmark_reader.read("# hi", name="x.md")
        tmark_reader.read("# hi again", name="x.md")
        assert calls == 1
    finally:
        monkeypatch.setattr(tmark_reader, "_wheel_schema_checked", False)


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


def test_join_returns_posix_text_even_from_a_windows_from_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``join``'s result crosses into tmark and appears in diagnostics and labels.

    On Windows, ``pathlib.Path`` is ``PureWindowsPath``, which renders with
    backslashes even when built from a forward-slash string — the bug behind
    the Windows-only failure this guards. Monkeypatching the module's
    ``PurePath`` to ``PureWindowsPath`` emulates that flavour on any OS.
    """
    monkeypatch.setattr(loader_module, "PurePath", PureWindowsPath)
    assert join("/docs/book/chapter.md", "figs/a.md") == "/docs/book/figs/a.md"
    assert join("/docs/book/chapter.md", "../other.md") == "/docs/other.md"
    assert join("/docs/book/chapter.md", "/abs/file.md") == "/abs/file.md"
    # A genuine Windows absolute path (drive letter, backslashes) as ``from_path``:
    # the directory is still found and the result still posix-style.
    windows_from = r"C:\Users\ycr\project\docs\chapter.md"
    assert join(windows_from, "figs/a.md") == "C:/Users/ycr/project/docs/figs/a.md"
    assert (
        join_dir(r"C:\Users\ycr\project\docs", "figs/a.md") == "C:/Users/ycr/project/docs/figs/a.md"
    )


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


def test_every_emitter_numbers_a_batch_the_same_way(tmp_path: Path) -> None:
    """The file a span names must not depend on which emitter the caller passed.

    ``span.file`` is part of ``Diagnostic.key``, the identity the sink
    deduplicates on. When only some emitters carried a file table, a batch run
    with a silent one numbered every document 0, so two findings in two files
    collided; run with a logging one they did not.
    """
    first = _write(tmp_path, "# First\n", "first.md")
    second = _write(tmp_path, "# Second\n", "second.md")

    numbering: dict[str, list[int]] = {}
    for name, emitter in (("logging", LoggingEmitter()), ("null", NullEmitter())):
        documents = [Document.from_markdown(path, emitter=emitter) for path in (first, second)]
        assert all(document.ir is not None for document in documents)
        assert all(document.files is emitter.sink.files for document in documents)
        numbering[name] = [document.ir.file for document in documents if document.ir]

    assert numbering["null"] == [0, 1]
    assert numbering["null"] == numbering["logging"]


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
