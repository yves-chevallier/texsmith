from pathlib import Path

import pytest

from texsmith.core.context import DocumentState
from texsmith.core.templates import (
    TemplateError,
    WrappableTemplate,
    copy_template_assets,
    load_template,
)
from texsmith.core.templates.wrapper import wrap_template_document


@pytest.fixture
def project_root(monkeypatch: pytest.MonkeyPatch) -> Path:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def book_template(project_root: Path) -> WrappableTemplate:
    return load_template(str(project_root / "src" / "texsmith" / "builtin_templates" / "book"))


@pytest.fixture
def article_template(project_root: Path) -> WrappableTemplate:
    return load_template(str(project_root / "src" / "texsmith" / "builtin_templates" / "article"))


def test_iter_assets_declares_required_files(book_template: WrappableTemplate) -> None:
    assets = list(book_template.iter_assets())
    destinations = {asset.destination for asset in assets}

    assert Path("covers") in destinations
    assert Path("covers/circles.tex") in destinations
    assert Path("titlepage.tex") in destinations
    assert Path("mkbook.cls") in destinations


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


def test_wrap_document_includes_index_when_flag_true(
    book_template: WrappableTemplate,
) -> None:
    context = book_template.prepare_context("")
    context["index_entries"] = True
    wrapped = book_template.wrap_document("", context=context)
    assert "\\makeindex" in wrapped
    assert "\\printindex" in wrapped


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
    book_template: WrappableTemplate,
) -> None:
    context = book_template.prepare_context("")
    context["acronyms"] = {"HTTP": "Hypertext Transfer Protocol"}
    wrapped = book_template.wrap_document("", context=context)
    assert "\\makeglossaries" in wrapped
    assert "\\newacronym{HTTP}{HTTP}{Hypertext Transfer Protocol}" in wrapped
    assert "\\printglossary[type=\\acronymtype" in wrapped


def test_copy_template_assets_materialises_payload(
    book_template: WrappableTemplate, tmp_path: Path
) -> None:
    destination_root = tmp_path
    context = book_template.prepare_context("")
    copy_template_assets(book_template, destination_root, context=context)

    assert (destination_root / "mkbook.cls").exists()
    circles = destination_root / "covers" / "circles.tex"
    assert circles.exists()
    content = circles.read_text(encoding="utf-8")
    assert "\\VAR{" not in content
    assert "\\BLOCK" not in content
    assert "\\def\\covercolor{indigo(dye)}" in content
    assert (destination_root / "titlepage.tex").exists()


def test_load_template_from_shortcut_path(book_template: WrappableTemplate) -> None:
    shortcut = load_template("./src/texsmith/builtin_templates/book")
    assert shortcut.info.name == book_template.info.name
    assert shortcut.info.entrypoint == book_template.info.entrypoint
    slug = load_template("book")
    assert slug.info.name == book_template.info.name


def test_documentclass_defaults(article_template: WrappableTemplate) -> None:
    wrapped = article_template.wrap_document("")
    assert r"\documentclass[a4paper]{article}" in wrapped
    assert "landscape]{article}" not in wrapped
    assert r"\geometry{margin=2.5cm,a4paper}" in wrapped
    assert "\\usepackage{imakeidx}" not in wrapped
    assert "\\usepackage[acronym]{glossaries}" not in wrapped
    assert "\\makeindex" not in wrapped
    assert "\\printindex" not in wrapped
    assert "\\newacronym" not in wrapped


def test_documentclass_overrides(article_template: WrappableTemplate) -> None:
    overrides = {
        "paper": "a3",
        "orientation": "landscape",
        "title": "Demo Article",
        "author": "Alice Example",
    }
    wrapped = article_template.wrap_document("", overrides=overrides)
    assert r"\documentclass[a3paper,landscape]{article}" in wrapped
    assert r"\geometry{margin=2.5cm,a3paper,landscape}" in wrapped
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
    shortcut = load_template("./src/texsmith/builtin_templates/article")
    assert shortcut.info.name == article_template.info.name
    slug = load_template("article")
    assert slug.info.name == article_template.info.name


def test_rejects_invalid_paper_option(article_template: WrappableTemplate) -> None:
    with pytest.raises(TemplateError):
        article_template.wrap_document("", overrides={"paper": "iso"})


def test_rejects_invalid_orientation_option(article_template: WrappableTemplate) -> None:
    with pytest.raises(TemplateError):
        article_template.wrap_document("", overrides={"orientation": "diagonal"})


def test_article_includes_index_when_flag_true(
    article_template: WrappableTemplate,
) -> None:
    context = article_template.prepare_context("")
    context["index_entries"] = True
    context["index_engine"] = "texindy"
    wrapped = article_template.wrap_document("", context=context)
    assert "\\usepackage[xindy]{imakeidx}" in wrapped
    assert "\\makeindex" in wrapped
    assert "\\printindex" in wrapped


def test_article_falls_back_to_makeindex_when_xindy_missing(
    article_template: WrappableTemplate,
) -> None:
    context = article_template.prepare_context("")
    context["index_entries"] = True
    context["index_engine"] = "makeindex"
    wrapped = article_template.wrap_document("", context=context)
    assert "\\usepackage{imakeidx}" in wrapped
    assert "\\usepackage[xindy]{imakeidx}" not in wrapped


def test_article_includes_acronyms_when_present(
    article_template: WrappableTemplate,
) -> None:
    context = article_template.prepare_context("")
    context["acronyms"] = {"HTTP": "Hypertext Transfer Protocol"}
    wrapped = article_template.wrap_document("", context=context)
    assert "\\usepackage[acronym,nomain]{glossaries}" in wrapped
    assert "\\makeglossaries" in wrapped
    assert "\\newacronym{HTTP}{HTTP}{Hypertext Transfer Protocol}" in wrapped
    assert "\\printglossary[type=\\acronymtype" in wrapped


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
    assert "\\usepackage{ts-fonts}" in latex_output


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
    assert "\\usepackage{ts-fonts}" in latex_output
    assert "\\usepackage[T1]{fontenc}" not in latex_output
