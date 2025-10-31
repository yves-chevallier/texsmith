from datetime import date
from pathlib import Path
import textwrap

import pytest
import requests

from texsmith.core.bibliography import (
    BibliographyCollection,
    DoiBibliographyFetcher,
    DoiLookupError,
    bibliography_data_from_string,
)
from texsmith.core.conversion import extract_front_matter_bibliography
from texsmith.core.conversion.inputs import (
    InlineBibliographyEntry,
    InlineBibliographyValidationError,
)
from texsmith.core.conversion.templates import _load_inline_bibliography
from texsmith.core.diagnostics import NullEmitter


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


def test_bibliography_collection_load_data_merges_inline_entries(tmp_path: Path) -> None:
    collection = BibliographyCollection()
    payload = """
    @article{ignored,
        title = {Inline Source},
        author = {Inline, Donna},
    }
    """
    data = bibliography_data_from_string(payload, "frontref")
    collection.load_data(data, source="frontmatter-inline.bib")

    entry = collection.find("frontref")
    assert entry is not None
    assert entry["fields"]["title"] == "Inline Source"
    stats = collection.file_stats
    assert stats == ((Path("frontmatter-inline.bib"), 1),)


def test_doi_bibliography_fetcher_uses_fallbacks() -> None:
    class FakeResponse:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

    class FakeSession:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get(self, url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
            self.calls.append(url)
            if url.startswith("https://doi.org/"):
                return FakeResponse(404, "")
            if url.startswith("https://dx.doi.org/"):
                raise requests.RequestException("temporary failure")
            return FakeResponse(
                200,
                """
                @article{demo,
                    title = {Demo Reference},
                }
                """,
            )

    fetcher = DoiBibliographyFetcher(session=FakeSession(), timeout=0.1)
    payload = fetcher.fetch("https://doi.org/10.1000/demo")

    assert "Demo Reference" in payload
    assert fetcher._session.calls[0].startswith("https://doi.org/10.1000/demo")
    assert fetcher._session.calls[1].startswith("https://dx.doi.org/10.1000/demo")
    assert fetcher._session.calls[2].startswith("https://api.crossref.org/works/10.1000/demo")

    with pytest.raises(DoiLookupError):
        fetcher.fetch("")


def test_extract_front_matter_bibliography_merges_sections() -> None:
    front_matter = {
        "press": {
            "bibliography": {
                "alpha": "https://doi.org/10.1/foo",
            },
        },
        "bibliography": {
            "beta": {"doi": "10.2/bar"},
            "alpha": "doi:10.3/baz",
        },
    }

    result = extract_front_matter_bibliography(front_matter)

    assert set(result) == {"alpha", "beta"}
    assert isinstance(result["alpha"], InlineBibliographyEntry)
    assert result["alpha"].doi == "doi:10.3/baz"
    assert result["beta"].doi == "10.2/bar"


def test_extract_front_matter_bibliography_manual_entry() -> None:
    front_matter = {
        "bibliography": {
            "CHE2025": {
                "type": "misc",
                "title": "Quiz-AI Automated Grading Pipeline",
                "author": "Yves Chevallier",
                "date": date(2025, 10, 20),
                "url": "https://github.com/yves-chevallier/quiz-ai",
            }
        }
    }

    result = extract_front_matter_bibliography(front_matter)

    assert set(result) == {"CHE2025"}
    entry = result["CHE2025"]
    assert entry.entry_type == "misc"
    assert entry.fields["title"] == "Quiz-AI Automated Grading Pipeline"
    assert entry.fields["url"] == "https://github.com/yves-chevallier/quiz-ai"
    assert entry.fields["year"] == "2025"
    assert entry.fields["month"] == "10"
    assert entry.fields["day"] == "20"
    assert entry.persons["author"] == ["Yves Chevallier"]


def test_extract_front_matter_bibliography_rejects_unknown_fields() -> None:
    front_matter = {
        "bibliography": {
            "INVALID": {
                "type": "misc",
                "title": "Missing Fields",
                "foo": "bar",
            }
        }
    }

    with pytest.raises(InlineBibliographyValidationError, match="unsupported field"):
        extract_front_matter_bibliography(front_matter)


def test_inline_manual_bibliography_merged_into_collection() -> None:
    front_matter = {
        "bibliography": {
            "AI2027": {
                "type": "misc",
                "title": "AI 2027 Forecast",
                "authors": ["Daniel Kokotajlo", "Scott Alexander"],
                "date": date(2025, 4, 3),
                "url": "https://example.com/ai-2027.pdf",
            }
        }
    }
    entries = extract_front_matter_bibliography(front_matter)

    collection = BibliographyCollection()
    _load_inline_bibliography(
        collection,
        entries,
        source_label="ai2027",
        emitter=NullEmitter(),
    )

    stored = collection.find("AI2027")
    assert stored is not None
    assert stored["fields"]["title"] == "AI 2027 Forecast"
    assert stored["fields"]["year"] == "2025"
    assert stored["fields"]["month"] == "04"
    assert stored["persons"]["author"][0]["last"] == ["Kokotajlo"]
    assert stored["persons"]["author"][1]["last"] == ["Alexander"]


def test_bibliography_collection_sanitizes_html_markup() -> None:
    collection = BibliographyCollection()
    payload = """
    @article{kofinas2025,
        title = {The impact of generative <scp>AI</scp> on academic integrity},
        year = {2025},
    }
    """
    data = bibliography_data_from_string(payload, "kofinas2025")
    collection.load_data(data, source="frontmatter-inline.bib")

    entry = collection.find("kofinas2025")
    assert entry is not None
    title = entry["fields"]["title"]
    assert "<" not in title and ">" not in title
    assert "AI" in title


def test_bibliography_writer_preserves_url_underscores(tmp_path: Path) -> None:
    front_matter = {
        "bibliography": {
            "HEIGPR": {
                "type": "misc",
                "title": "Principes",
                "url": "https://intra.heig-vd.ch/academique/documents_ia/IA_principes.pdf",
            }
        }
    }

    entries = extract_front_matter_bibliography(front_matter)
    collection = BibliographyCollection()
    _load_inline_bibliography(
        collection,
        entries,
        source_label="inline",
        emitter=NullEmitter(),
    )

    bib_path = tmp_path / "inline.bib"
    collection.write_bibtex(bib_path)

    contents = bib_path.read_text(encoding="utf-8")
    assert "\\_" not in contents
    assert "documents_ia" in contents
