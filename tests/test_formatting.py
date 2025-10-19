import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from latex.config import BookConfig
from latex.renderer import LaTeXRenderer


class InlineFormattingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")

    def test_strong_tag_converted(self) -> None:
        html = "<strong>Important</strong>"
        latex = self.renderer.render(html)
        self.assertEqual("\\textbf{Important}", latex.strip())

    def test_emphasis_tag_converted(self) -> None:
        html = "<em>Italic</em>"
        latex = self.renderer.render(html)
        self.assertEqual("\\emph{Italic}", latex.strip())

    def test_underline_tag_converted(self) -> None:
        html = "<ins>Highlight</ins>"
        latex = self.renderer.render(html)
        self.assertEqual("\\uline{Highlight}", latex.strip())

    def test_critic_substitution(self) -> None:
        html = "<p><span class='critic subst'><del>bad</del><ins>good</ins></span></p>"
        latex = self.renderer.render(html)
        self.assertIn("\\xout{bad}\\ \\uline{good}", latex)

    def test_nested_strong_inside_emphasis(self) -> None:
        html = "<p><em>Very <strong>important</strong></em></p>"
        latex = self.renderer.render(html)
        self.assertIn("\\emph{Very \\textbf{important}}", latex)

    def test_nested_emphasis_inside_underline(self) -> None:
        html = "<p><ins><em>note</em></ins></p>"
        latex = self.renderer.render(html)
        self.assertIn("\\uline{\\emph{note}}", latex)

    def test_keyboard_shortcut_rendering(self) -> None:
        html = "<p>Press <span class='keys'><kbd class='key-control'>Ctrl</kbd><kbd>s</kbd></span></p>"
        latex = self.renderer.render(html)
        self.assertIn("\\keystroke{Ctrl}+\\keystroke{S}", latex)

    def test_inline_highlight_code(self) -> None:
        html = "<p>Say <code class='highlight'><span class='nb'>print</span><span class='p'>(</span><span class='s2'>\"Hi\"</span><span class='p'>)</span></code></p>"
        latex = self.renderer.render(html)
        self.assertIn("\\texttt{print(\"Hi\")}", latex)


if __name__ == "__main__":
    unittest.main()
