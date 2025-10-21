import unittest

from texsmith.config import BookConfig
from texsmith.renderer import LaTeXRenderer


class BlockRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")

    def test_inline_code_rendering(self) -> None:
        html = "<p>Use <code>print('hi')</code> in Python.</p>"
        latex = self.renderer.render(html)
        self.assertIn("\\texttt{print('hi')}", latex)

    def test_ordered_list_rendering(self) -> None:
        html = "<ol><li>First</li><li>Second</li></ol>"
        latex = self.renderer.render(html)
        self.assertIn("\\begin{enumerate}", latex)
        self.assertIn("\\item First", latex)
        self.assertIn("\\item Second", latex)

    def test_unordered_list_with_formatting(self) -> None:
        html = "<ul><li>Item <em>one</em></li><li><strong>Two</strong></li></ul>"
        latex = self.renderer.render(html)
        self.assertIn("\\begin{itemize}", latex)
        self.assertIn("Item \\emph{one}", latex)
        self.assertIn("\\textbf{Two}", latex)

    def test_task_list_rendering(self) -> None:
        html = "<ul><li>[x] Completed task</li><li>[ ] Pending task</li></ul>"
        latex = self.renderer.render(html)
        self.assertIn("\\begin{description}", latex)
        self.assertIn("\\correctchoice", latex)
        self.assertIn("Completed task", latex)
        self.assertIn("\\choice", latex)
        self.assertIn("Pending task", latex)

    def test_definition_list_rendering(self) -> None:
        html = "<dl><dt>Apple</dt><dd>Sweet</dd><dt>Banana</dt><dd>Yellow</dd></dl>"
        latex = self.renderer.render(html)
        self.assertIn("\\begin{description}", latex)
        self.assertIn("\\item[Apple] Sweet", latex)
        self.assertIn("\\item[Banana] Yellow", latex)

    def test_footnote_conversion(self) -> None:
        html = """
        <p>See note<sup id="fnref:1"><a href="#fn:1">1</a></sup>.</p>
        <div class="footnote">
            <ol>
                <li id="fn:1">Footnote content</li>
            </ol>
        </div>
        """
        latex = self.renderer.render(html)
        self.assertIn("\\footnote{Footnote content}", latex)
        self.assertNotIn("<div", latex)


if __name__ == "__main__":
    unittest.main()
