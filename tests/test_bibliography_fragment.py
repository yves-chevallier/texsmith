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

            Some text with a citation[^LAWRENCE19841632].

            [^LAWRENCE19841632]: See bibliography.
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

            Some text with a citation[^LAWRENCE19841632].

            [^LAWRENCE19841632]: See bibliography.
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
