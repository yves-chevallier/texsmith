import unittest

from texsmith.config import BookConfig
from texsmith.context import DocumentState
from texsmith.renderer import LaTeXRenderer


class AdmonitionRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")

    def test_fill_in_the_blank_solution_capture(self) -> None:
        from texsmith.plugins import material

        material.register(self.renderer)
        html = """
        <div class="admonition exercise">
            <p class="admonition-title">
                <span class="exercise-label">Exercise</span> Solve
            </p>
            <p>Answer: <input class="text-with-gap" answer="42" size="4" /></p>
            <details class="solution">
                <summary>Solution</summary>
                <p>Because it is the answer.</p>
            </details>
        </div>
        """
        state = DocumentState()
        latex = self.renderer.render(html, state=state)

        self.assertIn("\\rule{4ex}{0.4pt}", latex)
        self.assertTrue(state.solutions)
        solution_payload = state.solutions[0]
        self.assertIn("42", solution_payload["solution"])
        self.assertIn("Because it is the answer.", solution_payload["solution"])

    def test_details_callout_rendering(self) -> None:
        html = """
        <details class="note">
            <summary>More info</summary>
            <p>Hidden <strong>details</strong>.</p>
        </details>
        """
        latex = self.renderer.render(html)
        self.assertIn("\\begin{callout}[callout note]{More info}", latex)
        self.assertIn("Hidden \\textbf{details}.", latex)


if __name__ == "__main__":
    unittest.main()
