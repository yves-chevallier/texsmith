from __future__ import annotations

from bs4 import BeautifulSoup
from markdown import Markdown

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown
from texsmith.extensions.quotes import TexsmithQuotesExtension


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


def test_quotes_leave_attribute_lists_alone() -> None:
    # Inline patterns run long before the attr_list treeprocessor: converting
    # ``width="50%"`` into a <q> would split the brace group and drop every
    # attribute, id included, leaving the whole thing as literal text.
    html = render_markdown(
        '![Trace](a.png){#fig:trace width="50%"}', extensions=DEFAULT_MARKDOWN_EXTENSIONS
    ).html
    soup = BeautifulSoup(html, "html.parser")
    image = soup.find("img")
    assert image is not None
    assert image.get("id") == "fig:trace"
    assert image.get("width") == "50%"
    assert soup.find("q") is None


def test_quotes_leave_heading_attribute_lists_alone() -> None:
    html = render_markdown(
        '## Titre {#sec:x title="Mon titre"}', extensions=DEFAULT_MARKDOWN_EXTENSIONS
    ).html
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h2")
    assert heading is not None
    assert heading.get("id") == "sec:x"
    assert heading.get("title") == "Mon titre"


def test_quotes_still_apply_next_to_an_attribute_list() -> None:
    html = render_markdown(
        'Texte "cite" puis ![L](a.png){#fig:y width="3cm"}.',
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html
    soup = BeautifulSoup(html, "html.parser")
    quote = soup.find("q")
    assert quote is not None and quote.text == "cite"
    image = soup.find("img")
    assert image is not None and image.get("width") == "3cm"


def test_quotes_inside_a_plain_brace_group_are_untouched() -> None:
    # A brace in running prose carries no ``#id`` / ``.class`` / ``key=`` token,
    # so it is not an attribute list and its quotes keep their meaning.
    html = render_markdown(
        'Une phrase {avec des "guillemets"} en prose.', extensions=DEFAULT_MARKDOWN_EXTENSIONS
    ).html
    soup = BeautifulSoup(html, "html.parser")
    quote = soup.find("q")
    assert quote is not None and quote.text == "guillemets"
