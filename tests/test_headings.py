import pytest

from texsmith.config import BookConfig
from texsmith.context import DocumentState
from texsmith.renderer import LaTeXRenderer


@pytest.fixture
def renderer() -> LaTeXRenderer:
    return LaTeXRenderer(config=BookConfig(), parser="html.parser")


def test_basic_heading_rendering(renderer: LaTeXRenderer) -> None:
    html = "<h2 id='intro'>Introduction</h2>"
    state = DocumentState()
    latex = renderer.render(
        html,
        runtime={"base_level": 0},
        state=state,
    )
    assert "\\section{Introduction}\\label{intro}" in latex
    assert state.headings == [{"level": 1, "text": "Introduction", "ref": "intro"}]


def test_inline_formatting_preserved(renderer: LaTeXRenderer) -> None:
    html = "<h3 id='intro'>Intro <strong>Bold</strong></h3>"
    latex = renderer.render(html, runtime={"base_level": 0})
    assert "\\subsection{Intro \\textbf{Bold}}\\label{intro}" in latex


def test_heading_with_nested_formatting(renderer: LaTeXRenderer) -> None:
    html = "<h2 id='mix'>Title <strong>and <em>mix</em></strong></h2>"
    latex = renderer.render(html, runtime={"base_level": 0})
    assert "\\section{Title \\textbf{and \\emph{mix}}}\\label{mix}" in latex


def test_drop_title_runtime_flag(renderer: LaTeXRenderer) -> None:
    html = "<h1>Main Title</h1><h2>Subsection</h2>"
    state = DocumentState()
    latex = renderer.render(
        html,
        runtime={"base_level": 0, "drop_title": True},
        state=state,
    )
    assert "\\chapter{Main Title}" not in latex
    assert "\\thispagestyle{plain}" in latex
    assert "\\section{Subsection}" in latex
    assert state.headings == [{"level": 1, "text": "Subsection", "ref": None}]
