from __future__ import annotations

from pathlib import Path

import markdown
import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.bibliography import BibliographyCollection
from texsmith.core.context import DocumentState
from texsmith.ui.cli import DEFAULT_MARKDOWN_EXTENSIONS


FIXTURE_BIB = Path(__file__).resolve().parent / "fixtures" / "bib" / "b.bib"
SAMPLE_DOI_BIB = "@article{KLEPPNER2005,title={Example},author={Doe, Jane},year={2024}}\n"
SAMPLE_DOI_BIB_TWO = "@article{SHPSB201112002,title={Another},author={Roe, John}}\n"


class _StaticFetcher:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping
        self.requests: list[str] = []

    def fetch(self, value: str) -> str:
        self.requests.append(value)
        return self.mapping[value]


def _render_markdown(
    source: str,
    bibliography: dict[str, dict[str, object]],
    runtime: dict[str, object] | None = None,
) -> tuple[str, DocumentState]:
    md = markdown.Markdown(extensions=DEFAULT_MARKDOWN_EXTENSIONS)
    html = md.convert(source)
    renderer = LaTeXRenderer(parser="html.parser")
    state = DocumentState(bibliography=dict(bibliography))
    runtime_payload: dict[str, object] = {"bibliography": bibliography}
    if runtime:
        runtime_payload.update(runtime)
    latex = renderer.render(html, runtime=runtime_payload, state=state)
    return latex, state


def _bibliography_from(files: list[Path]) -> dict[str, dict[str, object]]:
    collection = BibliographyCollection()
    collection.load_files(files)
    return collection.to_dict()


def test_missing_footnote_converts_to_citation() -> None:
    bibliography = _bibliography_from([FIXTURE_BIB])
    latex, state = _render_markdown("Cheese[^LAWRENCE19841632]", bibliography)

    assert "\\cite{LAWRENCE19841632}" in latex
    assert state.citations == ["LAWRENCE19841632"]


def test_defined_footnote_conflicts_with_bibliography() -> None:
    bibliography = _bibliography_from([FIXTURE_BIB])
    with pytest.warns(UserWarning, match="Conflicting bibliography definition"):
        latex, state = _render_markdown(
            "Cheese[^LAWRENCE19841632]\n\n[^LAWRENCE19841632]: custom note",
            bibliography,
        )

    assert "\\cite{LAWRENCE19841632}" in latex
    assert state.citations == ["LAWRENCE19841632"]


def test_missing_citation_without_bibliography_warns() -> None:
    with pytest.warns(UserWarning, match="Reference to 'unknown'"):
        latex, state = _render_markdown("Cheese[^unknown]", {})

    assert "unknown" in latex
    assert state.citations == []


def test_regular_footnote_still_rendered() -> None:
    latex, state = _render_markdown(
        "Cheese[^note]\n\n[^note]: contains details",
        {},
    )

    assert "\\footnote{" in latex
    assert "contains details" in latex
    assert state.citations == []


def test_multiple_citations_are_combined() -> None:
    bibliography = _bibliography_from([FIXTURE_BIB])
    latex, state = _render_markdown(
        "Both[^LAWRENCE19841632,BERESFORD2001259] references matter.",
        bibliography,
    )

    assert "\\cite{LAWRENCE19841632,BERESFORD2001259}" in latex
    assert state.citations == ["LAWRENCE19841632", "BERESFORD2001259"]


def test_doi_citation_fetches_bibliography_entry() -> None:
    fetcher = _StaticFetcher({"10.1063/1.1897520": SAMPLE_DOI_BIB})
    latex, state = _render_markdown(
        "Einstein^[10.1063/1.1897520]",
        {},
        runtime={"doi_fetcher": fetcher},
    )

    assert "\\cite{KLEPPNER2005}" in latex
    assert state.citations == ["KLEPPNER2005"]
    assert "KLEPPNER2005" in state.bibliography
    assert fetcher.requests == ["10.1063/1.1897520"]


def test_multiple_doi_citations_are_combined() -> None:
    fetcher = _StaticFetcher(
        {
            "10.1016/j.shpsb.2011.12.002": SAMPLE_DOI_BIB,
            "10.1007/978-94-007-2582-9_14": SAMPLE_DOI_BIB_TWO,
        }
    )
    latex, state = _render_markdown(
        "Refs^[10.1016/j.shpsb.2011.12.002,10.1007/978-94-007-2582-9_14]",
        {},
        runtime={"doi_fetcher": fetcher},
    )

    assert "\\cite{KLEPPNER2005,SHPSB201112002}" in latex
    assert state.citations == [
        "KLEPPNER2005",
        "SHPSB201112002",
    ]
    assert set(fetcher.requests) == {
        "10.1016/j.shpsb.2011.12.002",
        "10.1007/978-94-007-2582-9_14",
    }
