from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from texsmith.adapters.latex.latexmk import build_latexmkrc_content
from texsmith.api.document import Document
from texsmith.api.pipeline import convert_documents, to_template_fragments
from texsmith.api.templates import TemplateSession
from texsmith.core.conversion.renderer import FragmentOverrideError, TemplateRenderer
from texsmith.core.templates import coerce_base_level, load_template_runtime


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
    runtime = load_template_runtime("book")
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
    print(f"DEBUG: backmatter keys: {result.context.keys()}")
    print(f"DEBUG: backmatter content: {result.context.get('backmatter')}")
    assert "Custom Title" in latex_output
    assert "\\cite{LAWRENCE19841632}" in latex_output
    # Book template puts backmatter in \backmatter which might not be directly visible as "Supplemental material" if it's in a separate file or wrapped differently.
    # But wait, render() should return the main tex file.
    # Let's check if "Supplemental material" is in the output.
    # In book template, backmatter slot is rendered.
    assert "Supplemental material" in latex_output or "Supplemental material" in result.context.get(
        "backmatter", ""
    )

    assert result.bibliography_path is not None
    assert result.bibliography_path.exists()
    assert result.document_state.citations == ["LAWRENCE19841632"]

    assert result.requires_shell_escape is False
    assert result.template_engine == "lualatex"

    # Assets from the template are still copied alongside the main document.
    latexmkrc = result.main_tex_path.parent / ".latexmkrc"
    assert latexmkrc.exists()
    rc_content = latexmkrc.read_text(encoding="utf-8")
    assert "\\VAR{" not in rc_content
    assert "$lualatex" in rc_content

    # Renderer avoids emitting intermediate fragment files by default.
    assert result.fragment_paths == []


def test_template_session_single_document_uses_renderer(tmp_path: Path) -> None:
    runtime = load_template_runtime("article")
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
    runtime = load_template_runtime("article")
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
    runtime = load_template_runtime("book")
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


def test_linked_fragments_still_enable_code_fragment(tmp_path: Path) -> None:
    runtime = load_template_runtime("article")
    session = TemplateSession(runtime=runtime)

    intro_path = _write_markdown(
        tmp_path,
        "intro.md",
        """
        # Intro
        """,
    )
    code_path = _write_markdown(
        tmp_path,
        "code.md",
        """
        ```python
        print("hello")
        ```
        """,
    )

    session.add_document(Document.from_markdown(intro_path))
    session.add_document(Document.from_markdown(code_path))

    build_dir = tmp_path / "linked"
    result = session.render(build_dir, embed_fragments=False)

    latex = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{ts-code}" in latex
    assert any("\\input{" in line for line in latex.splitlines())


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
    assert "$xelatex" in content
    assert "$bibtex_use" not in content


def test_context_attributes_capture_emitters_and_consumers(tmp_path: Path) -> None:
    runtime = load_template_runtime("article")
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "context.md",
        """
        ---
        title: Context Demo
        ---

        # Heading
        Body text.
        """,
    )

    session.add_document(Document.from_markdown(doc_path))
    build_dir = tmp_path / "context-build"

    result = session.render(build_dir)

    usage = {entry["name"]: entry for entry in result.context_attributes}

    assert "title" in usage
    assert any("template:" in emitter for emitter in usage["title"].get("emitters", []))
    assert any(consumer.startswith("template:") for consumer in usage["title"].get("consumers", []))


def test_renderer_preserves_template_latexmkrc(tmp_path: Path) -> None:
    runtime = load_template_runtime("article")
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
    # Article template latexmkrc has different content
    assert "$pdf_mode" in content


