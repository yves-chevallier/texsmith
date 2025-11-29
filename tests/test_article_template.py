from __future__ import annotations

from pathlib import Path

from texsmith.api.document import Document
from texsmith.core.conversion.templates import build_binder_context
from texsmith.core.conversion_contexts import GenerationStrategy
from texsmith.core.templates import load_template_runtime


def test_document_context_promotes_common_metadata(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text(
        "---\ntitle: Root Title\nsubtitle: Root Subtitle\nauthor: Ada Lovelace\n---\n# Heading\n",
        encoding="utf-8",
    )

    document = Document.from_markdown(source)
    context = document.to_context()

    press = context.front_matter["press"]
    assert press["title"] == "Root Title"
    assert press["subtitle"] == "Root Subtitle"
    assert press["authors"][0]["name"] == "Ada Lovelace"


def test_article_template_registers_mermaid_extra() -> None:
    runtime = load_template_runtime("article")
    config_path = Path(runtime.extras["mermaid_config"])
    assert config_path.is_file()


def test_article_template_sets_mermaid_config(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# Title\nbody", encoding="utf-8")

    document = Document.from_markdown(source)
    context = document.to_context()

    runtime = load_template_runtime("article")
    binder = build_binder_context(
        document_context=context,
        template="article",
        template_runtime=runtime,
        requested_language=None,
        bibliography_files=[],
        slot_overrides=None,
        output_dir=tmp_path,
        strategy=GenerationStrategy(),
        emitter=None,
        legacy_latex_accents=False,
    )

    assert binder.config.mermaid_config is not None
    assert Path(binder.config.mermaid_config).is_file()


def test_article_template_omits_author_when_not_set() -> None:
    runtime = load_template_runtime("article")
    template = runtime.instance
    context = template.prepare_context("Body")
    assert "author" not in context or not context["author"]


def test_article_template_skips_maketitle_without_title() -> None:
    runtime = load_template_runtime("article")
    latex = runtime.instance.wrap_document("Body")
    assert "\\maketitle" not in latex


def test_article_template_renders_maketitle_with_title_override() -> None:
    runtime = load_template_runtime("article")
    latex = runtime.instance.wrap_document(
        "Body",
        overrides={"press": {"title": "Handbook"}},
    )
    assert "\\maketitle" in latex
