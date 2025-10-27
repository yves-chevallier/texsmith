from __future__ import annotations

from pathlib import Path

from texsmith.api.service import (
    SlotAssignment,
    apply_slot_assignments,
    build_callbacks,
    build_render_settings,
    execute_conversion,
    prepare_documents,
    split_document_inputs,
)


def test_split_document_inputs_separates_sources(tmp_path: Path) -> None:
    doc_a = tmp_path / "chapter.md"
    doc_b = tmp_path / "appendix.html"
    bib = tmp_path / "refs.bib"
    for path in (doc_a, doc_b, bib):
        path.write_text("content", encoding="utf-8")

    documents, bibliography = split_document_inputs(
        [doc_a, bib, doc_b],
        extra_bibliography=[tmp_path / "extra.bib"],
    )

    assert documents == [doc_a, doc_b]
    assert bibliography[0] == bib
    assert len(bibliography) == 2


def test_prepare_documents_applies_drop_title_flags(tmp_path: Path) -> None:
    first = tmp_path / "one.md"
    second = tmp_path / "two.md"
    first.write_text("# Title\nBody", encoding="utf-8")
    second.write_text("# Another\nBody", encoding="utf-8")

    callbacks = build_callbacks(emit_warning=None, emit_error=None, debug_enabled=False)
    prepared = prepare_documents(
        [first, second],
        selector="article",
        full_document=False,
        heading_level=0,
        base_level=0,
        drop_title_all=False,
        drop_title_first_document=True,
        numbered=True,
        markdown_extensions=[],
        callbacks=callbacks,
    )

    assert prepared.documents[0].options.drop_title is True
    assert prepared.documents[1].options.drop_title is False


def test_apply_slot_assignments_updates_document_slots(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# Heading\nContent", encoding="utf-8")
    callbacks = build_callbacks(emit_warning=None, emit_error=None, debug_enabled=False)
    prepared = prepare_documents(
        [source],
        selector="article",
        full_document=False,
        heading_level=0,
        base_level=0,
        drop_title_all=False,
        drop_title_first_document=False,
        numbered=True,
        markdown_extensions=[],
        callbacks=callbacks,
    )

    apply_slot_assignments(
        prepared.document_map,
        {
            source: [
                SlotAssignment(slot="sidebar", selector="#Heading", include_document=False),
                SlotAssignment(slot="main", selector=None, include_document=True),
            ]
        },
    )

    document = prepared.document_map[source]
    assert document.slot_overrides["sidebar"] == "#Heading"
    assert "main" in document.slot_inclusions


def test_execute_conversion_without_template_returns_bundle(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# Title\nBody", encoding="utf-8")
    callbacks = build_callbacks(emit_warning=None, emit_error=None, debug_enabled=False)
    prepared = prepare_documents(
        [source],
        selector="article",
        full_document=False,
        heading_level=0,
        base_level=0,
        drop_title_all=False,
        drop_title_first_document=False,
        numbered=True,
        markdown_extensions=[],
        callbacks=callbacks,
    )
    settings = build_render_settings(
        parser=None,
        disable_fallback_converters=False,
        copy_assets=False,
        manifest=False,
        persist_debug_html=False,
        language=None,
        legacy_latex_accents=False,
    )

    outcome = execute_conversion(
        prepared.documents,
        settings=settings,
        callbacks=callbacks,
        bibliography_files=[],
        template=None,
        render_dir=None,
    )

    assert outcome.bundle is not None
    assert outcome.render_result is None
    assert outcome.bundle.fragments[0].stem == "doc"


def test_execute_conversion_with_template_returns_render_result(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# Title\nBody", encoding="utf-8")
    callbacks = build_callbacks(emit_warning=None, emit_error=None, debug_enabled=False)
    prepared = prepare_documents(
        [source],
        selector="article",
        full_document=False,
        heading_level=0,
        base_level=0,
        drop_title_all=False,
        drop_title_first_document=False,
        numbered=True,
        markdown_extensions=[],
        callbacks=callbacks,
    )
    settings = build_render_settings(
        parser=None,
        disable_fallback_converters=False,
        copy_assets=False,
        manifest=False,
        persist_debug_html=False,
        language=None,
        legacy_latex_accents=False,
    )

    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "manifest.toml").write_text(
        """
[compat]
texsmith = ">=0.1,<2.0"

[latex.template]
name = "demo"
version = "0.0.1"
entrypoint = "template.tex"
engine = "pdflatex"
shell_escape = false

[latex.template.slots.mainmatter]
default = true
depth = "section"
""".strip(),
        encoding="utf-8",
    )
    (template_dir / "template.tex").write_text(
        """
\\documentclass{article}
\\begin{document}
{{ mainmatter }}
\\end{document}
""".strip(),
        encoding="utf-8",
    )

    render_dir = tmp_path / "build"

    outcome = execute_conversion(
        prepared.documents,
        settings=settings,
        callbacks=callbacks,
        bibliography_files=[],
        template=str(template_dir),
        render_dir=render_dir,
    )

    render_result = outcome.render_result
    assert render_result is not None
    assert render_result.main_tex_path.exists()
