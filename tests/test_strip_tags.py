import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.config import BookConfig


@pytest.fixture
def renderer() -> LaTeXRenderer:
    return LaTeXRenderer(config=BookConfig(), parser="html.parser")


def test_strip_default_html_structure(renderer: LaTeXRenderer) -> None:
    html = """
    <html>
        <head>
            <title>Should disappear</title>
        </head>
        <body>
            <h1>Main</h1>
            <p>Content</p>
        </body>
    </html>
    """
    latex = renderer.render(
        html,
        runtime={
            "base_level": 1,
            "strip_tags": {
                "html": "unwrap",
                "body": "unwrap",
                "head": {"mode": "decompose"},
            },
        },
    )
    assert "<head" not in latex
    assert "<body" not in latex
    assert "<html" not in latex
    assert "\\section{Main}" in latex
    assert "Content" in latex


def test_html_comment_stripped(renderer: LaTeXRenderer) -> None:
    html = "<!-- This is a comment --><p>Hello</p>"
    latex = renderer.render(html)
    assert "This is a comment" not in latex
    assert "Hello" in latex


def test_html_comment_between_paragraphs_stripped(renderer: LaTeXRenderer) -> None:
    html = "<p>Before</p><!-- hidden note --><p>After</p>"
    latex = renderer.render(html)
    assert "hidden note" not in latex
    assert "Before" in latex
    assert "After" in latex


def test_html_comment_inside_paragraph_stripped(renderer: LaTeXRenderer) -> None:
    html = "<p>Start<!-- inline comment -->End</p>"
    latex = renderer.render(html)
    assert "inline comment" not in latex
    assert "Start" in latex
    assert "End" in latex


def test_latex_ignore_div_dropped(renderer: LaTeXRenderer) -> None:
    # The configurable ``strip_tags`` runtime override is gone with the legacy
    # engine; structural stripping (and the built-in ``latex-ignore`` opt-out)
    # is now the reader's responsibility.
    html = """
    <body>
        <div class="keep">Keep me</div>
        <div class="latex-ignore"><span>Drop me</span></div>
        <h1>Heading</h1>
    </body>
    """
    latex = renderer.render(html, runtime={"base_level": 1})
    assert "Keep me" in latex
    assert "Drop me" not in latex
    assert "\\section{Heading}" in latex
