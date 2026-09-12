from __future__ import annotations

from pathlib import Path
import tempfile

from texsmith.core.documents import Document
from texsmith.core.templates.session import get_template


def test_combining_marks_stick_to_base_script() -> None:
    """A combining mark never splits the run of the script it decorates.

    The ``scripts`` pass wraps each foreign run in ``\\tsscript{slug}{…}``; a
    Syriac word ending on a combining diacritic must stay one Syriac run, even
    though the summary still records the diacritics coverage the fonts need.
    """
    tmp_path = Path(tempfile.mkdtemp())
    source = tmp_path / "syriac.md"
    source.write_text("ܛܘܒܝܗܘܢ ܠܡܣܟܢ̈\n", encoding="utf-8")

    session = get_template("article")
    session.add_document(Document.from_markdown(source))
    result = session.render(tmp_path / "build")

    content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\tsscript{syriacfull}{ܛܘܒܝܗܘܢ ܠܡܣܟܢ̈}" in content
    assert "\\tsscript{diacritics}" not in content
    assert content.count("\\tsscript{") == 1

    usage = result.context.get("fonts", {}).get("script_usage") or []
    slugs = {entry.get("slug") for entry in usage}
    assert "syriacfull" in slugs
    # The summary still records diacritics coverage, but the body must not split it.
    assert "diacritics" in slugs
