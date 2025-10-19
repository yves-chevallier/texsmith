from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # pragma: no cover - optional dependency
    from mkdocs.commands.build import build as mkdocs_build
    from mkdocs.config import load_config
except ModuleNotFoundError:  # pragma: no cover - graceful degradation
    mkdocs_build = None  # type: ignore[assignment]
    load_config = None  # type: ignore[assignment]


@unittest.skipIf(
    mkdocs_build is None, "MkDocs is not installed; skipping HTML integration tests."
)
class MkDocsHTMLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = TemporaryDirectory()
        cls.tmp_path = Path(cls.tmp.name)
        cls.site_dir = cls.tmp_path / "site"

        config_path = ROOT / "tests" / "test_mkdocs" / "mkdocs.yml"
        cls.docs_dir = config_path.parent / "docs"

        config = load_config(
            config_file=str(config_path),
            site_dir=str(cls.site_dir),
            docs_dir=str(cls.docs_dir),
        )
        mkdocs_build(config)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def _load_soup(self, slug: str) -> BeautifulSoup:
        target = self.site_dir / slug / "index.html"
        self.assertTrue(
            target.exists(), f"Expected HTML file {target} was not generated."
        )
        html = target.read_text(encoding="utf-8")
        return BeautifulSoup(html, "html.parser")

    def test_formatting_page_contains_inline_elements(self) -> None:
        soup = self._load_soup("formatting")

        bold = soup.find("strong", string="bold")
        italic = soup.find("em", string="italic")
        strike = soup.find("del", string="strikethrough")
        highlight = soup.find("mark", string="highlighted")
        inline_code = soup.find("code", string='print("highlight")')
        blockquote = soup.find("blockquote")
        link = soup.find("a", href="https://www.mkdocs.org/")

        self.assertIsNotNone(bold)
        self.assertIsNotNone(italic)
        self.assertIsNotNone(strike)
        self.assertIsNotNone(highlight)
        self.assertIsNotNone(inline_code)
        self.assertIsNotNone(blockquote)
        self.assertIsNotNone(link)

        # Definition list should produce <dl> with nested <dt>/<dd>
        definition_list = soup.find("dl")
        self.assertIsNotNone(definition_list)
        self.assertIsNotNone(definition_list.find("dt", string="Term"))
        self.assertIsNotNone(definition_list.find("dd"))

    def test_headings_page_levels(self) -> None:
        soup = self._load_soup("headings")

        h1 = soup.find("h1", id="heading-overview")
        h2 = soup.find("h2", id="section-level-two")
        h3 = soup.find("h3", id="custom-heading")
        h4 = soup.find("h4")
        h5 = soup.find("h5")

        self.assertIsNotNone(h1)
        self.assertEqual(h1.get_text(strip=True), "Heading Overview")
        self.assertIsNotNone(h2)
        self.assertEqual(h2.get_text(strip=True), "Section Level Two")
        self.assertIsNotNone(h3)
        self.assertEqual(h3.get_text(strip=True), "Subsection With Custom ID")
        self.assertIsNotNone(h4)
        self.assertIn("Fourth Level Heading", h4.get_text(strip=True))
        self.assertIsNotNone(h5)
        self.assertIn("Fifth Level Heading", h5.get_text(strip=True))

    def test_code_page_has_syntax_highlighting(self) -> None:
        soup = self._load_soup("code")

        highlight_blocks = soup.select("div.highlight")
        block_texts = [" ".join(block.stripped_strings) for block in highlight_blocks]
        inline_code = soup.find("code", string="sum(range(10))")

        self.assertTrue(
            highlight_blocks, "Expected highlighted code blocks were not generated."
        )
        self.assertTrue(any("def add" in text for text in block_texts))
        self.assertTrue(any('echo "shell block"' in text for text in block_texts))
        self.assertTrue(any('{"valid": true' in text for text in block_texts))
        self.assertIsNotNone(inline_code)


if __name__ == "__main__":
    unittest.main()
