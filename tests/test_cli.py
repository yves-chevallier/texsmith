from pathlib import Path
import sys
import types
from typing import Any

import pytest
from typer.testing import CliRunner

from texsmith.cli import DEFAULT_MARKDOWN_EXTENSIONS, app
from texsmith.cli.commands import build as build_cmd


def _template_path(name: str) -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "templates" / name


def test_convert_command() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        html_file = Path("index.html")
        html_file.write_text(
            "<article class='md-content__inner'><h2 id='intro'>Introduction</h2></article>",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "convert",
                str(html_file),
                "--base-level",
                "0",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "\\section{Introduction}\\label{intro}" in result.stdout


def test_heading_level_option() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        html_file = Path("index.html")
        html_file.write_text(
            "<article class='md-content__inner'><h2 id='intro'>Overview</h2></article>",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "convert",
                str(html_file),
                "-h",
                "1",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "\\subsection{Overview}\\label{intro}" in result.stdout


def test_copy_assets_disabled() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        html_file = Path("index.html")
        html_file.write_text(
            "<article class='md-content__inner'><img src='logo.png' alt='Logo'></article>",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "convert",
                str(html_file),
                "--no-copy-assets",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "Logo" in result.stdout
    assert "\\includegraphics" not in result.stdout


def test_convert_markdown_file(monkeypatch: Any) -> None:
    class DummyMarkdown:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def convert(self, text: str) -> str:
            html_parts: list[str] = []
            for line in text.splitlines():
                if line.startswith("# "):
                    html_parts.append(f"<h1>{line[2:].strip()}</h1>")
                elif line.strip():
                    html_parts.append(f"<p>{line.strip()}</p>")
            return "".join(html_parts)

    monkeypatch.setitem(sys.modules, "markdown", types.SimpleNamespace(Markdown=DummyMarkdown))

    runner = CliRunner()
    with runner.isolated_filesystem():
        markdown_file = Path("index.md")
        markdown_file.write_text("# Intro\n\nParagraph text.", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "convert",
                str(markdown_file),
                "-h",
                "1",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "\\section{Intro}" in result.stdout
    assert "Paragraph text." in result.stdout


def test_default_markdown_extensions(monkeypatch: Any) -> None:
    recorded: dict[str, list[str] | None] = {"extensions": None}

    class DummyMarkdown:
        def __init__(self, *args: object, **kwargs: object) -> None:
            recorded["extensions"] = list(kwargs.get("extensions") or [])

        def convert(self, _: str) -> str:
            return "<p>content</p>"

    monkeypatch.setitem(sys.modules, "markdown", types.SimpleNamespace(Markdown=DummyMarkdown))

    runner = CliRunner()
    with runner.isolated_filesystem():
        markdown_file = Path("doc.md")
        markdown_file.write_text("plain text", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "convert",
                str(markdown_file),
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert recorded["extensions"] == DEFAULT_MARKDOWN_EXTENSIONS


def test_markdown_extensions_option_extends_defaults(monkeypatch: Any) -> None:
    recorded: dict[str, list[str] | None] = {"extensions": None}

    class DummyMarkdown:
        def __init__(self, *args: object, **kwargs: object) -> None:
            recorded["extensions"] = list(kwargs.get("extensions") or [])

        def convert(self, _: str) -> str:
            return "<p>content</p>"

    dummy_module = types.SimpleNamespace(Markdown=DummyMarkdown)
    monkeypatch.setitem(sys.modules, "markdown", dummy_module)

    runner = CliRunner()
    with runner.isolated_filesystem():
        markdown_file = Path("doc.md")
        markdown_file.write_text("plain text", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "convert",
                str(markdown_file),
                "-x",
                "custom_extension,another_extension",
                "-x",
                "custom_extension",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert recorded["extensions"] == [
        *DEFAULT_MARKDOWN_EXTENSIONS,
        "custom_extension",
        "another_extension",
    ]


def test_disable_markdown_extensions_option(tmp_path: Path, monkeypatch: Any) -> None:
    recorded: dict[str, list[str] | None] = {"extensions": None}

    class DummyMarkdown:
        def __init__(self, *args: object, **kwargs: object) -> None:
            recorded["extensions"] = list(kwargs.get("extensions") or [])

        def convert(self, _: str) -> str:
            return "<p>content</p>"

    dummy_module = types.SimpleNamespace(Markdown=DummyMarkdown)
    monkeypatch.setitem(sys.modules, "markdown", dummy_module)

    markdown_file = tmp_path / "doc.md"
    markdown_file.write_text("plain text", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(tmp_path / "output"),
            "--disable-markdown-extensions",
            "footnotes, pymdownx.details",
            "--disable-markdown-extensions",
            "pymdownx.magiclink",
        ],
    )

    assert result.exit_code == 0, result.stdout
    disabled = {"footnotes", "pymdownx.details", "pymdownx.magiclink"}
    assert disabled.isdisjoint(set(recorded["extensions"] or []))
    assert set(DEFAULT_MARKDOWN_EXTENSIONS) - disabled <= set(recorded["extensions"] or [])


def test_list_extensions_option() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--list-extensions"])

    assert result.exit_code == 0, result.stdout
    listed = [line for line in result.stdout.splitlines() if line]
    assert listed == DEFAULT_MARKDOWN_EXTENSIONS


def test_rejects_mkdocs_configuration(tmp_path: Path) -> None:
    runner = CliRunner()
    config_file = tmp_path / "mkdocs.yml"
    config_file.write_text("site_name: Demo", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "convert",
            str(config_file),
        ],
    )

    assert result.exit_code == 1
    assert "configuration files are not supported" in result.stderr.lower()


def test_mdx_math_extension_preserves_latex() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        markdown_file = Path("math.md")
        markdown_file.write_text(
            ("# Math\n\nInline $E = mc^2$ example.\n\n$$\n\\nabla \\cdot \\mathbf{E} = 0\n$$\n"),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "convert",
                str(markdown_file),
                "-x",
                "mdx_math",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "$E = mc^2$" in result.stdout
    assert result.stdout.count("$$") == 2
    assert "\\mathbf{E}" in result.stdout
    assert "\\textbackslash" not in result.stdout


def test_multi_document_stdout_concat() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        first = Path("first.md")
        first.write_text("# First\n\nAlpha.", encoding="utf-8")
        second = Path("second.md")
        second.write_text("# Second\n\nBeta.", encoding="utf-8")

        result = runner.invoke(app, ["convert", str(first), str(second)])

    assert result.exit_code == 0, result.stdout
    assert "\\chapter{First}" in result.stdout
    assert "\\chapter{Second}" in result.stdout
    assert result.stdout.index("First") < result.stdout.index("Second")


def test_multi_document_output_file(tmp_path: Path) -> None:
    runner = CliRunner()
    first = tmp_path / "chapter1.md"
    first.write_text("# Chapter One\n\nContent.", encoding="utf-8")
    second = tmp_path / "chapter2.md"
    second.write_text("# Chapter Two\n\nMore text.", encoding="utf-8")
    output_file = tmp_path / "combined.tex"

    result = runner.invoke(
        app,
        [
            "convert",
            str(first),
            str(second),
            "--output",
            str(output_file),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "\\chapter{Chapter One}" in content
    assert "\\chapter{Chapter Two}" in content
    assert content.index("Chapter One") < content.index("Chapter Two")


def test_slot_injection_extracts_abstract(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        "## Abstract\n\nThis is the abstract.\n\n## Introduction\n\nBody text.",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[1]
    template_dir = project_root / "templates" / "nature"
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--slot",
            "abstract:Abstract",
        ],
    )

    assert result.exit_code == 0, result.stderr
    tex_path = output_dir / "paper.tex"
    assert tex_path.exists()
    content = tex_path.read_text(encoding="utf-8")
    assert "\\abstract{" in content
    assert "This is the abstract." in content
    assert "\\subsection{Abstract}" not in content
    assert "\\subsection{Introduction}" in content


def test_slot_injection_matches_label(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        "## Abstract {#absSection}\n\nLabel abstract.\n\n## Body\n\nContent.",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[1]
    template_dir = project_root / "templates" / "nature"
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--slot",
            "abstract:#absSection",
        ],
    )

    assert result.exit_code == 0, result.stderr
    tex_path = output_dir / "paper.tex"
    content = tex_path.read_text(encoding="utf-8")
    assert "Label abstract." in content
    assert "\\subsection{Abstract}" not in content


def test_slot_injection_warns_unknown_slot(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text("## Abstract\n\nContent.", encoding="utf-8")

    template_dir = _template_path("article")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--slot",
            "abstract:Abstract",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert "slot 'abstract' is not defined" in result.stderr.lower()
    tex_path = output_dir / "paper.tex"
    assert tex_path.exists()
    content = tex_path.read_text(encoding="utf-8")
    assert "\\subsection{Abstract}" in content


def test_slot_injection_preserves_footnotes(tmp_path: Path) -> None:
    runner = CliRunner()
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            "examples/scientific-paper/cheese.md",
            "--output-dir",
            str(output_dir),
            "--template",
            "templates/nature",
            "--slot",
            "abstract:Abstract",
            "--bibliography",
            "examples/scientific-paper/cheese.bib",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert "Reference to '1' is not in your bibliography" not in result.stderr
    tex_path = output_dir / "cheese.tex"
    assert tex_path.exists()
    content = tex_path.read_text(encoding="utf-8")
    assert "\\footnote{" in content
    assert "Parmigiano-Reggiano" in content


def test_front_matter_slots_mapping(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        """---
meta:
  slots:
    abstract: Abstract
---
## Abstract

Front matter abstract.

## Body

Main discussion.
""",
        encoding="utf-8",
    )

    template_dir = _template_path("nature")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
        ],
    )

    assert result.exit_code == 0, result.stderr
    tex_path = output_dir / "paper.tex"
    content = tex_path.read_text(encoding="utf-8")
    assert "\\abstract{" in content
    assert "Front matter abstract." in content
    assert "\\subsection{Abstract}" not in content


def test_front_matter_slots_top_level_mapping(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        """---
slots:
  abstract: Abstract
meta:
  title: Demo
---
## Abstract

Front matter abstract.

## Body

Main discussion.
""",
        encoding="utf-8",
    )

    template_dir = _template_path("nature")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
        ],
    )

    assert result.exit_code == 0, result.stderr
    tex_path = output_dir / "paper.tex"
    content = tex_path.read_text(encoding="utf-8")
    assert "\\abstract{" in content
    assert "Front matter abstract." in content


def test_cli_slot_overrides_front_matter(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        """---
meta:
  slots:
    abstract: Abstract
---
## Abstract

Front matter abstract.

## Highlight

Override from CLI.
""",
        encoding="utf-8",
    )

    template_dir = _template_path("nature")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--slot",
            "abstract:Highlight",
        ],
    )

    assert result.exit_code == 0, result.stderr
    tex_path = output_dir / "paper.tex"
    content = tex_path.read_text(encoding="utf-8")
    assert "Override from CLI." in content
    assert "Front matter abstract." in content
    assert "\\subsection{Highlight}" not in content


