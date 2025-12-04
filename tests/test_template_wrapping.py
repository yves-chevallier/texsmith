from pathlib import Path

import pytest

from texsmith.core.context import DocumentState
from texsmith.core.fragments import register_fragment
from texsmith.core.templates import (
    TemplateError,
    WrappableTemplate,
    copy_template_assets,
    load_template,
)
from texsmith.core.templates.wrapper import _squash_blank_lines, wrap_template_document


@pytest.fixture
def project_root(monkeypatch: pytest.MonkeyPatch) -> Path:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def book_template(project_root: Path) -> WrappableTemplate:
    return load_template(str(project_root / "src" / "texsmith" / "templates" / "book"))


@pytest.fixture
def article_template(project_root: Path) -> WrappableTemplate:
    return load_template(str(project_root / "src" / "texsmith" / "templates" / "article"))


def test_squash_blank_lines_trims_trailing_whitespace() -> None:
    dirty = "First line   \nSecond\t \n\n  \n\n\nTail  "

    cleaned = _squash_blank_lines(dirty)

    assert cleaned == "First line\nSecond\n\nTail"


def test_iter_assets_declares_required_files(book_template: WrappableTemplate) -> None:
    assets = list(book_template.iter_assets())
    assert len(assets) == 1
    assert assets[0].destination.name == "fixtoc.sty"


def test_wrap_document_injects_mainmatter(book_template: WrappableTemplate) -> None:
    body = "\\section{Demo}"
    wrapped = book_template.wrap_document(body)

    assert "\\mainmatter" in wrapped
    assert body in wrapped


def test_manifest_defaults_are_applied(book_template: WrappableTemplate) -> None:
    wrapped = book_template.wrap_document("")
    assert "\\newcommand{\\booktitle}{A LaTeX Book Template}" in wrapped
    assert "\\tableofcontents" in wrapped
    assert "\\makeglossaries" not in wrapped
    assert "\\newacronym" not in wrapped
    assert "\\makeindex" not in wrapped
    assert "\\printindex" not in wrapped


def test_wrap_template_document_includes_index_when_flag_true(
    book_template: WrappableTemplate, tmp_path: Path
) -> None:
    state = DocumentState()
    state.has_index_entries = True
    state.index_entries.append(("Alpha",))
    result = wrap_template_document(
        template=book_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": ""},
        document_state=state,
        template_overrides=None,
        output_dir=tmp_path,
        copy_assets=False,
    )
    assert "\\usepackage{ts-index}" in result.latex_output
    assert "\\printindex" in result.latex_output
    assert "\\printindex" in result.template_context.get("fragment_backmatter", "")


def test_wrap_template_document_exposes_index_terms(
    article_template: WrappableTemplate, tmp_path: Path
) -> None:
    state = DocumentState()
    state.has_index_entries = True
    state.index_entries.append(("Alpha", "Beta"))
    result = wrap_template_document(
        template=article_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": ""},
        document_state=state,
        template_overrides=None,
        output_dir=tmp_path,
        copy_assets=False,
    )

    context = result.template_context
    assert context["has_index"] is True
    assert ("Alpha", "Beta") in context["index_terms"]


def test_wrap_document_includes_acronyms_when_present(
    book_template: WrappableTemplate, tmp_path: Path
) -> None:
    state = DocumentState()
    state.acronyms["HTTP"] = ("HTTP", "Hypertext Transfer Protocol")
    result = wrap_template_document(
        template=book_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": ""},
        document_state=state,
        template_overrides=None,
        output_dir=tmp_path,
        copy_assets=False,
    )

    latex_output = result.latex_output
    assert "\\usepackage{ts-glossary}" in latex_output
    assert "\\printglossary[type=\\acronymtype" in latex_output
    fragment = (tmp_path / "ts-glossary.sty").read_text(encoding="utf-8")
    assert "\\makeglossaries" in fragment
    assert "\\newacronym{HTTP}{HTTP}{Hypertext Transfer Protocol}" in fragment


def test_copy_template_assets_materialises_payload(
    book_template: WrappableTemplate, tmp_path: Path
) -> None:
    destination_root = tmp_path
    context = book_template.prepare_context("")
    copy_template_assets(book_template, destination_root, context=context)

    assert not (destination_root / "covers").exists()
    assert not (destination_root / ".latexmkrc").exists()
    assert not (destination_root / "titlepage.tex").exists()


