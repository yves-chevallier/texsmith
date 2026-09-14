from __future__ import annotations

from pathlib import Path
import textwrap
import warnings

from texsmith.core.documents import Document
from texsmith.core.templates.session import get_template


FIXTURE_BIB = Path(__file__).resolve().parent / "fixtures" / "bib" / "b.bib"


def test_fragment_injects_biblatex_and_csquotes(tmp_path: Path) -> None:
    doc_path = tmp_path / "cheese.md"
    doc_path.write_text(
        textwrap.dedent(
            """
            # Cheese

            Some text with a citation @LAWRENCE19841632.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    session = get_template("article")
    session.add_document(Document.from_markdown(doc_path))
    session.add_bibliography(FIXTURE_BIB)

    build_dir = tmp_path / "build"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = session.render(build_dir)

    content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{csquotes}" in content
    assert "\\usepackage[\n  backend=biber," in content
    assert "\\addbibresource{texsmith-bibliography.bib}" in content
    assert "\\printbibliography" in content
    # Default: URL fields are suppressed and the title becomes a hyperlink to
    # the entry's url, which avoids overfull \hbox warnings on long URLs.
    assert "\\DeclareFieldFormat{url}{}" in content
    assert "\\href{\\thefield{url}}" in content


def _bibliography_doc(tmp_path: Path) -> Path:
    doc_path = tmp_path / "cheese.md"
    doc_path.write_text(
        textwrap.dedent(
            """
            # Cheese

            Some text with a citation @LAWRENCE19841632.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return doc_path


def test_bibliography_show_urls_opt_in_keeps_raw_urls(tmp_path: Path) -> None:
    """Setting bibliography_show_urls=true must skip the title-hyperlink overrides."""
    doc_path = _bibliography_doc(tmp_path)

    session = get_template("article")
    session.set_options({"bibliography_show_urls": True})
    session.add_document(Document.from_markdown(doc_path))
    session.add_bibliography(FIXTURE_BIB)

    build_dir = tmp_path / "build"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = session.render(build_dir)

    content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\printbibliography" in content
    # Opt-in mode: do NOT inject the URL-suppressing field formats.
    assert "\\DeclareFieldFormat{url}{}" not in content
    assert "\\href{\\thefield{url}}" not in content


def test_bare_citation_is_the_short_form_by_default(tmp_path: Path) -> None:
    """tmark C51: a bare ``@key`` renders ``\\cite``, not the narrative ``\\textcite``."""
    doc_path = _bibliography_doc(tmp_path)

    session = get_template("article")
    session.add_document(Document.from_markdown(doc_path))
    session.add_bibliography(FIXTURE_BIB)

    build_dir = tmp_path / "build"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = session.render(build_dir)

    content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\cite{LAWRENCE19841632}" in content
    assert "\\textcite{LAWRENCE19841632}" not in content


def test_citations_narrative_feature_switches_bare_citations_to_textcite(tmp_path: Path) -> None:
    """``press.features: {citations.narrative: true}`` reaches ``tmark.write`` untouched.

    TeXSmith does not translate this feature into a writer option: tmark reads
    it straight off the document's own front matter (the ``Document`` IR
    carries it through ``codec.encode_document``), the same way it already
    reads ``press.features.strict``. This is the regression guard for that.
    """
    doc_path = tmp_path / "cheese.md"
    doc_path.write_text(
        textwrap.dedent(
            """
            ---
            press:
              features:
                citations.narrative: true
            ---

            # Cheese

            Some text with a citation @LAWRENCE19841632.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    session = get_template("article")
    session.add_document(Document.from_markdown(doc_path))
    session.add_bibliography(FIXTURE_BIB)

    build_dir = tmp_path / "build"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = session.render(build_dir)

    content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\textcite{LAWRENCE19841632}" in content
    assert "\\cite{LAWRENCE19841632}" not in content
