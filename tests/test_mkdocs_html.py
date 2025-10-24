from collections.abc import Callable
from pathlib import Path
import sys

from bs4 import BeautifulSoup
import pytest


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
    mkdocs_build is None, reason="MkDocs is not installed; skipping HTML integration tests."
)


@pytest.fixture(scope="module")
def mkdocs_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    assert mkdocs_build is not None
    assert load_config is not None

    temp_root = tmp_path_factory.mktemp("mkdocs-site")
    site_dir = temp_root / "site"

    config_path = ROOT / "tests" / "test_mkdocs" / "mkdocs.yml"
    docs_dir = config_path.parent / "docs"

    config = load_config(
        config_file=str(config_path),
        site_dir=str(site_dir),
        docs_dir=str(docs_dir),
    )
    mkdocs_build(config)
    return site_dir


@pytest.fixture
def load_soup(mkdocs_site: Path) -> Callable[[str], BeautifulSoup]:
    def _load_soup(slug: str) -> BeautifulSoup:
        target = mkdocs_site / slug / "index.html"
        assert target.exists(), f"Expected HTML file {target} was not generated."
        html = target.read_text(encoding="utf-8")
        return BeautifulSoup(html, "html.parser")

    return _load_soup


def test_formatting_page_contains_inline_elements(
    load_soup: Callable[[str], BeautifulSoup],
) -> None:
    soup = load_soup("formatting")

    bold = soup.find("strong", string="bold")
    italic = soup.find("em", string="italic")
    strike = soup.find("del", string="strikethrough")
    highlight = soup.find("mark", string="highlighted")
    inline_code = soup.find("code", string='print("highlight")')
    blockquote = soup.find("blockquote")
    link = soup.find("a", href="https://www.mkdocs.org/")

    assert bold is not None
    assert italic is not None
    assert strike is not None
    assert highlight is not None
    assert inline_code is not None
    assert blockquote is not None
    assert link is not None

    definition_list = soup.find("dl")
    assert definition_list is not None
    assert definition_list.find("dt", string="Term") is not None
    assert definition_list.find("dd") is not None


def test_headings_page_levels(load_soup: Callable[[str], BeautifulSoup]) -> None:
    soup = load_soup("headings")

    h1 = soup.find("h1", id="heading-overview")
    h2 = soup.find("h2", id="section-level-two")
    h3 = soup.find("h3", id="custom-heading")
    h4 = soup.find("h4")
    h5 = soup.find("h5")

    assert h1 is not None
    assert h1.get_text(strip=True) == "Heading Overview"
    assert h2 is not None
    assert h2.get_text(strip=True) == "Section Level Two"
    assert h3 is not None
    assert h3.get_text(strip=True) == "Subsection With Custom ID"
    assert h4 is not None
    assert "Fourth Level Heading" in h4.get_text(strip=True)
    assert h5 is not None
    assert "Fifth Level Heading" in h5.get_text(strip=True)


def test_code_page_has_syntax_highlighting(load_soup: Callable[[str], BeautifulSoup]) -> None:
    soup = load_soup("code")

    highlight_blocks = soup.select("div.highlight")
    block_texts = [" ".join(block.stripped_strings) for block in highlight_blocks]
    inline_code = soup.find("code", string="sum(range(10))")

    assert highlight_blocks, "Expected highlighted code blocks were not generated."
    assert any("def add" in text for text in block_texts)
    assert any('echo "shell block"' in text for text in block_texts)
    assert any('{"valid": true' in text for text in block_texts)
    assert inline_code is not None
