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


def _scaffold_context(template: TypstTemplate, **overrides: object) -> dict[str, object]:
    context = template.resolve_attributes({"title": "T", **overrides})
    context.update(
        {
            "title": "T",
            "author_names": [],
            "author_blocks": [],
            "mainmatter": "= Section\n\n- un\n- deux",
            "abstract": "",
            "has_bibliography": False,
            "bibliography_sources": '""',
            "uses_mitex": False,
            "asset": lambda value: value,
        }
    )
    return context


@pytest.mark.parametrize("template", ["article", "book", "letter"])
def test_a_french_document_marks_its_list_items_with_an_en_dash(template: str) -> None:
    """``language: french`` (the babel name the LaTeX path shares) sets the list
    marker to the en dash babel-french prints; other languages keep the bullet."""
    scaffold = load_typst_template(template)
    french = scaffold.render(_scaffold_context(scaffold, language="french"))
    english = scaffold.render(_scaffold_context(scaffold, language="english"))
    marker = "#set list(marker: [\u2013])"  # the en dash
    assert 'lang: "fr"' in french
    assert marker in french
    assert french.index('lang: "fr"') < french.index(marker) < french.index("= Section")
    assert "#set list(marker:" not in english


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


def test_the_declared_typst_assets_are_copied_next_to_the_source(tmp_path) -> None:
    """``[typst.template.assets]`` lands in the output directory, as the LaTeX assets do."""
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
                'name = "assets"',
                'version = "0.0.1"',
                'entrypoint = "template.tex"',
                "",
                "[typst.template]",
                'name = "assets"',
                'version = "0.0.1"',
                'entrypoint = "template.typ"',
                "",
                "[typst.template.assets]",
                '"logo.svg" = { source = "logo.svg" }',
            ]
        ),
        encoding="utf-8",
    )
    (root / "template.tex").write_text("\\VAR{mainmatter}\n", encoding="utf-8")
    (root / "template.typ").write_text("{{ mainmatter }}\n", encoding="utf-8")
    (root / "logo.svg").write_text("<svg/>", encoding="utf-8")
    source = tmp_path / "doc.md"
    source.write_text("One\n", encoding="utf-8")

    document = Document.from_markdown(source).prepare_for_conversion()
    render_typst_document(
        document,
        ConversionRequest(documents=[Path(source)], template=str(root)),
        output_dir=tmp_path / "out",
    )

    assert (tmp_path / "out" / "logo.svg").read_text(encoding="utf-8") == "<svg/>"


@pytest.mark.parametrize(
    ("template", "slot_depth"),
    [("article", "section"), ("book", "chapter")],
)
def test_the_built_in_templates_declare_an_appendix_slot_for_typst(template, slot_depth) -> None:
    """The Typst half declares ``appendix`` as the LaTeX half does."""
    slots, default = load_typst_template(template).info.resolve_slots()
    assert default == "mainmatter"
    assert "appendix" in slots
    assert slots["appendix"].depth == slot_depth


def test_an_appendix_section_is_lettered_after_the_main_matter(tmp_path) -> None:
    """``press.slots.appendix`` moves the section after the body and restarts the
    heading counter in letters — what ``\\appendix`` does on the LaTeX path."""
    from pathlib import Path

    from texsmith.core.conversion import ConversionRequest
    from texsmith.core.conversion.typst import render_typst_document
    from texsmith.core.documents import Document

    source = tmp_path / "doc.md"
    source.write_text(
        "\n".join(
            [
                "---",
                "title: Report",
                "press:",
                "  template: article",
                "  slots:",
                "    appendix: Measurements",
                "---",
                "",
                "# Measurements",
                "",
                "Raw data.",
                "",
                "## Setup",
                "",
                "# Findings",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    document = Document.from_markdown(source).prepare_for_conversion()
    out = render_typst_document(
        document,
        ConversionRequest(documents=[Path(source)], template="article"),
        output_dir=tmp_path / "out",
    )

    findings = out.index("= Findings")
    reset = out.index("#counter(heading).update(0)")
    lettered = out.index('#set heading(numbering: "A.1")')
    appendix = out.index("= Measurements")
    assert findings < reset < lettered < appendix
    assert "== Setup" in out


def test_an_unnumbered_article_keeps_its_appendix_unnumbered(tmp_path) -> None:
    from pathlib import Path

    from texsmith.core.conversion import ConversionRequest
    from texsmith.core.conversion.typst import render_typst_document
    from texsmith.core.documents import Document

    source = tmp_path / "doc.md"
    source.write_text(
        "---\ntitle: T\npress:\n  template: article\n  numbering: false\n"
        "  slots:\n    appendix: Data\n---\n\n# Data\n\nRaw.\n\n# Body\n\nText.\n",
        encoding="utf-8",
    )
    document = Document.from_markdown(source).prepare_for_conversion()
    out = render_typst_document(
        document,
        ConversionRequest(documents=[Path(source)], template="article"),
        output_dir=tmp_path / "out",
    )
    assert "#counter(heading).update(0)" in out
    assert '#set heading(numbering: "A.1")' not in out
    assert out.index("= Body") < out.index("= Data")
