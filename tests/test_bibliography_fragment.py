from __future__ import annotations

from pathlib import Path
import textwrap
import warnings

from texsmith.api.document import Document
from texsmith.api.templates import get_template


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
