import unittest

from mkdocs_latex.config import BookConfig
from mkdocs_latex.renderer import LaTeXRenderer


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
        html = (
            "<p>Press <span class='keys'><kbd class='key-control'>Ctrl</kbd>"
            "<kbd>s</kbd></span></p>"
        )
        latex = self.renderer.render(html)
        self.assertIn("\\keystroke{Ctrl}+\\keystroke{S}", latex)

    def test_inline_highlight_code(self) -> None:
        html = (
            "<p>Say <code class='highlight'><span class='nb'>print</span>"
            "<span class='p'>(</span><span class='s2'>\"Hi\"</span>"
            "<span class='p'>)</span></code></p>"
        )
        latex = self.renderer.render(html)
        self.assertIn('\\texttt{print("Hi")}', latex)

    def test_unicode_superscript_conversion(self) -> None:
        html = "<p>(0.1 s⁻¹, 1 s⁻¹, 10 s⁻¹)</p>"
        latex = self.renderer.render(html)
        self.assertIn(
            (
                "(0.1 s\\textsuperscript{-1}, 1 s\\textsuperscript{-1}, "
                "10 s\\textsuperscript{-1})"
            ),
            latex,
        )

    def test_unicode_subscript_conversion(self) -> None:
        html = "<p>H₂O and CO₂</p>"
        latex = self.renderer.render(html)
        self.assertIn("H\\textsubscript{2}O", latex)
        self.assertIn("CO\\textsubscript{2}", latex)

    def test_index_span_with_bold_style(self) -> None:
        html = '<p><span data-tag-name="term" data-tag-style="b">Term</span></p>'
        latex = self.renderer.render(html)
        self.assertIn("Term\\index{\\textbf{term}}", latex)

    def test_index_span_without_style(self) -> None:
        html = '<p><span data-tag-name="Entry">Label</span></p>'
        latex = self.renderer.render(html)
        self.assertIn("Label\\index{Entry}", latex)

    def test_index_span_with_italic_style(self) -> None:
        html = '<p><span data-tag-name="horse" data-tag-style="i">Horse</span></p>'
        latex = self.renderer.render(html)
        self.assertIn("Horse\\index{\\textit{horse}}", latex)

    def test_index_anchor_with_bold_italic_style(self) -> None:
        html = '<p><a href="#" data-tag-name="complex" data-tag-style="bi"></a></p>'
        latex = self.renderer.render(html)
        self.assertIn("\\index{\\textbf{\\textit{complex}}}", latex)

    def test_index_nested_entries(self) -> None:
        html = '<p><span data-tag-name="first, second ,third">Nested</span></p>'
        latex = self.renderer.render(html)
        self.assertIn("Nested\\index{first!second!third}", latex)


if __name__ == "__main__":
    unittest.main()