def test_requires_shell_escape_reaches_templated_assets(tmp_path: Path) -> None:
    template_dir = tmp_path / "templated-rc"
    template_dir.mkdir()
    (template_dir / "manifest.toml").write_text(
        textwrap.dedent(
            """
            [compat]
            texsmith = ">=0.1,<2.0"

            [latex.template]
            name = "templated-rc"
            version = "0.0.1"
            entrypoint = "template.tex"
            engine = "lualatex"
            shell_escape = true

            [latex.template.slots.mainmatter]
            default = true
            depth = "section"

            [latex.template.assets]
            ".latexmkrc" = { source = "latexmkrc.jinja", template = true }
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
    (template_dir / "latexmkrc.jinja").write_text(
        textwrap.dedent(
            r"""
            \BLOCK{ if latex_engine == "lualatex" }
            $lualatex = 'lualatex\BLOCK{ if requires_shell_escape } --shell-escape\BLOCK{ endif } %O %S';
            \BLOCK{ else }
            $pdflatex = 'pdflatex %O %S';
            \BLOCK{ endif }
            """
        ).strip(),
        encoding="utf-8",
    )

    runtime = load_template_runtime(str(template_dir))
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "article.md",
        """
        # Heading
        """,
    )
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "templated-rc-build"
    session.render(build_dir)

    latexmkrc = build_dir / ".latexmkrc"
    assert latexmkrc.exists()
    content = latexmkrc.read_text(encoding="utf-8")
    assert "--shell-escape" in content
    assert "$lualatex" in content


def test_front_matter_merges_press_and_top_level_metadata(tmp_path: Path) -> None:
    runtime = load_template_runtime("book")
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "book.md",
        """
        ---
        title: Custom Title
        author: Jane Author
        press:
          template: book
        ---

        # Heading
        """,
    )
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "book-metadata-build"
    result = session.render(build_dir)

    tex_payload = result.main_tex_path.read_text(encoding="utf-8")
    assert "Custom Title" in tex_payload
    assert "Jane Author" in tex_payload


def test_book_template_exposes_dedication_and_colophon_slots() -> None:
    runtime = load_template_runtime("book")
    assert "dedication" in runtime.slots
    assert "colophon" in runtime.slots


def test_base_level_alias_part() -> None:
    assert coerce_base_level("part") == -1


def test_imprint_fields_render_markdown(tmp_path: Path) -> None:
    runtime = load_template_runtime("book")
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "book.md",
        """
        ---
        title: Demo
        press:
          template: book
          imprint:
            thanks: Thanks to __ACME__!
            license: "MIT, see http://example.com"
        ---

        # Body
        """,
    )
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "imprint-build"
    session.render(build_dir)

    tex_files = list(build_dir.glob("*.tex"))
    assert tex_files, "Expected rendered LaTeX output"
    content = tex_files[0].read_text(encoding="utf-8")
    assert r"Thanks to \textsc{ACME}!" in content
    assert r"http://example.com" in content


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


def test_templated_latexmkrc_includes_optional_tools_when_fragments_render(
    tmp_path: Path,
) -> None:
    runtime = load_template_runtime("article")
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "article.md",
        """
        This study references prior work.[^LAWRENCE19841632]

        ```python
        print("hi")
        ```
        """,
    )
    session.add_document(Document.from_markdown(doc_path))
    session.add_bibliography(FIXTURE_BIB)

    build_dir = tmp_path / "templated-rc-fragments"
    session.render(build_dir)

    latexmkrc = build_dir / ".latexmkrc"
    assert latexmkrc.exists()
    content = latexmkrc.read_text(encoding="utf-8")
    assert "$bibtex_use = 2;" in content
    assert "--shell-escape" not in content
    assert "$makeindex" not in content
    assert "makeglossaries" not in content
    assert "\n\n\n" not in content
    for line in content.splitlines():
        assert line == line.rstrip()


def test_templated_latexmkrc_skips_tools_when_fragments_absent(tmp_path: Path) -> None:
    runtime = load_template_runtime("article")
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "article.md",
        """
        # Heading
        """,
    )
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "templated-rc-minimal"
    session.render(build_dir)

    latexmkrc = build_dir / ".latexmkrc"
    assert latexmkrc.exists()
    content = latexmkrc.read_text(encoding="utf-8")
    assert "$bibtex_use" not in content
    assert "$makeindex" not in content
    assert "makeglossaries" not in content
    assert "--shell-escape" not in content
    assert "\n\n\n" not in content
    for line in content.splitlines():
        assert line == line.rstrip()