def test_multi_document_template_generates_inputs(tmp_path: Path) -> None:
    runner = CliRunner()
    chapter1 = tmp_path / "chapter1.md"
    chapter1.write_text("# Chapter One\n\nContent.", encoding="utf-8")
    chapter2 = tmp_path / "chapter2.md"
    chapter2.write_text("# Chapter Two\n\nMore text.", encoding="utf-8")

    template_dir = _template_path("book")
    output_dir = tmp_path / "build"
    result = runner.invoke(
        app,
        [
            "convert",
            str(chapter1),
            str(chapter2),
            "--template",
            str(template_dir),
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.stderr
    fragment_one = output_dir / "chapter1.tex"
    fragment_two = output_dir / "chapter2.tex"
    assert fragment_one.exists()
    assert fragment_two.exists()
    main_file = output_dir / "chapter1-collection.tex"
    assert main_file.exists()
    content = main_file.read_text(encoding="utf-8")
    assert "\\input{chapter1}" in content
    assert "\\input{chapter2}" in content


def test_slot_assignment_targets_specific_file(tmp_path: Path) -> None:
    runner = CliRunner()
    abstract_doc = tmp_path / "abstract.md"
    abstract_doc.write_text("# Abstract\n\nSummary.", encoding="utf-8")
    body_doc = tmp_path / "body.md"
    body_doc.write_text("# Body\n\nContent.", encoding="utf-8")

    template_dir = _template_path("nature")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            str(abstract_doc),
            str(body_doc),
            "--template",
            str(template_dir),
            "--output",
            str(output_dir),
            "--slot",
            f"abstract:{abstract_doc.name}",
        ],
    )

    assert result.exit_code == 0, result.stderr
    main_file = output_dir / "abstract-collection.tex"
    assert main_file.exists()
    content = main_file.read_text(encoding="utf-8")
    assert "\\abstract{\\input{abstract}}" in content
    assert "\\input{body}" in content


