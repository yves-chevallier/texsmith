from pathlib import Path
import textwrap

from typer.testing import CliRunner
import yaml

from texsmith.ui.cli import app


FIXTURE_BIB_DIR = Path(__file__).resolve().parent / "fixtures" / "bib"


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def _template_path(name: str) -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "src" / "texsmith" / "templates" / name


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
    result = runner.invoke(app, ["--list-bibliography", str(bib_file)])

    assert result.exit_code == 0, result.stdout
    assert "Bibliography Files" in result.stdout
    assert "Entries" in result.stdout
    assert "sample (article)" in result.stdout
    assert "Sample Article" in result.stdout
    assert "John Example" in result.stdout
    assert "Sources" in result.stdout
    assert not result.stderr


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
    result = runner.invoke(app, ["--list-bibliography", str(original), str(conflicting)])

    assert result.exit_code == 0, result.stdout
    assert "Warnings" in result.stdout
    assert "Duplicate entry conflicts" in result.stdout
    assert "refkey (book)" in result.stdout
    assert "Original Title" in result.stdout
    assert "Different Title" not in result.stdout
    assert not result.stderr


def test_cli_bibliography_list_with_fixture_files() -> None:
    fixture_files = [
        FIXTURE_BIB_DIR / "a.bib",
        FIXTURE_BIB_DIR / "b.bib",
    ]

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["--list-bibliography", *(str(path) for path in fixture_files)],
    )

    assert result.exit_code == 0, result.stdout
    assert "Bibliography Files" in result.stdout
    assert "Warnings" in result.stdout
    assert "No references found in file." in result.stdout
    for filename in ("a.bib", "b.bib"):
        assert filename in result.stdout
    for key in ("LAWRENCE19841632", "BERESFORD2001259", "BEST20255106"):
        assert key in result.stdout
    assert not result.stderr


def test_cli_front_matter_bibliography_fetches_doi(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    class DummyFetcher:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def fetch(self, value: str) -> str:
            calls.append(value)
            return textwrap.dedent(
                """
                @article{any,
                    title = {Inline Demonstration},
                    author = {Doe, Jane},
                }
                """
            )

    monkeypatch.setattr("texsmith.core.conversion.templates.DoiBibliographyFetcher", DummyFetcher)

    markdown_file = _write(
        tmp_path,
        "paper.md",
        """
        ---
        bibliography:
          inline: https://doi.org/10.1038/146796a0
        ---

        Cheese[^inline]
        """,
    )

    template_dir = _template_path("article")
    output_dir = tmp_path / "out"
    runner = CliRunner()
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
    assert calls == ["https://doi.org/10.1038/146796a0"]

    tex_path = output_dir / "paper.tex"
    assert tex_path.exists()
    content = tex_path.read_text(encoding="utf-8")
    assert "\\cite{inline}" in content

    bibliography_file = output_dir / "texsmith-bibliography.bib"
    assert bibliography_file.exists()
    bibliography_payload = bibliography_file.read_text(encoding="utf-8")
    assert "@article{inline" in bibliography_payload
    assert "Inline Demonstration" in bibliography_payload


def test_cli_front_matter_bibliography_uses_output_cache(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    class DummyFetcher:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def fetch(self, value: str) -> str:
            calls.append(value)
            return textwrap.dedent(
                """
                @article{any,
                    title = {Inline Demonstration},
                    author = {Doe, Jane},
                }
                """
            )

    monkeypatch.setattr("texsmith.core.conversion.templates.DoiBibliographyFetcher", DummyFetcher)

    markdown_file = _write(
        tmp_path,
        "paper.md",
        """
        ---
        bibliography:
          inline: https://doi.org/10.1038/146796a0
        ---

        Cheese[^inline]
        """,
    )

    template_dir = _template_path("article")
    output_dir = tmp_path / "out"
    runner = CliRunner()

    result_first = runner.invoke(
        app,
        [
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
        ],
    )
    assert result_first.exit_code == 0, result_first.stderr
    assert calls == ["https://doi.org/10.1038/146796a0"]

    cache_path = output_dir / "texsmith-doi-cache.yaml"
    assert cache_path.exists()
    cache_payload = yaml.safe_load(cache_path.read_text(encoding="utf-8"))
    assert isinstance(cache_payload, dict)
    entries = cache_payload.get("entries") if isinstance(cache_payload, dict) else None
    if isinstance(entries, dict):
        assert "10.1038/146796a0" in entries

    result_second = runner.invoke(
        app,
        [
            str(markdown_file),
            "--output-dir",
            str(output_dir),
            "--template",
            str(template_dir),
        ],
    )
    assert result_second.exit_code == 0, result_second.stderr
    assert calls == ["https://doi.org/10.1038/146796a0"]
