import unittest

from latex.config import BookConfig
from latex.context import DocumentState
from latex.renderer import LaTeXRenderer


class HeadingRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")

    def test_basic_heading_rendering(self) -> None:
        html = "<h2 id='intro'>Introduction</h2>"
        state = DocumentState()
        latex = self.renderer.render(
            html,
            runtime={"base_level": 0},
            state=state,
        )
        self.assertIn("\\section{Introduction}\\label{intro}", latex)
        self.assertEqual(
            state.headings,
            [{"level": 1, "text": "Introduction", "ref": "intro"}],
        )

    def test_inline_formatting_preserved(self) -> None:
        html = "<h3 id='intro'>Intro <strong>Bold</strong></h3>"
        latex = self.renderer.render(html, runtime={"base_level": 0})
        self.assertIn("\\subsection{Intro \\textbf{Bold}}\\label{intro}", latex)

    def test_heading_with_nested_formatting(self) -> None:
        html = "<h2 id='mix'>Title <strong>and <em>mix</em></strong></h2>"
        latex = self.renderer.render(html, runtime={"base_level": 0})
        self.assertIn("\\section{Title \\textbf{and \\emph{mix}}}\\label{mix}", latex)

    def test_drop_title_runtime_flag(self) -> None:
        html = "<h1>Main Title</h1><h2>Subsection</h2>"
        state = DocumentState()
        latex = self.renderer.render(
            html,
            runtime={"base_level": 0, "drop_title": True},
            state=state,
        )
        self.assertNotIn("\\chapter{Main Title}", latex)
        self.assertIn("\\thispagestyle{plain}", latex)
        self.assertIn("\\section{Subsection}", latex)
        self.assertEqual(
            state.headings,
            [{"level": 1, "text": "Subsection", "ref": None}],
        )


if __name__ == "__main__":
    unittest.main()
