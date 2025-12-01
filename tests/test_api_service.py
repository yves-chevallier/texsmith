from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from texsmith.api.document import TitleStrategy
from texsmith.api.service import ConversionRequest, ConversionService, SlotAssignment
from texsmith.core.conversion.debug import ConversionError
from texsmith.core.conversion.inputs import UnsupportedInputError
from texsmith.core.conversion.templates import build_binder_context
from texsmith.core.conversion_contexts import GenerationStrategy
from texsmith.core.templates.runtime import load_template_runtime


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


def test_split_inputs_captures_front_matter(tmp_path: Path) -> None:
    service = ConversionService()
    doc = tmp_path / "chapter.md"
    doc.write_text("# Title\n", encoding="utf-8")
    metadata_file = tmp_path / "frontmatter.yml"
    metadata_file.write_text("press:\n  template: demo\n", encoding="utf-8")

    result = service.split_inputs([doc, metadata_file])

    assert result.documents == [doc]
    assert result.front_matter_path == metadata_file
    assert isinstance(result.front_matter, Mapping)
    assert result.front_matter.get("press", {}).get("template") == "demo"


def test_split_inputs_allows_yaml_only_input(tmp_path: Path) -> None:
    service = ConversionService()
    recipe = tmp_path / "recipe.yml"
    recipe.write_text("title: Cake\n", encoding="utf-8")

    result = service.split_inputs([recipe])

    assert result.documents == [recipe]
    assert result.front_matter is None
    assert result.front_matter_path is None


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
        base_level=0,
        strip_heading_first_document=True,
        promote_title=False,
        numbered=True,
    )

    prepared = service.prepare_documents(request)

    assert len(prepared.documents) == 2
    assert prepared.documents[0].kind.name == "MARKDOWN"
    assert prepared.documents[0].options.title_strategy is TitleStrategy.DROP
    assert prepared.documents[1].kind.name == "HTML"
    assert prepared.documents[1].options.title_strategy is TitleStrategy.KEEP


def test_document_context_records_title_from_heading(tmp_path: Path) -> None:
    service = ConversionService()
    template_dir = _create_template(tmp_path)
    source = tmp_path / "doc.md"
    source.write_text("# Sample Title\n\nBody text.", encoding="utf-8")

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        template=str(template_dir),
        promote_title=True,
    )

    prepared = service.prepare_documents(request)
    document = prepared.documents[0]
    context = document.to_context()

    assert context.title_from_heading is True
    assert context.extracted_title == "Sample Title"
    assert context.drop_title is True
    assert context.base_level == 0


def test_title_promotion_requires_unique_level(tmp_path: Path) -> None:
    service = ConversionService()
    template_dir = _create_template(tmp_path)
    source = tmp_path / "doc.md"
    source.write_text("## Title\n\n## Other", encoding="utf-8")

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        template=str(template_dir),
        promote_title=True,
    )

    prepared = service.prepare_documents(request)
    context = prepared.documents[0].to_context()

    assert context.title_from_heading is False
    assert context.extracted_title is None
    assert context.drop_title is False


def test_binder_context_injects_template_title(tmp_path: Path) -> None:
    service = ConversionService()
    template_dir = _create_template(tmp_path)
    source = tmp_path / "doc.md"
    source.write_text("# Sample Title\nContent", encoding="utf-8")

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        template=str(template_dir),
        promote_title=True,
    )

    prepared = service.prepare_documents(request)
    document = prepared.documents[0]
    context = document.to_context()

    runtime = load_template_runtime(str(template_dir))
    binder = build_binder_context(
        document_context=context,
        template=str(template_dir),
        template_runtime=runtime,
        requested_language=None,
        bibliography_files=[],
        slot_overrides=None,
        output_dir=tmp_path,
        strategy=GenerationStrategy(),
        emitter=None,
        legacy_latex_accents=False,
    )

    assert binder.template_overrides["press"]["title"] == "Sample Title"


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
    assert document.slots.selectors()["sidebar"] == "#Heading"
    assert "main" in document.slots.includes()


def test_document_slots_merge_front_matter_and_cli(tmp_path: Path) -> None:
    service = ConversionService()
    source = tmp_path / "doc.md"
    source.write_text(
        """---
press:
  slots:
    abstract: "*"
slots:
  backmatter: Appendix
---

# Introduction

Body text.
""",
        encoding="utf-8",
    )

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        slot_assignments={
            source: [
                SlotAssignment(
                    slot="frontmatter", selector="#Introduction", include_document=False
                ),
                SlotAssignment(slot="mainmatter", selector=None, include_document=True),
            ]
        },
        markdown_extensions=[],
    )

    prepared = service.prepare_documents(request)
    document = prepared.document_map[source]
    selectors = document.slots.selectors()
    inclusions = document.slots.includes()
    assert selectors["backmatter"] == "Appendix"
    assert selectors["frontmatter"] == "#Introduction"
    assert "abstract" in inclusions
    assert "mainmatter" in inclusions


