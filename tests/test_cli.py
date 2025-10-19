from pathlib import Path

from typer.testing import CliRunner

from latex.cli import app


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
