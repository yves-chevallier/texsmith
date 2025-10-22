from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from texsmith.config import BookConfig
from texsmith.context import DocumentState
from texsmith.renderer import LaTeXRenderer


class LinkRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")

    def test_external_link_rendering(self) -> None:
        html = '<p><a href="https://example.com">Example</a></p>'
        latex = self.renderer.render(html)
        self.assertIn("\\href{https://example.com}{Example}", latex)

    def test_internal_anchor_link_rendering(self) -> None:
        html = '<p><a href="#section-1">Jump</a></p>'
        latex = self.renderer.render(html)
        self.assertIn("\\ref{section-1}", latex)

    def test_label_generated_for_anchor_without_href(self) -> None:
        html = '<a id="section-1"></a>'
        latex = self.renderer.render(html)
        self.assertIn("\\label{section-1}", latex)

    def test_local_file_link_registers_snippet(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            snippet_file = tmp_path / "snippet.txt"
            snippet_file.write_text("print('Hello snippet')", encoding="utf-8")
            html = f'<p><a href="{snippet_file.name}">See snippet</a></p>'
            state = DocumentState()
            latex = self.renderer.render(
                html,
                runtime={"document_path": tmp_path / "index.md"},
                state=state,
            )

            self.assertTrue(state.snippets)
            reference_key = next(iter(state.snippets))
            payload = state.snippets[reference_key]
            self.assertEqual(payload["path"], snippet_file.resolve())
            self.assertEqual(payload["content"], snippet_file.read_bytes())
            self.assertIn(reference_key, latex)


if __name__ == "__main__":
    unittest.main()
