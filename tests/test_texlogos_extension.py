"""Integration tests for the texsmith-texlogos extension package."""

from __future__ import annotations

from pathlib import Path
import sys

from bs4 import BeautifulSoup
from markdown import Markdown


ROOT = Path(__file__).resolve().parents[1]
EXT_SRC = ROOT / "packages" / "texsmith-texlogos" / "src"
if str(EXT_SRC) not in sys.path:
    sys.path.insert(0, str(EXT_SRC))

from texsmith_texlogos import iter_specs, register_renderer  # noqa: E402
from texsmith_texlogos.markdown import TexLogosExtension  # noqa: E402

from texsmith.adapters.latex.renderer import LaTeXRenderer  # noqa: E402


def _convert(text: str) -> BeautifulSoup:
    md = Markdown(extensions=[TexLogosExtension()])
    html = md.convert(text)
    return BeautifulSoup(html, "html.parser")


def test_markdown_generates_logo_spans() -> None:
    soup = _convert("TeX, LaTeX, LaTeX2e, TeXSmith.")
    spans = soup.find_all("span", class_="tex-logo")
    assert len(spans) == 4

    commands = {span["data-tex-command"] for span in spans}
    expected = {spec.command for spec in iter_specs()}
    assert commands == expected


def test_markdown_skips_code_blocks() -> None:
    soup = _convert("`TeX` should remain untouched.")
    assert not soup.find_all("span", class_="tex-logo")


def test_renderer_emits_logo_commands() -> None:
    soup = _convert("TeX, LaTeX, LaTeX2e, TeXSmith.")
    renderer = LaTeXRenderer()
    register_renderer(renderer)

    latex = renderer.render(str(soup))
    for spec in iter_specs():
        assert spec.command in latex
