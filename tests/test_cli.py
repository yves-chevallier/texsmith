import importlib
from pathlib import Path
import sys
import types
from typing import Any

import click
import pytest
import typer
from typer.testing import CliRunner

from texsmith.adapters.latex import engines as engine
from texsmith.adapters.latex.engines import LatexMessage, LatexMessageSeverity
from texsmith.core.conversion.debug import ConversionError, raise_conversion_error
from texsmith.ui.cli import DEFAULT_MARKDOWN_EXTENSIONS, app
from texsmith.ui.cli.commands import render as render_cmd
import texsmith.ui.cli.state as cli_state


render_module = importlib.import_module("texsmith.ui.cli.commands.render")


def _template_path(name: str) -> Path:
    project_root = Path(__file__).resolve().parents[1]
    local_candidate = project_root / "templates" / name
    if local_candidate.exists():
        return local_candidate

    builtin_candidate = project_root / "src" / "texsmith" / "templates" / name
    if builtin_candidate.exists():
        return builtin_candidate

    raise AssertionError(f"Template '{name}' is not available in tests")


def _stub_tectonic_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    binary = tmp_path / "tectonic"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    selection = types.SimpleNamespace(path=binary, source="bundled")
    biber = tmp_path / "biber"
    biber.write_text("#!/bin/sh\n", encoding="utf-8")
    biber.chmod(0o755)

    def fake_select_tectonic(_use_system: bool, console=None):
        _ = console
        return selection

    def fake_select_biber(console=None):
        _ = console
        return biber

    monkeypatch.setattr(render_module, "select_tectonic_binary", fake_select_tectonic)
    monkeypatch.setattr(render_module, "select_biber_binary", fake_select_biber)
    return binary


def test_raise_conversion_error_marks_exception_logged() -> None:
    class DummyEmitter:
        def __init__(self) -> None:
            self.messages: list[tuple[str, Exception]] = []

        def error(self, message: str, exc: Exception) -> None:
            self.messages.append((message, exc))

    emitter = DummyEmitter()
    with pytest.raises(ConversionError) as excinfo:
        raise_conversion_error(emitter, "failed", ValueError("boom"))

    assert getattr(excinfo.value, "_texsmith_logged", False) is True
    assert emitter.messages and emitter.messages[0][0] == "failed"


def test_emit_error_skips_logged_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, str, BaseException | None]] = []

    def fake_render(level: str, message: str, *, exception: BaseException | None = None) -> None:
        captured.append((level, message, exception))

    monkeypatch.setattr(cli_state, "render_message", fake_render)

    logged_exc = Exception("already logged")
    logged_exc._texsmith_logged = True
    cli_state.emit_error("first", exception=logged_exc)
    assert captured == []

    fresh_exc = Exception("new")
    cli_state.emit_error("second", exception=fresh_exc)
    assert captured == [("error", "second", fresh_exc)]


