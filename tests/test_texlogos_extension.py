"""Integration tests for the bundled TeX logos extension."""

from __future__ import annotations

from bs4 import BeautifulSoup
from markdown import Markdown

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.texlogos import TexLogosExtension, iter_specs, register_renderer


def _convert(text: str) -> BeautifulSoup:
    md = Markdown(extensions=[TexLogosExtension()])
    html = md.convert(text)
    return BeautifulSoup(html, "html.parser")


def test_markdown_generates_logo_spans() -> None:
    soup = _convert("TeX, LaTeX, LaTeX2e, TeXSmith.")
    spans = soup.find_all("span", class_="tex-logo")
    assert len(spans) == 3

    commands = {span["data-tex-command"] for span in spans}
    expected = {spec.command for spec in iter_specs()}
    assert commands == expected
    assert not soup.find("span", attrs={"data-tex-logo": "texsmith"})


def test_markdown_skips_code_blocks() -> None:
    soup = _convert("`TeX` should remain untouched.")
    assert not soup.find_all("span", class_="tex-logo")


def test_renderer_emits_logo_commands() -> None:
    soup = _convert("TeX, LaTeX, LaTeX2e.")
    renderer = LaTeXRenderer()
    register_renderer(renderer)

    latex = renderer.render(str(soup))
    for spec in iter_specs():
        assert spec.command in latex
