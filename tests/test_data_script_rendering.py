from __future__ import annotations

from pathlib import Path

from texsmith.api.document import Document
from texsmith.api.pipeline import convert_documents


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_data_script_paragraphs_group_into_environments(tmp_path: Path) -> None:
    html = """
    <html><body>
    <p data-script="arabics">ألف</p>
    <p data-script="arabics">باء</p>
    <p data-script="chinese">漢字</p>
    </body></html>
    """
    doc_path = _write(tmp_path / "doc.html", html)
    doc = Document.from_html(doc_path, full_document=True)

    bundle = convert_documents([doc], output_dir=tmp_path)
    latex = bundle.fragments[0].latex
    assert latex.count("\\begin{arabics}") == 1
    assert "\\begin{arabics}" in latex and "\\end{arabics}" in latex
    assert "ألف" in latex and "باء" in latex
    assert "\\begin{chinese}" in latex and "\\end{chinese}" in latex

    usage = bundle.fragments[0].conversion.document_state.script_usage
    slugs = {entry.get("slug") for entry in usage}
    assert {"arabics", "chinese"} <= slugs


def test_data_script_spans_render_to_text_commands(tmp_path: Path) -> None:
    html = """
    <html><body>
    <p>Hello <span data-script="arabics">العربية</span> world.</p>
    </body></html>
    """
    doc_path = _write(tmp_path / "inline.html", html)
    doc = Document.from_html(doc_path, full_document=True)

    bundle = convert_documents([doc], output_dir=tmp_path)
    latex = bundle.fragments[0].latex
    assert "\\textarabics{العربية}" in latex
    usage = bundle.fragments[0].conversion.document_state.script_usage
    slugs = {entry.get("slug") for entry in usage}
    assert "arabics" in slugs
