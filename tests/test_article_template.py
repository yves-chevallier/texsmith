from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.core.conversion import ConversionRequest
from texsmith.core.conversion.execution import resolve_conversion_context
from texsmith.core.conversion.templates import bind_template
from texsmith.core.documents import Document
from texsmith.core.templates import load_template_runtime


def test_document_promotes_common_metadata(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text(
        "---\ntitle: Root Title\nsubtitle: Root Subtitle\nauthor: Ada Lovelace\n---\n# Heading\n",
        encoding="utf-8",
    )

    document = Document.from_markdown(source)
    context = document.prepare_for_conversion()

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

    document = Document.from_markdown(source).prepare_for_conversion()

    runtime = load_template_runtime("article")
    request = ConversionRequest(documents=[source], template="article")
    context = resolve_conversion_context(
        document,
        request,
        template_runtime=runtime,
        output_dir=tmp_path,
    )
    bind_template(
        context=context,
        template="article",
        emitter=None,
        legacy_latex_accents=False,
    )

    assert context.config is not None
    assert context.config.mermaid_config is not None
    assert Path(context.config.mermaid_config).is_file()


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


def test_article_template_omits_version_when_not_set() -> None:
    runtime = load_template_runtime("article")
    latex = runtime.instance.wrap_document(
        "Body",
        overrides={"press": {"title": "Handbook"}},
    )
    # The empty branch keeps a bare \date{...} without the version sub-line.
    assert "\\date{\\today}" in latex


def test_article_template_renders_explicit_version_string() -> None:
    runtime = load_template_runtime("article")
    latex = runtime.instance.wrap_document(
        "Body",
        overrides={
            "press": {"title": "Handbook"},
            "version": "Consolidation du draft de janvier 2026",
        },
    )
    assert "Consolidation du draft de janvier 2026" in latex


def test_article_template_escapes_special_chars_in_version() -> None:
    runtime = load_template_runtime("article")
    latex = runtime.instance.wrap_document(
        "Body",
        overrides={
            "press": {"title": "Handbook"},
            "version": "v1.0_alpha & co",
        },
    )
    assert "v1.0\\_alpha \\& co" in latex
    assert "v1.0_alpha" not in latex


def test_article_template_resolves_git_version(monkeypatch: pytest.MonkeyPatch) -> None:
    from texsmith.core import git_version

    git_version.reset_cache()
    monkeypatch.setattr(git_version, "git_describe", lambda **_: "v1.2.3-dirty")

    runtime = load_template_runtime("article")
    latex = runtime.instance.wrap_document(
        "Body",
        overrides={
            "press": {"title": "Handbook"},
            "version": "git",
        },
    )
    assert "v1.2.3-dirty" in latex