def test_slot_assignment_extracts_section_from_file(tmp_path: Path) -> None:
    runner = CliRunner()
    chapter1 = tmp_path / "chapter1.md"
    chapter1.write_text("# Chapter One\n\nBody.", encoding="utf-8")
    chapter2 = tmp_path / "chapter2.md"
    chapter2.write_text(
        "# Chapter Two\n\n## Appendix\n\nAppendix content.",
        encoding="utf-8",
    )

    template_dir = _template_path("book")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "convert",
            str(chapter1),
            str(chapter2),
            "--template",
            str(template_dir),
            "--output",
            str(output_dir),
            "--slot",
            f"backmatter:{chapter2.name}:Appendix",
        ],
    )

    assert result.exit_code == 0, result.stderr
    main_file = output_dir / "chapter1-collection.tex"
    content = main_file.read_text(encoding="utf-8")
    assert "Appendix content." in content
    assert "\\input{chapter2}" in content


def test_build_requires_template(tmp_path: Path) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><h2>Title</h2></article>",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "build",
            str(html_file),
            "--output-dir",
            str(tmp_path / "output"),
        ],
    )

    assert result.exit_code == 1
    assert "requires a LaTeX template" in result.stderr


def test_build_invokes_latexmk(tmp_path: Path, monkeypatch: Any) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><p>Body</p></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    template_dir = _template_path("article")

    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_which(name: str) -> str:
        assert name == "latexmk"
        return "/usr/bin/latexmk"

    def fake_run(cmd: list[str], **kwargs: Any) -> types.SimpleNamespace:
        calls.append((cmd, kwargs))
        pdf_path = Path(kwargs["cwd"]) / "index.pdf"
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="build ok\n", stderr="")

    monkeypatch.setattr(build_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(build_cmd.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "build",
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert calls, "latexmk was not invoked"
    command, kwargs = calls[0]
    assert command[0] == "/usr/bin/latexmk"
    assert "-bibtex" not in command
    pdflatex_args = [arg for arg in command if arg.startswith("-pdflatex=")]
    assert pdflatex_args
    assert any(engine in pdflatex_args[0] for engine in {"xelatex", "lualatex"})
    assert "--shell-escape" in pdflatex_args[0]
    assert command[-1] == "index.tex"
    assert kwargs["cwd"] == output_dir
    assert "build ok" in result.stdout
    assert "PDF document written to" in result.stdout


def test_build_with_bibliography_forces_bibtex(tmp_path: Path, monkeypatch: Any) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        (
            "<article class='md-content__inner'>"
            "<texsmith-missing-footnote data-footnote-id='Ref'>"
            "</texsmith-missing-footnote>"
            "</article>"
        ),
        encoding="utf-8",
    )

    bib_file = tmp_path / "refs.bib"
    bib_file.write_text(
        "@article{Ref, author={Doe, Jane}, title={Demo}, journal={Demo}, year={2024}}",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    template_dir = _template_path("article")

    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_which(name: str) -> str:
        assert name == "latexmk"
        return "/usr/bin/latexmk"

    def fake_run(cmd: list[str], **kwargs: Any) -> types.SimpleNamespace:
        calls.append((cmd, kwargs))
        pdf_path = Path(kwargs["cwd"]) / "index.pdf"
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="build ok\n", stderr="")

    monkeypatch.setattr(build_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(build_cmd.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "build",
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--bibliography",
            str(bib_file),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert calls, "latexmk was not invoked"
    command, _ = calls[0]
    assert "-bibtex" in command


def test_build_respects_shell_escape(tmp_path: Path, monkeypatch: Any) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><p>Body</p></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    template_dir = _template_path("book")

    def fake_which(name: str) -> str:
        assert name == "latexmk"
        return "/usr/bin/latexmk"

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> types.SimpleNamespace:
        calls.append(cmd)
        pdf_path = Path(kwargs["cwd"]) / "index.pdf"
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(build_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(build_cmd.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "build",
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert calls, "latexmk was not invoked"
    pdflatex_args = [arg for arg in calls[0] if arg.startswith("-pdflatex=")]
    assert pdflatex_args and "--shell-escape" in pdflatex_args[0]
