"""HTML input end to end: MkDocs page HTML → ``HtmlReader`` → passes → tmark writers.

The pages of ``tests/test_mkdocs`` are built with MkDocs (as
``tests/test_mkdocs_html.py`` does), read with :meth:`Document.from_html`
and rendered through the same pipeline as a ``--reader tmark`` Markdown
source. The ``ts-*`` contract macros of the tmark writers are asserted in
the bodies; the fragments defining them are the engine's business.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
from typer.testing import CliRunner

from texsmith.core.conversion.core import convert_documents
from texsmith.core.documents import Document
from texsmith.ir import model
from texsmith.ui.cli import app


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # pragma: no cover - optional dependency
    from mkdocs.commands.build import build as mkdocs_build
    from mkdocs.config import load_config
except ModuleNotFoundError:  # pragma: no cover - graceful degradation
    mkdocs_build = None  # type: ignore[assignment]
    load_config = None  # type: ignore[assignment]


pytestmark = pytest.mark.skipif(
    mkdocs_build is None, reason="MkDocs is not installed; skipping HTML input tests."
)


@pytest.fixture(scope="module")
def mkdocs_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    assert mkdocs_build is not None
    assert load_config is not None

    site_dir = tmp_path_factory.mktemp("mkdocs-site") / "site"
    config_path = ROOT / "tests" / "test_mkdocs" / "mkdocs.yml"
    config = load_config(
        config_file=str(config_path),
        site_dir=str(site_dir),
        docs_dir=str(config_path.parent / "docs"),
    )
    mkdocs_build(config)
    return site_dir


def _render(page: Path, out: Path) -> tuple[Document, str]:
    document = Document.from_html(page)
    bundle = convert_documents([document], output_dir=out)
    return document, bundle.fragments[0].latex


def test_from_html_builds_the_ir_document_shape(mkdocs_site: Path) -> None:
    document = Document.from_html(mkdocs_site / "formatting" / "index.html")
    assert document.reader == "html"
    assert isinstance(document.ir, model.Document)
    assert document.files.path(document.ir.file) == mkdocs_site / "formatting" / "index.html"
    assert document.files.text(document.ir.file) == ""
    assert document.keys == model.Keys()
    assert document.diagnostics == []
    assert document.press == {}
    assert document.first_heading_level() == 1
    assert [header.level for header in document.top_level_headers()] == [1]

    document.set_front_matter({"title": "Formatting", "press": {"language": "fr"}})
    assert document.press["language"] == "fr"


def test_formatting_page_renders_through_the_tmark_writers(
    mkdocs_site: Path, tmp_path: Path
) -> None:
    _document, latex = _render(mkdocs_site / "formatting" / "index.html", tmp_path)
    assert "\\chapter{Formatting Showcase}" in latex
    assert (
        "\\textbf{bold}, \\emph{italic}, \\sout{strikethrough}, and \\tsmark{highlighted}" in latex
    )
    assert '\\tscodeinline{print("highlight")}' in latex
    assert "\\begin{displayquote}" in latex
    assert "\\item[\\tsdone] Completed" in latex
    assert "\\item[\\tstodo] Pending" in latex
    assert "\\href{https://www.mkdocs.org/}{MkDocs}" in latex
    assert "\\begin{description}" in latex
    assert (
        "\\item[{Term}] Meaning that includes \\emph{emphasis} and \\tscodeinline{code}." in latex
    )


def test_headings_page_keeps_levels_and_explicit_ids(mkdocs_site: Path, tmp_path: Path) -> None:
    _document, latex = _render(mkdocs_site / "headings" / "index.html", tmp_path)
    assert "\\chapter{Heading Overview}\\label{heading-overview}" in latex
    assert "\\section{Section Level Two}\\label{section-level-two}" in latex
    assert "\\subsection{Subsection With Custom ID}\\label{custom-heading}" in latex
    assert "\\paragraph{Fifth Level Heading}" in latex


def test_code_page_goes_through_the_highlight_pass(mkdocs_site: Path, tmp_path: Path) -> None:
    _document, latex = _render(mkdocs_site / "code" / "index.html", tmp_path)
    assert "\\begin{tscode}[lang=text, engine=pygments]" in latex
    assert "def add(a, b):" in latex
    assert "\\tscodeinline{sum(range(10))}" in latex


def test_cli_renders_a_page_with_a_template(mkdocs_site: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = CliRunner().invoke(
        app,
        [str(mkdocs_site / "formatting" / "index.html"), "-o", str(out), "-t", "article"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    tex = (out / "index.tex").read_text(encoding="utf-8")
    assert "\\begin{document}" in tex
    assert "\\tsmark{highlighted}" in tex
    assert "\\begin{tstasklist}" in tex
