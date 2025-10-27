from __future__ import annotations

from pathlib import Path
import textwrap

from texsmith.api.document import Document
from texsmith.api.templates import TemplateSession
from texsmith.core.templates import load_template_runtime


FIXTURE_BIB = Path(__file__).resolve().parent / "fixtures" / "bib" / "b.bib"


def _write_markdown(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def test_template_session_renders_bundle_via_renderer(tmp_path: Path) -> None:
    runtime = load_template_runtime(str(Path("templates") / "nature"))
    session = TemplateSession(runtime=runtime)

    doc1_path = _write_markdown(
        tmp_path,
        "chapter.md",
        """
        # Introduction
        This study references prior work.[^LAWRENCE19841632]
        """,
    )
    doc2_path = _write_markdown(
        tmp_path,
        "appendix.md",
        """
        # Appendix

        Supplemental material.
        """,
    )

    document_one = Document.from_markdown(doc1_path)
    document_two = Document.from_markdown(doc2_path)

    session.add_document(document_one)
    session.add_document(document_two, slot="backmatter")
    session.add_bibliography(FIXTURE_BIB)
    session.update_options({"title": "Custom Title"})

    build_dir = tmp_path / "build"
    result = session.render(build_dir)

    assert result.main_tex_path.exists()
    latex_output = result.main_tex_path.read_text(encoding="utf-8")
    assert "Custom Title" in latex_output
    assert "\\cite{LAWRENCE19841632}" in latex_output
    assert "Supplemental material" in result.context.get("backmatter", "")

    assert result.bibliography_path is not None
    assert result.bibliography_path.exists()
    assert result.document_state.citations == ["LAWRENCE19841632"]

    assert result.requires_shell_escape is True
    assert result.template_engine == "lualatex"

    # Assets from the template are still copied alongside the main document.
    sn_class = result.main_tex_path.parent / "sn-jnl.cls"
    assert sn_class.exists()

    # Renderer avoids emitting intermediate fragment files by default.
    assert result.fragment_paths == []


def test_template_session_single_document_uses_renderer(tmp_path: Path) -> None:
    runtime = load_template_runtime(str(Path("templates") / "nature"))
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "article.md",
        """
        # Overview

        Plain paragraph content without citations.
        """,
    )

    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "single"
    result = session.render(build_dir)

    assert result.main_tex_path.exists()
    latex = result.main_tex_path.read_text(encoding="utf-8")
    assert "Overview" in latex
    assert result.fragment_paths == []
