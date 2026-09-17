"""Tests for the Typst template path (manifest section + scaffolding wrapper)."""

from __future__ import annotations

import pytest

from texsmith.core.templates.manifest import TemplateError
from texsmith.core.templates.typst import TypstTemplate, load_typst_template


def test_article_declares_typst_section() -> None:
    template = load_typst_template("article")
    assert isinstance(template, TypstTemplate)
    assert template.info.name == "article"
    assert template.info.entrypoint == "template/template.typ"


def test_book_declares_typst_section() -> None:
    template = load_typst_template("book")
    assert template.info.name == "book"


def test_manifest_section_raises_for_missing_backend() -> None:
    template = load_typst_template("article")
    with pytest.raises(TemplateError, match="Unknown template backend"):
        template.manifest.section("html")


def test_template_without_typst_section_is_explicit() -> None:
    # The 'snippet' template has no [typst.template] block.
    from texsmith.core.templates.loader import load_template

    root = load_template("snippet").root
    with pytest.raises(TemplateError, match="does not declare a"):
        TypstTemplate(root)


def test_article_scaffolding_renders_title_and_body() -> None:
    template = load_typst_template("article")
    context = template.resolve_attributes({"title": "Hello"})
    context.update(
        {
            "title": "Hello",
            "author_names": ["Ada"],
            "author_blocks": ["[Ada]"],
            "mainmatter": "= Section\n\nbody",
            "abstract": "",
            "has_bibliography": False,
            "bibliography_sources": '""',
            "uses_mitex": False,
        }
    )
    out = template.render(context)
    assert "#set document(" in out
    assert "Hello" in out
    assert "= Section" in out
    assert "#bibliography(" not in out


def test_article_scaffolding_emits_bibliography_when_present() -> None:
    template = load_typst_template("article")
    context = template.resolve_attributes({})
    context.update(
        {
            "title": "T",
            "author_names": [],
            "author_blocks": [],
            "mainmatter": "body",
            "abstract": "",
            "has_bibliography": True,
            "bibliography_sources": '"refs.bib"',
            "uses_mitex": False,
            "bibliography_style": "ieee",
        }
    )
    out = template.render(context)
    assert '#bibliography("refs.bib", style: "ieee")' in out


def test_the_scaffolding_can_place_its_own_definitions_between_prelude_and_body(
    tmp_path,
) -> None:
    """``prelude`` and ``body`` are the two halves of ``mainmatter``.

    A ``#let ts-…`` redefinition only reaches the calls that follow it, so a
    template that restyles a contract function — ``texsmith.typ`` says it may —
    needs a seam between the definitions it overrides and the body that calls
    them.
    """
    from pathlib import Path

    from texsmith.core.conversion import ConversionRequest
    from texsmith.core.conversion.typst import render_typst_document
    from texsmith.core.documents import Document

    root = tmp_path / "tpl"
    root.mkdir()
    (root / "manifest.toml").write_text(
        "\n".join(
            [
                "[latex.template]",
                'name = "seam"',
                'version = "0.0.1"',
                'entrypoint = "template.tex"',
                "",
                "[typst.template]",
                'name = "seam"',
                'version = "0.0.1"',
                'entrypoint = "template.typ"',
            ]
        ),
        encoding="utf-8",
    )
    (root / "template.tex").write_text("\\VAR{mainmatter}\n", encoding="utf-8")
    (root / "template.typ").write_text(
        "{{ prelude }}\n\n#let ts-divider() = [BREAK]\n\n{{ body }}\n", encoding="utf-8"
    )
    source = tmp_path / "doc.md"
    source.write_text("One\n\n---\n\nTwo\n", encoding="utf-8")

    document = Document.from_markdown(source).prepare_for_conversion()
    out = render_typst_document(
        document,
        ConversionRequest(documents=[Path(source)], template=str(root)),
        output_dir=tmp_path / "out",
    )

    assert out.index("#let ts-divider() = [BREAK]") > out.index("#let ts-callout-style")
    assert out.index("#ts-divider()") > out.index("#let ts-divider() = [BREAK]")
