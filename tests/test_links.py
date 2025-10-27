from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.config import BookConfig
from texsmith.core.context import DocumentState


@pytest.fixture
def renderer() -> LaTeXRenderer:
    return LaTeXRenderer(config=BookConfig(), parser="html.parser")


def test_external_link_rendering(renderer: LaTeXRenderer) -> None:
    html = '<p><a href="https://example.com">Example</a></p>'
    latex = renderer.render(html)
    assert "\\href{https://example.com}{Example}" in latex


def test_internal_anchor_link_rendering(renderer: LaTeXRenderer) -> None:
    html = '<p><a href="#section-1">Jump</a></p>'
    latex = renderer.render(html)
    assert "\\ref{section-1}" in latex


def test_label_generated_for_anchor_without_href(renderer: LaTeXRenderer) -> None:
    html = '<a id="section-1"></a>'
    latex = renderer.render(html)
    assert "\\label{section-1}" in latex


def test_local_file_link_registers_snippet(renderer: LaTeXRenderer) -> None:
    with TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        snippet_file = tmp_path / "snippet.txt"
        snippet_file.write_text("print('Hello snippet')", encoding="utf-8")
        html = f'<p><a href="{snippet_file.name}">See snippet</a></p>'
        state = DocumentState()
        latex = renderer.render(
            html,
            runtime={"document_path": tmp_path / "index.md"},
            state=state,
        )

        assert state.snippets
        reference_key = next(iter(state.snippets))
        payload = state.snippets[reference_key]
        assert payload["path"] == snippet_file.resolve()
        assert payload["content"] == snippet_file.read_bytes()
        assert reference_key in latex
