import pytest

from texsmith.config import BookConfig
from texsmith.context import DocumentState
from texsmith.renderer import LaTeXRenderer


@pytest.fixture
def renderer() -> LaTeXRenderer:
    return LaTeXRenderer(config=BookConfig(), parser="html.parser")


def test_fill_in_the_blank_solution_capture(renderer: LaTeXRenderer) -> None:
    from texsmith.plugins import material

    material.register(renderer)
    html = """
    <div class="admonition exercise">
        <p class="admonition-title">
            <span class="exercise-label">Exercise</span> Solve
        </p>
        <p>Answer: <input class="text-with-gap" answer="42" size="4" /></p>
        <details class="solution">
            <summary>Solution</summary>
            <p>Because it is the answer.</p>
        </details>
    </div>
    """
    state = DocumentState()
    latex = renderer.render(html, state=state)

    assert "\\rule{4ex}{0.4pt}" in latex
    assert state.solutions
    solution_payload = state.solutions[0]
    assert "42" in solution_payload["solution"]
    assert "Because it is the answer." in solution_payload["solution"]


def test_details_callout_rendering(renderer: LaTeXRenderer) -> None:
    html = """
    <details class="note">
        <summary>More info</summary>
        <p>Hidden <strong>details</strong>.</p>
    </details>
    """
    latex = renderer.render(html)
    assert "\\begin{callout}[callout note]{More info}" in latex
    assert "Hidden \\textbf{details}." in latex
