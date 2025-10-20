from pathlib import Path
import sys
import types
from typing import Any

from typer.testing import CliRunner

from mkdocs_latex.cli import app


def test_convert_command(tmp_path: Path) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><h2 id='intro'>Introduction</h2></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            "convert",
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--base-level",
            "0",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "\\section{Introduction}\\label{intro}" in result.stdout


def test_heading_level_option(tmp_path: Path) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><h2 id='intro'>Overview</h2></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            "convert",
            str(html_file),
            "--output-dir",
            str(output_dir),
            "-h",
            "1",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "\\subsection{Overview}\\label{intro}" in result.stdout


def test_copy_assets_disabled(tmp_path: Path) -> None:
    runner = CliRunner()
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<article class='md-content__inner'><img src='logo.png' alt='Logo'></article>",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            "convert",
            str(html_file),
            "--output-dir",
            str(output_dir),
            "--no-copy-assets",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Logo" in result.stdout
    assert "\\includegraphics" not in result.stdout


def test_convert_markdown_file(tmp_path: Path, monkeypatch: Any) -> None:
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
    markdown_file = tmp_path / "index.md"
    markdown_file.write_text("# Intro\n\nParagraph text.", encoding="utf-8")

    output_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "-h",
            "1",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "\\section{Intro}" in result.stdout
    assert "Paragraph text." in result.stdout


def test_markdown_extensions_normalization(
    tmp_path: Path, monkeypatch: Any
) -> None:
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
            "-e",
            "fenced_code, tables",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert recorded["extensions"] == ["fenced_code", "tables"]


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


def test_mdx_math_extension_preserves_latex(tmp_path: Path) -> None:
    runner = CliRunner()
    markdown_file = tmp_path / "math.md"
    markdown_file.write_text(
        "# Math\n\nInline $E = mc^2$ example.\n\n$$\n\\nabla \\cdot \\mathbf{E} = 0\n$$\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            "convert",
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "-e",
            "mdx_math",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "$E = mc^2$" in result.stdout
    assert result.stdout.count("$$") == 2
    assert "\\mathbf{E}" in result.stdout
    assert "\\textbackslash" not in result.stdout
