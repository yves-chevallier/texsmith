from __future__ import annotations

from bs4 import BeautifulSoup
from markdown import Markdown

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.progressbar import ProgressBarExtension


def _render_html(markdown_text: str) -> BeautifulSoup:
    md = Markdown(extensions=[ProgressBarExtension()])
    html = md.convert(markdown_text)
    return BeautifulSoup(html, "html.parser")


def test_markdown_generates_progress_div() -> None:
    soup = _render_html('[=73% "Almost There"]{: .thin .custom data-theme="dark"}')
    node = soup.find("div", class_="progress")
    assert node is not None
    assert "progress-70plus" in node.get("class", [])
    assert node["data-progress-percent"].startswith("73")
    assert node["data-progress-fraction"].startswith("0.73")
    assert node["data-theme"] == "dark"
    assert "thin" in node.get("class", [])


def test_markdown_ignores_fenced_code_blocks() -> None:
    soup = _render_html('```\n[=90% "Snippet"]\n```')
    assert '[=90% "Snippet"]' in soup.get_text()
    assert not soup.find("div", class_="progress")


def test_renderer_outputs_progressbar_command() -> None:
    soup = _render_html('[=25% "Planning"]')
    renderer = LaTeXRenderer()

    latex = renderer.render(str(soup))
    assert "\\progressbar" in latex
    assert "{0.25}" in latex
    assert "Planning" in latex
