from pathlib import Path
import textwrap

from texsmith.bibliography import BibliographyCollection


def _write(
    tmp_path: Path,
    filename: str,
    payload: str,
) -> Path:
    file_path = tmp_path / filename
    file_path.write_text(textwrap.dedent(payload).strip() + "\n", encoding="utf-8")
    return file_path


def test_bibliography_collection_loads_multiple_files(tmp_path: Path) -> None:
    file_one = _write(
        tmp_path,
        "first.bib",
        """
        @article{smith2020,
            title = {Example Article},
            author = {Smith, John},
            year = {2020},
            journal = {Journal of Testing},
        }
        """,
    )

    file_two = _write(
        tmp_path,
        "second.bib",
        """
        @book{doe2021,
            title = {Example Book},
            author = {Doe, Jane},
            year = {2021},
            publisher = {Publishing House},
        }
        """,
    )

    collection = BibliographyCollection()
    collection.load_files([file_one, file_two])

    assert collection.find("smith2020") is not None
    assert collection.find("doe2021") is not None

    smith = collection.find("smith2020")
    assert smith is not None
    assert smith["fields"]["title"] == "Example Article"
    assert smith["persons"]["author"][0]["last"] == ["Smith"]

    references = collection.list_references()
    assert {reference["key"] for reference in references} == {"doe2021", "smith2020"}
    stats = collection.file_stats
    assert stats == (
        (file_one.resolve(), 1),
        (file_two.resolve(), 1),
    )
    assert not collection.issues


def test_bibliography_collection_reports_conflicting_duplicates(
    tmp_path: Path,
) -> None:
    primary = _write(
        tmp_path,
        "primary.bib",
        """
        @article{duplicate,
            title = {Original Title},
            author = {Alpha, Alice},
        }
        """,
    )

    conflicting = _write(
        tmp_path,
        "conflicting.bib",
        """
        @article{duplicate,
            title = {Updated Title},
            author = {Alpha, Alice},
        }
        """,
    )

    collection = BibliographyCollection()
    collection.load_files([primary, conflicting])

    assert len(collection.list_references()) == 1
    assert collection.find("duplicate") is not None

    issues = collection.issues
    assert issues, "Expected duplicate conflict to produce an issue."
    first_issue = issues[0]
    assert first_issue.key == "duplicate"
    assert "conflicts" in first_issue.message
    assert first_issue.source == conflicting


def test_bibliography_collection_reports_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.bib"
    empty.write_text("\n", encoding="utf-8")

    collection = BibliographyCollection()
    collection.load_files([empty])

    stats = collection.file_stats
    assert stats == ((empty.resolve(), 0),)
    assert not collection.list_references()
    assert any("No references found" in issue.message for issue in collection.issues)