def test_convert_command() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        html_file = Path("index.html")
        html_file.write_text(
            (
                "<article class='md-content__inner'>"
                "<h2 id='intro'>Introduction</h2>"
                "<p>Body text.</p>"
                "</article>"
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                str(html_file),
                "--base-level",
                "0",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "\\chapter{Introduction}\\label{intro}" in result.stdout


def test_fonts_info_flag_displays_script_table() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        html_file = Path("index.html")
        html_file.write_text(
            (
                "<article class='md-content__inner'>"
                "<h2 id='intro'>Tibetan (བོད་ ཡིག Bengali বাংলা)</h2>"
                "</article>"
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                str(html_file),
                "--base-level",
                "0",
                "--template",
                "article",
                "--fonts-info",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "Fallback Fonts" in result.stdout
    assert "tibetan" in result.stdout.lower()
    assert "bengali" in result.stdout.lower()
    assert "[4]" in result.stdout or "Codepoints" in result.stdout


def test_template_alignment_defaults_to_section() -> None:
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
                str(html_file),
                "--template",
                "article",
                "--output",
                "build",
                "--no-promote-title",
            ],
        )

        output_file = Path("build") / "index.tex"
        assert output_file.exists(), result.stdout
        content = output_file.read_text(encoding="utf-8")

    assert result.exit_code == 0, result.stdout
    assert "\\section{Introduction}\\label{intro}" in content
    assert "\\title" not in content


def test_strip_heading_option() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        html_file = Path("index.html")
        html_file.write_text(
            "<article class='md-content__inner'><h1>Main</h1><h2 id='body'>Body</h2></article>",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                str(html_file),
                "--strip-heading",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "Main" not in result.stdout
    assert "\\section{Body}\\label{body}" in result.stdout


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
                str(markdown_file),
                "--base-level",
                "section",
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "\\section{Intro}" in result.stdout
    assert "Paragraph text." in result.stdout


def test_render_from_stdin(monkeypatch: Any) -> None:
    class DummyMarkdown:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def convert(self, text: str) -> str:
            return "<h1>Hello</h1>" if "# Title" in text else "<p>Body</p>"

    monkeypatch.setitem(sys.modules, "markdown", types.SimpleNamespace(Markdown=DummyMarkdown))

    runner = CliRunner()
    result = runner.invoke(
        app,
        [],
        input="# Title\n\nSome **bold** text.\n",
    )

    assert result.exit_code == 0, result.stdout
    assert "\\section{Hello}" in result.stdout


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
                str(markdown_file),
                "--enable-extension",
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
            str(markdown_file),
            "--output-dir",
            str(tmp_path / "output"),
            "--disable-extension",
            "footnotes, pymdownx.details",
            "-X",
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

        result = runner.invoke(app, [str(first), str(second)])

    assert result.exit_code == 0, result.stdout
    assert "\\section{First}" in result.stdout
    assert "\\section{Second}" in result.stdout
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
            str(first),
            str(second),
            "--output",
            str(output_file),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "\\section{Chapter One}" in content
    assert "\\section{Chapter Two}" in content
    assert content.index("Chapter One") < content.index("Chapter Two")


def test_slot_injection_extracts_abstract(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        "## Abstract\n\nThis is the abstract.\n\n## Introduction\n\nBody text.",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[1]
    template_dir = project_root / "src" / "texsmith" / "templates" / "article"
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
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
    assert "\\begin{abstract}" in content
    assert "This is the abstract." in content
    assert "\\subsection{Abstract}" not in content


def test_slot_injection_matches_label(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        "## Abstract {#absSection}\n\nLabel abstract.\n\n## Body\n\nContent.",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[1]
    template_dir = project_root / "src" / "texsmith" / "templates" / "article"
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
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
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--slot",
            "unknown:Abstract",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert "slot 'unknown' is not defined" in result.stderr.lower()
    tex_path = output_dir / "paper.tex"
    assert tex_path.exists()
    content = tex_path.read_text(encoding="utf-8")
    assert "Content." in content


def test_slot_injection_preserves_footnotes(tmp_path: Path) -> None:
    runner = CliRunner()
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "examples/paper/cheese.md",
            "examples/paper/cheese.bib",
            "--output-dir",
            str(output_dir),
            "--template",
            "article",
            "--slot",
            "abstract:Abstract",
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
press:
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

    template_dir = _template_path("article")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
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
    assert "\\begin{abstract}" in content
    assert "Front matter abstract." in content
    assert "\\subsection{Abstract}" not in content


def test_front_matter_slots_top_level_mapping(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        """---
slots:
  abstract: Abstract
press:
  title: Demo
---
## Abstract

Front matter abstract.

## Body

Main discussion.
""",
        encoding="utf-8",
    )

    template_dir = _template_path("article")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
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
    assert "\\begin{abstract}" in content
    assert "Front matter abstract." in content


def test_promoted_title_keeps_section_depth_for_slots(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        """---
press:
  subtitle: Subtitle
  slots:
    abstract: Abstract
---
# Title

## Abstract

abstract

## Section

section
""",
        encoding="utf-8",
    )

    template_dir = _template_path("article")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
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
    assert "\\begin{abstract}" in content
    assert "abstract" in content
    assert "\\section{Section}" in content
    assert "\\subsection{Section}" not in content


def test_cli_slot_overrides_front_matter(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "paper.md"
    markdown_file.write_text(
        """---
press:
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

    template_dir = _template_path("article")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
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
            str(chapter1),
            str(chapter2),
            "--template",
            str(template_dir),
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.stderr
    main_file = output_dir / "main.tex"
    assert main_file.exists()
    content = main_file.read_text(encoding="utf-8")
    assert "\\input{chapter1.tex}" in content
    assert "\\input{chapter2.tex}" in content


def test_convert_template_outputs_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><h2>Intro</h2></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    template_dir = _template_path("article")

    result = runner.invoke(
        app,
        [
            str(html_file),
            "--template",
            str(template_dir),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Template Conversion Summary" not in result.stdout
    assert "Main document" in result.stdout


def test_convert_template_outputs_debug_html(tmp_path: Path) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><h2>Intro</h2></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    template_dir = _template_path("article")

    result = runner.invoke(
        app,
        [
            str(html_file),
            "--template",
            str(template_dir),
            "--output-dir",
            str(output_dir),
            "--debug-html",
        ],
    )

    assert result.exit_code == 0, result.stdout
    debug_file = output_dir / "index.debug.html"
    assert debug_file.exists()
    assert "Debug HTML" in result.stdout
    assert str(debug_file) in result.stdout


def test_slot_assignment_targets_specific_file(tmp_path: Path) -> None:
    runner = CliRunner()
    abstract_doc = tmp_path / "abstract.md"
    abstract_doc.write_text("# Abstract\n\nSummary.", encoding="utf-8")
    body_doc = tmp_path / "body.md"
    body_doc.write_text("# Body\n\nContent.", encoding="utf-8")

    template_dir = _template_path("article")
    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
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
    main_file = output_dir / "main.tex"
    assert main_file.exists()
    content = main_file.read_text(encoding="utf-8")
    assert "\\input{abstract.tex}" in content
    assert "\\input{body.tex}" in content
    assert "Summary." in (output_dir / "abstract.tex").read_text(encoding="utf-8")
    assert "Content." in (output_dir / "body.tex").read_text(encoding="utf-8")


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
    main_file = output_dir / "main.tex"
    content = main_file.read_text(encoding="utf-8")
    assert "\\input{chapter2.backmatter.tex}" in content
    appendix_file = output_dir / "chapter2.backmatter.tex"
    assert "Appendix content." in appendix_file.read_text(encoding="utf-8")


def test_convert_verbose_emits_extension_diagnostics(tmp_path: Path) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><p>Body</p></article>",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--verbose",
            str(html_file),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Extensions:" in result.stdout


def test_convert_verbose_template_reports_overrides(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "chapter.md"
    markdown_file.write_text("# Heading\n\nBody", encoding="utf-8")
    output_dir = tmp_path / "build"
    template_dir = _template_path("article")

    result = runner.invoke(
        app,
        [
            "--verbose",
            "--verbose",
            str(markdown_file),
            "--template",
            str(template_dir),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Template overrides:" in result.stdout
    assert "Settings:" in result.stdout


def test_build_without_template_defaults_to_article(tmp_path: Path, monkeypatch: Any) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><h2>Title</h2></article>",
        encoding="utf-8",
    )

    _stub_tectonic_binary(monkeypatch, tmp_path)

    def fake_which(name: str) -> str:
        return name if str(name).startswith("/") else f"/usr/bin/{name}"

    def fake_run(command: Any, **kwargs: Any) -> engine.EngineResult:
        pdf_path = command.pdf_path
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return engine.EngineResult(
            returncode=0,
            messages=[],
            command=command.argv,
            log_path=command.log_path,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(render_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(engine.shutil, "which", fake_which)
    monkeypatch.setattr(render_cmd, "run_engine_command", fake_run)

    result = runner.invoke(
        app,
        [
            str(html_file),
            "--output-dir",
            str(tmp_path / "output"),
            "--build",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Running tectonic" in result.stdout


def test_build_defaults_to_rich_output(tmp_path: Path, monkeypatch: Any) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><p>Body</p></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    template_dir = _template_path("article")

    captured: dict[str, Any] = {}

    tectonic_path = _stub_tectonic_binary(monkeypatch, tmp_path)

    def fake_which(name: str) -> str:
        return name if str(name).startswith("/") else f"/usr/bin/{name}"

    def fake_run_engine(command: Any, **kwargs: Any) -> engine.EngineResult:
        captured["command"] = command.argv
        captured["cwd"] = kwargs.get("workdir")
        captured["env"] = kwargs.get("env")
        captured["console"] = kwargs.get("console")
        captured["verbosity"] = kwargs.get("verbosity")
        captured["classic"] = kwargs.get("classic_output")
        pdf_path = command.pdf_path
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return engine.EngineResult(
            returncode=0,
            messages=[],
            command=command.argv,
            log_path=command.log_path,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(render_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(engine.shutil, "which", fake_which)
    monkeypatch.setattr(render_cmd, "run_engine_command", fake_run_engine)

    result = runner.invoke(
        app,
        [
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--build",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured, "stream_latexmk_output was not called"
    assert captured["command"][0] == str(tectonic_path)
    assert captured["cwd"] == output_dir
    assert captured["console"] is not None
    assert captured["verbosity"] == 0
    assert captured["classic"] is False
    assert "Running tectonic…" in result.stdout


def test_system_flag_prefers_system_tectonic(tmp_path: Path, monkeypatch: Any) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><p>Body</p></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    template_dir = _template_path("article")
    system_flag: dict[str, Any] = {}
    captured: dict[str, Any] = {}

    def fake_select(use_system: bool, console: Any = None) -> Any:
        system_flag["use_system"] = use_system
        return types.SimpleNamespace(path=Path("/opt/tectonic/system"), source="system")

    def fake_which(name: str) -> str:
        return name if str(name).startswith("/") else f"/usr/bin/{name}"

    def fake_run_engine(command: Any, **kwargs: Any) -> engine.EngineResult:
        captured["command"] = command.argv
        pdf_path = command.pdf_path
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return engine.EngineResult(
            returncode=0,
            messages=[],
            command=command.argv,
            log_path=command.log_path,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(render_module, "select_tectonic_binary", fake_select)
    monkeypatch.setattr(render_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(engine.shutil, "which", fake_which)
    monkeypatch.setattr(render_cmd, "run_engine_command", fake_run_engine)

    result = runner.invoke(
        app,
        [
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--build",
            "--system",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert system_flag["use_system"] is True
    assert captured["command"][0] == "/opt/tectonic/system"


def test_build_supports_multiple_documents(tmp_path: Path, monkeypatch: Any) -> None:
    runner = CliRunner()
    chapter1 = tmp_path / "chapter1.md"
    chapter1.write_text("# One\n\nBody.", encoding="utf-8")
    chapter2 = tmp_path / "chapter2.md"
    chapter2.write_text("# Two\n\nMore.", encoding="utf-8")

    output_dir = tmp_path / "output"
    template_dir = _template_path("article")

    captured: dict[str, Any] = {}

    tectonic_path = _stub_tectonic_binary(monkeypatch, tmp_path)

    def fake_which(name: str) -> str:
        return name if str(name).startswith("/") else f"/usr/bin/{name}"

    def fake_run_engine(command: Any, **kwargs: Any) -> engine.EngineResult:
        captured["command"] = command.argv
        captured["cwd"] = kwargs.get("workdir")
        captured["env"] = kwargs.get("env")
        pdf_path = command.pdf_path
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return engine.EngineResult(
            returncode=0,
            messages=[],
            command=command.argv,
            log_path=command.log_path,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(render_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(engine.shutil, "which", fake_which)
    monkeypatch.setattr(render_cmd, "run_engine_command", fake_run_engine)

    result = runner.invoke(
        app,
        [
            str(chapter1),
            str(chapter2),
            "--template",
            str(template_dir),
            "--output",
            str(output_dir),
            "--build",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["cwd"] == output_dir
    assert captured["command"][0] == str(tectonic_path)
    main_file = output_dir / "main.tex"
    assert main_file.exists()


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
        return f"/usr/bin/{name}"

    def fake_run(command: Any, **kwargs: Any) -> engine.EngineResult:
        calls.append((command.argv, kwargs))
        pdf_path = command.pdf_path
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return engine.EngineResult(
            returncode=0,
            messages=[],
            command=command.argv,
            log_path=command.log_path,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(render_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(engine.shutil, "which", fake_which)
    monkeypatch.setattr(render_cmd, "run_engine_command", fake_run)

    result = runner.invoke(
        app,
        [
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--classic-output",
            "--build",
            "--engine",
            "lualatex",
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
    assert "--shell-escape" not in pdflatex_args[0]
    assert command[-1] == "index.tex"
    assert kwargs["workdir"] == output_dir
    assert "Build Outputs" not in result.stdout
    assert "Main document" in result.stdout
    assert "PDF" in result.stdout


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
        return f"/usr/bin/{name}"

    def fake_run(command: Any, **kwargs: Any) -> engine.EngineResult:
        calls.append((command.argv, kwargs))
        pdf_path = command.pdf_path
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return engine.EngineResult(
            returncode=0,
            messages=[],
            command=command.argv,
            log_path=command.log_path,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(render_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(engine.shutil, "which", fake_which)
    monkeypatch.setattr(render_cmd, "run_engine_command", fake_run)

    result = runner.invoke(
        app,
        [
            str(html_file),
            str(bib_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--classic-output",
            "--build",
            "--engine",
            "lualatex",
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
        return f"/usr/bin/{name}"

    calls: list[list[str]] = []

    def fake_run(command: Any, **kwargs: Any) -> engine.EngineResult:
        calls.append(command.argv)
        pdf_path = command.pdf_path
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("%PDF-1.4", encoding="utf-8")
        return engine.EngineResult(
            returncode=0,
            messages=[],
            command=command.argv,
            log_path=command.log_path,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(render_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(engine.shutil, "which", fake_which)
    monkeypatch.setattr(render_cmd, "run_engine_command", fake_run)

    result = runner.invoke(
        app,
        [
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--classic-output",
            "--build",
            "--engine",
            "lualatex",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert calls, "latexmk was not invoked"
    pdflatex_args = [arg for arg in calls[0] if arg.startswith("-pdflatex=")]
    assert pdflatex_args
    assert "--shell-escape" not in pdflatex_args[0]


def test_build_failure_reports_summary(tmp_path: Path, monkeypatch: Any) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><p>Body</p></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    template_dir = _template_path("article")

    _stub_tectonic_binary(monkeypatch, tmp_path)

    def fake_which(name: str) -> str:
        return f"/usr/bin/{name}"

    def fake_run(command: Any, **kwargs: Any) -> engine.EngineResult:
        log_path = command.log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("! Undefined control sequence.\nl.42 \\unknowncmd\n", encoding="utf-8")
        message = LatexMessage(
            severity=LatexMessageSeverity.ERROR,
            summary="! Undefined control sequence.",
            details=["l.42 \\unknowncmd"],
        )
        return engine.EngineResult(
            returncode=1,
            messages=[message],
            command=command.argv,
            log_path=log_path,
            pdf_path=command.pdf_path,
        )

    monkeypatch.setattr(render_cmd.shutil, "which", fake_which)
    monkeypatch.setattr(engine.shutil, "which", fake_which)
    monkeypatch.setattr(render_cmd, "run_engine_command", fake_run)

    result = runner.invoke(
        app,
        [
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
            "--build",
        ],
    )

    assert result.exit_code == 1
    assert "LaTeX failure" in result.stderr
    assert "Undefined control sequence" in result.stderr
    assert "index.log" in result.stderr


def test_html_output_with_template_metadata(tmp_path: Path) -> None:
    runner = CliRunner()
    doc = tmp_path / "doc.md"
    doc.write_text(
        "---\npress:\n  template: article\n---\n# Title\n\nBody\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, [str(doc), "--html"])

    output_file = tmp_path / "build" / "doc.html"
    assert result.exit_code == 0, result.stdout
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "<h1" in content and "Title" in content


def test_cli_state_per_context_isolated() -> None:
    command = click.Command("dummy")
    ctx_a = typer.Context(command)
    ctx_b = typer.Context(command)

    state_a = cli_state.get_cli_state(ctx_a)
    state_a.verbosity = 5

    state_b = cli_state.get_cli_state(ctx_b)
    assert state_b.verbosity == 0

    state_b.verbosity = 2
    # ensure fallback reflects most recent context state without mutating the first one
    assert cli_state.get_cli_state(ctx_b).verbosity == 2
    assert cli_state.get_cli_state(ctx_a).verbosity == 5
