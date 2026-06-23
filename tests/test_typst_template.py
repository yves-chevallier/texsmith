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
    # The 'letter' template has no [typst.template] block.
    from texsmith.core.templates.loader import load_template

    root = load_template("letter").root
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
            "bibliography_resource": "",
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
            "bibliography_resource": "refs.bib",
            "uses_mitex": False,
            "bibliography_style": "ieee",
        }
    )
    out = template.render(context)
    assert '#bibliography("refs.bib", style: "ieee")' in out
