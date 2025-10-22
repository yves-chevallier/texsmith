from __future__ import annotations

from pathlib import Path

import markdown
import pytest

from texsmith.bibliography import BibliographyCollection
from texsmith.cli import DEFAULT_MARKDOWN_EXTENSIONS
from texsmith.context import DocumentState
from texsmith.renderer import LaTeXRenderer


FIXTURE_BIB = Path(__file__).resolve().parent / "fixtures" / "bib" / "b.bib"


def _render_markdown(source: str, bibliography: dict[str, dict[str, object]]) -> tuple[str, DocumentState]:
    md = markdown.Markdown(extensions=DEFAULT_MARKDOWN_EXTENSIONS)
    html = md.convert(source)
    renderer = LaTeXRenderer(parser="html.parser")
    state = DocumentState(bibliography=dict(bibliography))
    latex = renderer.render(html, runtime={"bibliography": bibliography}, state=state)
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
