from __future__ import annotations

from pathlib import Path
import textwrap

from texsmith.api.document import Document
from texsmith.api.templates import get_template


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def test_promoted_title_keeps_section_level(tmp_path: Path) -> None:
    doc_path = _write(tmp_path, "a.md", "# Zeus\n\nHello.")
    session = get_template("article")
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "build"
    result = session.render(build_dir)

    content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\section{Zeus}" in content
    assert "\\subsection{Zeus}" not in content