class RecordingEmitter:
    debug_enabled = False

    def __init__(self) -> None:
        self.warnings: list[tuple[str, BaseException | None]] = []
        self.errors: list[tuple[str, BaseException | None]] = []
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, message: str, exc: BaseException | None = None) -> None:
        self.warnings.append((message, exc))

    def error(self, message: str, exc: BaseException | None = None) -> None:
        self.errors.append((message, exc))

    def event(self, name: str, payload: Mapping[str, object]) -> None:
        self.events.append((name, dict(payload)))


def test_conversion_service_uses_emitter(tmp_path: Path) -> None:
    service = ConversionService()
    template_dir = _create_template(tmp_path)
    source = tmp_path / "doc.md"
    source.write_text(
        """---
press:
  title: Sample
slots:
  missing: Section
---

# Introduction

Body text.
""",
        encoding="utf-8",
    )

    emitter = RecordingEmitter()
    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        markdown_extensions=[],
        template=str(template_dir),
        render_dir=tmp_path / "build",
        emitter=emitter,
    )

    prepared = service.prepare_documents(request)
    response = service.execute(request, prepared=prepared)

    assert response.is_template
    assert response.render_result.main_tex_path.exists()
    assert any("missing" in message for message, _ in emitter.warnings)
    assert any(name == "template_overrides" for name, _ in emitter.events)


def test_prepare_documents_rejects_multiple_press_sources(tmp_path: Path) -> None:
    service = ConversionService()
    doc_a = tmp_path / "a.md"
    doc_b = tmp_path / "b.md"
    doc_a.write_text("---\npress:\n  title: A\n---\n# A\n", encoding="utf-8")
    doc_b.write_text("---\npress:\n  title: B\n---\n# B\n", encoding="utf-8")

    request = ConversionRequest(documents=[doc_a, doc_b], bibliography_files=[])

    with pytest.raises(ConversionError):
        service.prepare_documents(request)


def test_prepare_documents_applies_shared_front_matter(tmp_path: Path) -> None:
    service = ConversionService()
    source = tmp_path / "doc.md"
    source.write_text("# Title\n\nBody", encoding="utf-8")

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        front_matter={"press": {"template": "demo"}, "author": "Ada"},
    )

    prepared = service.prepare_documents(request)
    front_matter = prepared.documents[0].front_matter
    assert front_matter.get("press", {}).get("template") == "demo"
    assert front_matter.get("author") == "Ada"


def test_shared_front_matter_preserves_heading_when_title_declared(tmp_path: Path) -> None:
    service = ConversionService()
    source = tmp_path / "doc.md"
    source.write_text("# Heading\n\nBody", encoding="utf-8")

    request = ConversionRequest(
        documents=[source],
        bibliography_files=[],
        front_matter={"press": {"title": "Declared"}},
    )

    prepared = service.prepare_documents(request)
    context = prepared.documents[0].to_context()

    assert context.drop_title is False
    assert context.title_from_heading is False


def test_prepare_documents_rejects_unsupported_mkdocs_inputs(tmp_path: Path) -> None:
    service = ConversionService()
    unsupported = tmp_path / "mkdocs.yml"
    unsupported.write_text("site_name: demo", encoding="utf-8")

    request = ConversionRequest(
        documents=[unsupported],
        bibliography_files=[],
    )

    with pytest.raises(UnsupportedInputError) as exc_info:
        service.prepare_documents(request)
    assert "MkDocs configuration files are not supported" in str(exc_info.value)


def test_prepare_documents_allows_generic_yaml(tmp_path: Path) -> None:
    service = ConversionService()
    yaml_doc = tmp_path / "recipe.yml"
    yaml_doc.write_text("---\ntitle: Demo\n---\nContent", encoding="utf-8")

    request = ConversionRequest(
        documents=[yaml_doc],
        bibliography_files=[],
    )

    prepared = service.prepare_documents(request)
    assert prepared.documents and prepared.documents[0].source_path == yaml_doc


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

    assert not response.is_template
    bundle = response.bundle
    assert bundle.fragments[0].stem == "doc"


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
    assert response.is_template
    render_result = response.render_result
    assert render_result.main_tex_path.exists()
