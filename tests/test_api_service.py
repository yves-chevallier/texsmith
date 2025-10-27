from __future__ import annotations

from pathlib import Path

from texsmith.api.service import (
    ConversionRequest,
    ConversionService,
    SlotAssignment,
)
from texsmith.core.conversion.inputs import UnsupportedInputError


def _create_template(tmp_path: Path) -> Path:
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
    return template_dir


def test_split_inputs_separates_sources(tmp_path: Path) -> None:
    service = ConversionService()
    doc_a = tmp_path / "chapter.md"
    doc_b = tmp_path / "appendix.html"
    bib = tmp_path / "refs.bib"
    for path in (doc_a, doc_b, bib):
        path.write_text("content", encoding="utf-8")

    documents, bibliography = service.split_inputs(
        [doc_a, bib, doc_b],
        extra_bibliography=[tmp_path / "extra.bib"],
    )

    assert documents == [doc_a, doc_b]
    assert bibliography[0] == bib
    assert len(bibliography) == 2


def test_prepare_documents_handles_markdown_and_html(tmp_path: Path) -> None:
    service = ConversionService()
    markdown = tmp_path / "chapter.md"
    markdown.write_text("# Title\nBody", encoding="utf-8")
    html = tmp_path / "chapter.html"
    html.write_text("<article class='md-content__inner'>Body</article>", encoding="utf-8")

    request = ConversionRequest(
        documents=[markdown, html],
        bibliography_files=[],
        selector="article.md-content__inner",
        markdown_extensions=[],
        heading_level=0,
        base_level=0,
        drop_title_first_document=True,
        numbered=True,
    )

    prepared = service.prepare_documents(request)

    assert len(prepared.documents) == 2
    assert prepared.documents[0].kind.name == "MARKDOWN"
    assert prepared.documents[0].options.drop_title is True
    assert prepared.documents[1].kind.name == "HTML"
    assert prepared.documents[1].options.drop_title is False


def test_prepare_documents_applies_slot_assignments(tmp_path: Path) -> None:
    service = ConversionService()
    source = tmp_path / "doc.md"
    source.write_text("# Heading\nContent", encoding="utf-8")

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        slot_assignments={
            source: [
                SlotAssignment(slot="sidebar", selector="#Heading", include_document=False),
                SlotAssignment(slot="main", selector=None, include_document=True),
            ]
        },
        markdown_extensions=[],
    )

    prepared = service.prepare_documents(request)
    document = prepared.document_map[source]
    assert document.slot_overrides["sidebar"] == "#Heading"
    assert "main" in document.slot_inclusions


def test_prepare_documents_rejects_unsupported_inputs(tmp_path: Path) -> None:
    service = ConversionService()
    unsupported = tmp_path / "config.yml"
    unsupported.write_text("site_name: demo", encoding="utf-8")

    request = ConversionRequest(
        documents=[unsupported],
        bibliography_files=[],
    )

    try:
        service.prepare_documents(request)
    except UnsupportedInputError as exc:
        assert "MkDocs configuration files are not supported" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Unsupported input should raise UnsupportedInputError")


def test_execute_without_template_returns_bundle(tmp_path: Path) -> None:
    service = ConversionService()
    source = tmp_path / "doc.md"
    source.write_text("# Title\nBody", encoding="utf-8")

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        markdown_extensions=[],
    )
    prepared = service.prepare_documents(request)

    response = service.execute(request, prepared=prepared)

    assert response.bundle is not None
    assert response.render_result is None
    assert response.bundle.fragments[0].stem == "doc"


def test_execute_with_template_returns_render_result(tmp_path: Path) -> None:
    service = ConversionService()
    source = tmp_path / "doc.md"
    source.write_text("# Title\nBody", encoding="utf-8")
    template_dir = _create_template(tmp_path)
    render_dir = tmp_path / "build"

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        markdown_extensions=[],
        template=str(template_dir),
        render_dir=render_dir,
    )
    prepared = service.prepare_documents(request)

    response = service.execute(request, prepared=prepared)
    render_result = response.render_result

    assert render_result is not None
    assert render_result.main_tex_path.exists()
