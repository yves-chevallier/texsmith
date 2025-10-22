from pathlib import Path
import textwrap

from typer.testing import CliRunner

from texsmith.cli import app


FIXTURE_BIB_DIR = Path(__file__).resolve().parent / "fixtures" / "bib"


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def test_cli_bibliography_list_outputs_entries(tmp_path: Path) -> None:
    bib_file = _write(
        tmp_path,
        "library.bib",
        """
        @article{sample,
            title = {Sample Article},
            author = {John Example},
            year = {2023},
        }
        """,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["bibliography", "list", str(bib_file)])

    assert result.exit_code == 0, result.stdout
    assert "Bibliography Files" in result.stdout
    assert "Entries" in result.stdout
    assert "sample (article)" in result.stdout
    assert "Sample Article" in result.stdout
    assert "John Example" in result.stdout
    assert "Sources" in result.stdout
    assert result.stderr == ""


def test_cli_bibliography_list_reports_conflicts(tmp_path: Path) -> None:
    original = _write(
        tmp_path,
        "one.bib",
        """
        @book{refkey,
            title = {Original Title},
            author = {Author, Primary},
        }
        """,
    )
    conflicting = _write(
        tmp_path,
        "two.bib",
        """
        @book{refkey,
            title = {Different Title},
            author = {Author, Primary},
        }
        """,
    )

    runner = CliRunner()
    result = runner.invoke(
        app, ["bibliography", "list", str(original), str(conflicting)]
    )

    assert result.exit_code == 0, result.stdout
    assert "Warnings" in result.stdout
    assert "Duplicate entry conflicts" in result.stdout
    assert "refkey (book)" in result.stdout
    assert "Original Title" in result.stdout
    assert "Different Title" not in result.stdout
    assert result.stderr == ""


def test_cli_bibliography_list_with_fixture_files() -> None:
    fixture_files = [
        FIXTURE_BIB_DIR / "a.bib",
        FIXTURE_BIB_DIR / "b.bib",
    ]

    runner = CliRunner()
    result = runner.invoke(
        app, ["bibliography", "list", *(str(path) for path in fixture_files)]
    )

    assert result.exit_code == 0, result.stdout
    assert "Bibliography Files" in result.stdout
    assert "Warnings" in result.stdout
    assert "No references found in file." in result.stdout
    for filename in ("a.bib", "b.bib"):
        assert filename in result.stdout
    for key in ("LAWRENCE19841632", "BERESFORD2001259", "BEST20255106"):
        assert key in result.stdout
    assert result.stderr == ""
