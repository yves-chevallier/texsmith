from __future__ import annotations

import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.config import BookConfig
from texsmith.core.context import DocumentState
from texsmith.index import TexsmithIndexExtension, register_renderer


markdown = pytest.importorskip("markdown")

EXTENSION = TexsmithIndexExtension()


@pytest.fixture
def renderer() -> LaTeXRenderer:
    renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")
    register_renderer(renderer)
    return renderer


def test_markdown_extension_generates_span() -> None:
    html = markdown.markdown("See #[Alpha]", extensions=[EXTENSION])
    assert 'class="ts-hashtag"' in html
    assert 'data-tag="Alpha"' in html


def test_markdown_extension_supports_hierarchy_and_style() -> None:
    html = markdown.markdown(
        "Use #[Matrices][Determinant][Formule]{bi}",
        extensions=[EXTENSION],
    )
    assert 'data-tag="Matrices"' in html
    assert 'data-tag1="Determinant"' in html
    assert 'data-tag2="Formule"' in html
    assert 'data-style="bi"' in html


def test_markdown_extension_extracts_registry_from_prefix() -> None:
    html = markdown.markdown(
        "Compare {index:physics}[relativity]",
        extensions=[EXTENSION],
    )
    assert 'data-registry="physics"' in html


def test_renderer_registers_index_entries(renderer: LaTeXRenderer) -> None:
    html = (
        '<p><span class="ts-hashtag" data-tag="Alpha" '
        'data-tag1="Beta" data-style="i">Alpha</span></p>'
    )
    state = DocumentState()
    latex = renderer.render(html, state=state)
    assert "Alpha\\index{Alpha!Beta@\\textit{Beta}}" in latex
    assert state.has_index_entries is True
    assert state.index_entries == [("Alpha", "Beta")]


def test_renderer_handles_three_levels(renderer: LaTeXRenderer) -> None:
    html = (
        '<p><span class="ts-hashtag" data-tag="Matrices" data-tag1="Determinant" '
        'data-tag2="Formula" data-style="bi">Matrices</span></p>'
    )
    latex = renderer.render(html)
    assert "Matrices\\index{Matrices!Determinant!Formula@\\textbf{\\textit{Formula}}}" in latex


def test_renderer_normalises_style(renderer: LaTeXRenderer) -> None:
    html = '<p><span class="ts-hashtag" data-tag="Gamma" data-style="ib">Gamma</span></p>'
    state = DocumentState()
    latex = renderer.render(html, state=state)
    assert "\\index{Gamma@\\textbf{\\textit{Gamma}}}" in latex
    assert state.index_entries == [("Gamma",)]
