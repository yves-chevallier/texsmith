from __future__ import annotations

from bs4 import BeautifulSoup
from markdown import Markdown

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown
from texsmith.quotes import TexsmithQuotesExtension


def test_quotes_extension_wraps_text_in_q_tags() -> None:
    html = render_markdown('Il a dit "bonjour"', extensions=DEFAULT_MARKDOWN_EXTENSIONS).html
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find("q")
    assert node is not None
    assert node.text == "bonjour"


def test_quotes_extension_ignores_code_spans() -> None:
    html = render_markdown('`"bonjour"`', extensions=DEFAULT_MARKDOWN_EXTENSIONS).html
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("q") is None
    code = soup.find("code")
    assert code is not None and code.text == '"bonjour"'


def test_renderer_outputs_enquote_for_q_tags() -> None:
    md = Markdown(extensions=[TexsmithQuotesExtension()])
    soup = BeautifulSoup(md.convert('Il a dit "bonjour"'), "html.parser")

    renderer = LaTeXRenderer()
    latex = renderer.render(str(soup))

    assert "\\enquote{bonjour}" in latex


def test_inline_formatting_inside_quotes() -> None:
    html = render_markdown('" **bold** "', extensions=DEFAULT_MARKDOWN_EXTENSIONS).html
    soup = BeautifulSoup(html, "html.parser")
    q = soup.find("q")
    assert q is not None
    assert q.find("strong") is not None, "bold should be parsed inside quotes"

    renderer = LaTeXRenderer()
    latex = renderer.render(str(soup))
    assert "\\enquote{" in latex
    assert "\\textbf{bold}" in latex
