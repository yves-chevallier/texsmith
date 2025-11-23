import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.config import BookConfig
from texsmith.core.context import DocumentState


@pytest.fixture
def renderer() -> LaTeXRenderer:
    return LaTeXRenderer(config=BookConfig(), parser="html.parser")


def test_fill_in_the_blank_solution_capture(renderer: LaTeXRenderer) -> None:
    from texsmith.adapters.plugins import material

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


def test_blockquote_callout_rendering(renderer: LaTeXRenderer) -> None:
    html = """
    <blockquote>
        <p>[!note] Ceci est une note.\n   Utilisé sur Docusaurus, Obsidian, GitHub.</p>
    </blockquote>
    """
    latex = renderer.render(html)
    assert "\\begin{callout}[callout note]{Ceci est une note.}" in latex
    assert "Utilisé sur Docusaurus, Obsidian, GitHub." in latex


def test_callout_inline_code_is_preserved(renderer: LaTeXRenderer) -> None:
    html = """
    <div class="admonition tip">
        <p class="admonition-title">Tip</p>
        <ul>
            <li>Foo (<code>foo_bar</code>)</li>
            <li>Bar <code>bar__foo</code></li>
            <li><strong>Baz</strong></li>
        </ul>
    </div>
    """
    latex = renderer.render(html)
    assert (
        latex.strip()
        == r"""
\begin{callout}[callout tip]{Tip}
\begin{itemize}
\item{} Foo (\texttt{foo\_bar})
\item{} Bar \texttt{bar\_\_foo}
\item{} \textbf{Baz}

\end{itemize}
\end{callout}
""".strip()
    )