def test_load_template_from_shortcut_path(book_template: WrappableTemplate) -> None:
    shortcut = load_template("./src/texsmith/templates/book")
    assert shortcut.info.name == book_template.info.name
    assert shortcut.info.entrypoint == book_template.info.entrypoint
    slug = load_template("book")
    assert slug.info.name == book_template.info.name


def test_documentclass_defaults(article_template: WrappableTemplate, tmp_path: Path) -> None:
    result = wrap_template_document(
        template=article_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": ""},
        document_state=DocumentState(),
        template_overrides=None,
        output_dir=tmp_path,
        copy_assets=False,
    )
    wrapped = result.latex_output
    assert r"\documentclass[a4paper,twoside]{article}" in wrapped
    assert "landscape]{article}" not in wrapped
    assert r"\usepackage[a4paper]{geometry}" in wrapped
    assert "\\makeindex" not in wrapped
    assert "\\printindex" not in wrapped
    assert "\\newacronym" not in wrapped


def test_documentclass_overrides(article_template: WrappableTemplate, tmp_path: Path) -> None:
    overrides = {
        "paper": "a3",
        "orientation": "landscape",
        "title": "Demo Article",
        "author": "Alice Example",
    }
    result = wrap_template_document(
        template=article_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": ""},
        document_state=DocumentState(),
        template_overrides=overrides,
        output_dir=tmp_path,
        copy_assets=False,
    )
    wrapped = result.latex_output
    assert r"\documentclass[a3paper,landscape,twoside]{article}" in wrapped
    assert r"\usepackage[a3paper,landscape]{geometry}" in wrapped
    assert r"\title{Demo Article}" in wrapped
    assert r"\author{Alice Example}" in wrapped


def test_article_injects_custom_preamble_block(
    article_template: WrappableTemplate,
) -> None:
    snippet = r"\usepackage{xcolor}"
    overrides = {"press": {"override": {"preamble": snippet}}}

    wrapped = article_template.wrap_document("", overrides=overrides)

    assert snippet in wrapped


def test_load_article_template_from_shortcut_path(
    article_template: WrappableTemplate,
) -> None:
    shortcut = load_template("./src/texsmith/templates/article")
    assert shortcut.info.name == article_template.info.name
    slug = load_template("article")
    assert slug.info.name == article_template.info.name


def test_rejects_invalid_paper_option(article_template: WrappableTemplate, tmp_path: Path) -> None:
    with pytest.raises(TemplateError):
        wrap_template_document(
            template=article_template,
            default_slot="mainmatter",
            slot_outputs={"mainmatter": ""},
            document_state=DocumentState(),
            template_overrides={"paper": "iso"},
            output_dir=tmp_path,
            copy_assets=False,
        )


def test_rejects_invalid_orientation_option(
    article_template: WrappableTemplate, tmp_path: Path
) -> None:
    with pytest.raises(TemplateError):
        wrap_template_document(
            template=article_template,
            default_slot="mainmatter",
            slot_outputs={"mainmatter": ""},
            document_state=DocumentState(),
            template_overrides={"orientation": "diagonal"},
            output_dir=tmp_path,
            copy_assets=False,
        )


def test_article_includes_acronyms_when_present(
    article_template: WrappableTemplate, tmp_path: Path
) -> None:
    state = DocumentState()
    state.acronyms["HTTP"] = ("HTTP", "Hypertext Transfer Protocol")
    result = wrap_template_document(
        template=article_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": ""},
        document_state=state,
        template_overrides=None,
        output_dir=tmp_path,
        copy_assets=False,
    )

    latex_output = result.latex_output
    assert "\\usepackage{ts-glossary}" in latex_output
    assert "\\printglossary[type=\\acronymtype" in latex_output
    fragment = (tmp_path / "ts-glossary.sty").read_text(encoding="utf-8")
    assert "\\makeglossaries" in fragment
    assert "\\newacronym{HTTP}{HTTP}{Hypertext Transfer Protocol}" in fragment


def test_fragment_targeting_slot_is_rejected(
    article_template: WrappableTemplate, tmp_path: Path
) -> None:
    frag_dir = tmp_path / "frag-slot"
    frag_dir.mkdir()
    (frag_dir / "inline.tex").write_text("Hello", encoding="utf-8")
    (frag_dir / "fragment.toml").write_text(
        "\n".join(
            [
                'name = "tmp-slot-frag"',
                "[[files]]",
                'path = "inline.tex"',
                'type = "inline"',
                'slot = "mainmatter"',
            ]
        ),
        encoding="utf-8",
    )
    register_fragment(frag_dir)

    with pytest.raises(TemplateError):
        wrap_template_document(
            template=article_template,
            default_slot="mainmatter",
            slot_outputs={"mainmatter": ""},
            document_state=DocumentState(),
            template_overrides=None,
            output_dir=tmp_path,
            copy_assets=False,
            fragments=["tmp-slot-frag"],
        )


