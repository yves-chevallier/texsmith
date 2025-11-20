from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from texsmith.adapters.latex.latexmk import build_latexmkrc_content
from texsmith.api.document import Document
from texsmith.api.pipeline import convert_documents, to_template_fragments
from texsmith.api.templates import TemplateSession
from texsmith.core.conversion.renderer import FragmentOverrideError, TemplateRenderer
from texsmith.core.templates import load_template_runtime


FIXTURE_BIB = Path(__file__).resolve().parent / "fixtures" / "bib" / "b.bib"


def _write_markdown(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def _create_minimal_template(tmp_path: Path, *, engine: str, shell_escape: bool) -> Path:
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "manifest.toml").write_text(
        textwrap.dedent(
            f"""
            [compat]
            texsmith = ">=0.1,<2.0"

            [latex.template]
            name = "demo"
            version = "0.0.1"
            entrypoint = "template.tex"
            engine = "{engine}"
            shell_escape = {str(bool(shell_escape)).lower()}

            [latex.template.slots.mainmatter]
            default = true
            depth = "section"
            """
        ).strip(),
        encoding="utf-8",
    )
    (template_dir / "template.tex").write_text(
        textwrap.dedent(
            r"""
            \documentclass{article}
            \begin{document}
            \VAR{mainmatter}
            \end{document}
            """
        ).strip(),
        encoding="utf-8",
    )
    return template_dir


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


def test_template_session_propagates_base_level(tmp_path: Path) -> None:
    runtime = load_template_runtime(str(Path("templates") / "nature"))
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "article.md",
        """
        # Heading
        """,
    )

    session.add_document(Document.from_markdown(doc_path))
    session.update_options({"base_level": 3})

    build_dir = tmp_path / "base-level"
    result = session.render(build_dir)

    assert result.context.get("base_level") == 3


def test_template_session_conflicting_overrides(tmp_path: Path) -> None:
    runtime = load_template_runtime(str(Path("templates") / "nature"))
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "article.md",
        """
        # Heading
        """,
    )
    session.add_document(Document.from_markdown(doc_path))
    session.add_document(Document.from_markdown(doc_path), slot="backmatter")

    session.documents[1].slots.add("backmatter", include_document=True)

    # Simulate conflicting overrides at the fragment layer.
    bundle = convert_documents(session.documents, wrap_document=False)
    fragments = to_template_fragments(bundle)
    fragments[0].template_overrides = {"press": {"title": "First Title"}}
    fragments[1].template_overrides = {"press": {"title": "Second Title"}}

    build_dir = tmp_path / "conflict"
    renderer = TemplateRenderer(runtime, emitter=session.emitter)
    with pytest.raises(FragmentOverrideError) as excinfo:
        renderer.render(fragments, output_dir=build_dir)
    assert "press.title" in str(excinfo.value)


def test_renderer_generates_latexmkrc_when_missing(tmp_path: Path) -> None:
    template_dir = _create_minimal_template(tmp_path, engine="xelatex", shell_escape=True)
    runtime = load_template_runtime(str(template_dir))
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "paper.md",
        """
        # Title

        Body text.
        """,
    )
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "rc-build"
    session.render(build_dir)

    latexmkrc = build_dir / ".latexmkrc"
    assert latexmkrc.exists()
    content = latexmkrc.read_text(encoding="utf-8")
    assert "$root_filename = 'paper';" in content
    assert "$pdf_mode = 5;" in content
    assert "$xelatex = 'xelatex --shell-escape %O %S';" in content
    assert "$bibtex_use" not in content


def test_renderer_preserves_template_latexmkrc(tmp_path: Path) -> None:
    runtime = load_template_runtime(str(Path("templates") / "nature"))
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "article.md",
        """
        # Heading
        """,
    )
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "nature-rc"
    session.render(build_dir)

    latexmkrc = build_dir / ".latexmkrc"
    assert latexmkrc.exists()
    content = latexmkrc.read_text(encoding="utf-8").strip()
    assert content == "$ENV{'TEXMFCACHE'} = 'texmf-cache';"


def test_latexmkrc_content_optional_sections() -> None:
    content = build_latexmkrc_content(
        root_filename="demo",
        engine="lualatex",
        requires_shell_escape=False,
        bibliography=True,
        index_engine="texindy",
        has_index=True,
        has_glossary=True,
    )

    assert "$pdf_mode = 4;" in content
    assert "$lualatex = 'lualatex %O %S';" in content
    assert "$bibtex_use = 2;" in content
    assert "$makeindex = 'texindy %O -o %D %S';" in content
    assert "makeglossaries" in content
    assert "--shell-escape" not in content
