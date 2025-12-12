from __future__ import annotations

from bs4 import BeautifulSoup

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown


def test_smart_dashes_convert_in_html() -> None:
    html = render_markdown(
        "hello -- world --- worlds",
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html
    soup = BeautifulSoup(html, "html.parser")

    assert soup.get_text() == "hello \u2013 world \u2014 worlds"


def test_smart_dashes_skip_code() -> None:
    html = render_markdown("`--` and `---`", extensions=DEFAULT_MARKDOWN_EXTENSIONS).html
    soup = BeautifulSoup(html, "html.parser")
    code = soup.find("code")
    assert code is not None
    assert code.text == "--"
    assert soup.get_text() == "-- and ---"


def test_latex_output_preserves_ascii_dashes() -> None:
    html = render_markdown(
        "hello -- world --- worlds",
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html
    renderer = LaTeXRenderer()

    latex = renderer.render(html)

    assert "hello -- world --- worlds" in latex
