import unittest

from latex.config import BookConfig
from latex.renderer import LaTeXRenderer


class StripTagsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")

    def test_strip_default_html_structure(self) -> None:
        html = """
        <html>
            <head>
                <title>Should disappear</title>
            </head>
            <body>
                <h1>Main</h1>
                <p>Content</p>
            </body>
        </html>
        """
        latex = self.renderer.render(
            html,
            runtime={
                "base_level": 1,
                "strip_tags": {
                    "html": "unwrap",
                    "body": "unwrap",
                    "head": {"mode": "decompose"},
                },
            },
        )
        self.assertNotIn("<head", latex)
        self.assertNotIn("<body", latex)
        self.assertNotIn("<html", latex)
        self.assertIn("\\section{Main}", latex)
        self.assertIn("Content", latex)

    def test_strip_custom_class_rule(self) -> None:
        html = """
        <body>
            <div class="keep">Keep me</div>
            <div class="remove-me"><span>Drop me</span></div>
            <h1>Heading</h1>
        </body>
        """
        latex = self.renderer.render(
            html,
            runtime={
                "base_level": 1,
                "strip_tags": {
                    "body": "unwrap",
                    "div": {"mode": "extract", "classes": ["remove-me"]},
                },
            },
        )
        self.assertIn("Keep me", latex)
        self.assertNotIn("Drop me", latex)
        self.assertIn("\\section{Heading}", latex)


if __name__ == "__main__":
    unittest.main()
