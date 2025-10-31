import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.adapters.markdown import render_markdown
from texsmith.core.config import BookConfig
from texsmith.ui.cli import DEFAULT_MARKDOWN_EXTENSIONS


markdown = pytest.importorskip("markdown")


def _render(source: str) -> str:
    md = markdown.Markdown(extensions=DEFAULT_MARKDOWN_EXTENSIONS)
    return md.convert(source)


def test_latex_text_replaced_in_paragraph() -> None:
    html = _render("TexSmith prend en charge LaTeX dès maintenant.")

    assert 'class="latex-text"' in html
    assert "LaTeX" not in html


def test_latex_text_skips_code_blocks_and_inline_code() -> None:
    source = "Avant LaTeX\n\n```\nLaTeX\n```\n\n`LaTeX` après"
    html = _render(source)

    assert html.count('class="latex-text"') == 1
    assert "<code>LaTeX</code>" in html


def test_latex_text_inside_emphasis_is_replaced() -> None:
    html = _render("Une mise en évidence de *LaTeX* pour la démonstration.")

    assert '<em><span class="latex-text"' in html


def test_latex_text_converts_to_latex_macro() -> None:
    html = render_markdown(
        "LaTeX et encore *LaTeX*.",
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html
    renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")
    latex = renderer.render(html)

    assert latex.count("\\LaTeX{}") == 2
