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


def test_strip_custom_class_rule(renderer: LaTeXRenderer) -> None:
    html = """
    <body>
        <div class="keep">Keep me</div>
        <div class="remove-me"><span>Drop me</span></div>
        <h1>Heading</h1>
    </body>
    """
    latex = renderer.render(
        html,
        runtime={
            "base_level": 1,
            "strip_tags": {
                "body": "unwrap",
                "div": {"mode": "extract", "classes": ["remove-me"]},
            },
        },
    )
    assert "Keep me" in latex
    assert "Drop me" not in latex
    assert "\\section{Heading}" in latex