def test_fragment_targeting_unknown_variable_is_rejected(
    article_template: WrappableTemplate, tmp_path: Path
) -> None:
    frag_dir = tmp_path / "frag-unknown"
    frag_dir.mkdir()
    (frag_dir / "inline.tex").write_text("Hello", encoding="utf-8")
    (frag_dir / "fragment.toml").write_text(
        "\n".join(
            [
                'name = "tmp-unknown-frag"',
                "[[files]]",
                'path = "inline.tex"',
                'type = "inline"',
                'slot = "unknown_variable"',
            ]
        ),
        encoding="utf-8",
    )
    register_fragment(frag_dir)

    with pytest.raises(TemplateError):
        wrap_template_document(
            template=article_template,
            default_slot="mainmatter",
            slot_outputs={"mainmatter": ""},
            document_state=DocumentState(),
            template_overrides=None,
            output_dir=tmp_path,
            copy_assets=False,
            fragments=["tmp-unknown-frag"],
        )


def test_ts_index_fragment_uses_texindy(
    article_template: WrappableTemplate,
    tmp_path: Path,
) -> None:
    state = DocumentState()
    state.has_index_entries = True
    state.index_entries.append(("Alpha",))
    result = wrap_template_document(
        template=article_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": ""},
        document_state=state,
        template_overrides={"index_engine": "texindy"},
        output_dir=tmp_path,
        copy_assets=False,
    )

    assert "\\printindex" in result.latex_output
    assert "\\usepackage{ts-index}" in result.latex_output
    ts_index = (tmp_path / "ts-index.sty").read_text(encoding="utf-8")
    assert "\\RequirePackage[xindy]{imakeidx}" in ts_index
    assert "\\makeindex" in ts_index


def test_ts_index_fragment_falls_back_to_makeindex(
    article_template: WrappableTemplate,
    tmp_path: Path,
) -> None:
    state = DocumentState()
    state.has_index_entries = True
    state.index_entries.append(("Beta",))
    result = wrap_template_document(
        template=article_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": ""},
        document_state=state,
        template_overrides={"index_engine": "makeindex"},
        output_dir=tmp_path,
        copy_assets=False,
    )

    assert "\\printindex" in result.latex_output
    ts_index = (tmp_path / "ts-index.sty").read_text(encoding="utf-8")
    assert "\\RequirePackage[xindy]{imakeidx}" not in ts_index
    assert "\\RequirePackage{imakeidx}" in ts_index
    assert "\\makeindex" in ts_index


def test_article_prefers_lualatex_for_latin_text(
    article_template: WrappableTemplate,
    tmp_path: Path,
) -> None:
    body = "Résumé avec des caractères comme œ et l'euro €."
    state = DocumentState()
    result = wrap_template_document(
        template=article_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": body},
        document_state=state,
        template_overrides=None,
        output_dir=tmp_path,
        copy_assets=False,
    )

    context = result.template_context
    assert context["latex_engine"] == "lualatex"
    assert "€" in context["unicode_chars"]
    assert context["unicode_problematic_chars"] == ""

    latex_output = result.latex_output
    assert "\\usepackage{ts-glossary}" not in latex_output


def test_article_switches_to_lualatex_for_non_latin_scripts(
    article_template: WrappableTemplate,
    tmp_path: Path,
) -> None:
    body = "Texte avec un caractère chinois 漢 et un emoji 😀."
    state = DocumentState()
    result = wrap_template_document(
        template=article_template,
        default_slot="mainmatter",
        slot_outputs={"mainmatter": body},
        document_state=state,
        template_overrides=None,
        output_dir=tmp_path,
        copy_assets=False,
    )

    context = result.template_context
    assert context["latex_engine"] == "lualatex"
    assert "漢" in context["unicode_problematic_chars"]
    assert "😀" in context["unicode_problematic_chars"]
    assert context["pdflatex_extra_packages"] == []

    latex_output = result.latex_output
    assert "\\usepackage{ts-glossary}" not in latex_output
    assert "\\usepackage[T1]{fontenc}" not in latex_output
