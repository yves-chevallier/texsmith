"""The mini site (``tests/test_mkdocs``) rendered by Material through the ``texsmith`` plugin.

The plugin lowers every page with ``tmark.lower_web`` before Python-Markdown
runs; these tests assert what Material renders from the spliced constructs
(``specs/migration/web-profile.md``, per-construct table) and the site-wide
numbering across two pages.
"""

from collections.abc import Callable
import json
from pathlib import Path
import re
import shutil
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

    # The configuration is copied so the plugin's ``press/`` lands in the
    # temporary project, not in the repository.
    temp_root = tmp_path_factory.mktemp("mkdocs-site")
    site_dir = temp_root / "site"
    source = ROOT / "tests" / "test_mkdocs"
    config_path = temp_root / "mkdocs.yml"
    shutil.copy(source / "mkdocs.yml", config_path)

    config = load_config(
        config_file=str(config_path),
        site_dir=str(site_dir),
        docs_dir=str(source / "docs"),
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


@pytest.fixture
def load_article(load_soup: Callable[[str], BeautifulSoup]) -> Callable[[str], BeautifulSoup]:
    """The page's ``<article>``: the rendered body, without the nav and the table of contents."""

    def _load_article(slug: str) -> BeautifulSoup:
        article = load_soup(slug).find("article")
        assert article is not None, f"page '{slug}' has no <article>"
        return article

    return _load_article


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


# -- the lowered constructs (tests/test_mkdocs/docs/constructs.md) ------------


def test_counters_are_numbered_and_linked(load_article: Callable[[str], BeautifulSoup]) -> None:
    soup = load_article("constructs")
    watchdog = soup.find("span", class_="ts-counter", id="fw:watchdog")
    assert watchdog is not None and watchdog.get_text() == "FW-01"
    assert watchdog["data-counter"] == "fw" and watchdog["data-key"] == "watchdog"
    ota = soup.find("span", class_="ts-counter", id="fw:ota")
    assert ota is not None and ota.get_text() == "FW-02"
    # The silent heading definition and the item in a table cell continue the series.
    assert soup.find("a", href="#fw:log-wrap").get_text() == "FW-03"
    table_item = soup.find("span", class_="ts-counter", id="fw:table")
    assert table_item is not None and table_item.get_text() == "FW-04"
    assert table_item.find_parent("td") is not None
    assert soup.find("a", href="#fw:watchdog").get_text() == "FW-01"
    # A section reference shows the heading title.
    assert soup.find("a", href="#sec:counters").get_text() == "Counters"


def test_figure_and_subfigures(load_article: Callable[[str], BeautifulSoup]) -> None:
    soup = load_article("constructs")
    figure = soup.find("figure", id="fig:trace")
    assert figure is not None
    assert figure.find("img") is not None
    caption = figure.find("figcaption")
    assert caption is not None
    assert caption.find("span", class_="ts-caption-label").get_text() == "Figure 1:"
    assert "The watchdog trace." in caption.get_text()

    grid = soup.find("figure", id="fig:views")
    assert grid is not None
    assert "ts-subfigures" in grid.get("class", [])
    assert "--ts-cols:2" in grid.get("style", "")
    assert len(grid.find_all("img")) == 2
    subcaptions = [span.get_text() for span in grid.find_all("span", class_="ts-subcaption")]
    assert subcaptions == ["(a)", "(b)"]

    assert soup.find("a", href="#fig:trace").get_text() == "Figure 1"
    left = soup.find("a", href="#fig:left")
    assert left is not None and left.get_text().startswith("Figure ")
    assert left.get_text().endswith("a")


def test_tables_keep_their_markdown_and_gain_a_caption(
    load_article: Callable[[str], BeautifulSoup],
) -> None:
    soup = load_article("constructs")
    figure = soup.find("figure", id="tbl:findings")
    assert figure is not None and "ts-table" in figure.get("class", [])
    assert figure.find("table") is not None
    caption = figure.find("figcaption")
    assert caption.find("span", class_="ts-caption-label").get_text() == "Table 1:"

    structured = soup.find("table", attrs={"data-ts-table": True})
    assert structured is not None
    cell = structured.find("td")
    assert cell is not None and cell.find("strong") is not None  # inline Markdown in cells
    assert soup.find("a", href="#tbl:findings").get_text() == "Table 1"
    assert soup.find("a", href="#tbl:yaml").get_text() == "Table 2"


def test_listing_and_equation(load_article: Callable[[str], BeautifulSoup]) -> None:
    soup = load_article("constructs")
    listing = soup.find("figure", id="lst:hello")
    assert listing is not None and "ts-listing" in listing.get("class", [])
    assert listing.select("div.highlight, pre") , "the fence renders as code inside the figure"
    assert listing.find("span", class_="ts-caption-label").get_text() == "Listing 1:"
    equation = soup.find("div", id="eq:einstein")
    assert equation is not None and "ts-equation" in equation.get("class", [])
    assert "E = mc^2" in equation.get_text()
    assert soup.find("a", href="#eq:einstein").get_text() == "Equation 1"


def test_callouts(load_article: Callable[[str], BeautifulSoup]) -> None:
    soup = load_article("constructs")
    titles = [p.get_text() for p in soup.select("div.admonition > p.admonition-title")]
    assert "Kept as written" in titles
    assert "Careful" in titles  # ``::: warning`` became ``!!! warning "Careful"``
    warning = soup.find("div", class_="warning")
    assert warning.find("a", href="#fw:watchdog").get_text() == "FW-01"
    theorem = soup.find("div", id="thm:one")
    assert theorem is not None and "theorem" in theorem.get("class", [])
    assert theorem.find("p", class_="admonition-title").get_text() == "Theorem 1 (Pythagoras)"
    assert soup.find("details") is not None  # ``collapsed=true`` → ``???``
    assert soup.find("a", href="#thm:one").get_text() == "Theorem 1"


def test_asides_index_and_glossary(load_article: Callable[[str], BeautifulSoup]) -> None:
    soup = load_article("constructs")
    aside = soup.find("aside", class_="ts-aside")
    assert aside is not None and "A block aside." in aside.get_text()
    inline = soup.find("span", class_="ts-aside")
    assert inline is not None and inline["data-side"] == "left"
    index = soup.find("span", class_="ts-index")
    assert index is not None
    assert index["data-tag"] == "watchdog" and index["data-tag1"] == "timer"
    assert index.get_text() == ""
    abbr = soup.find("abbr")
    assert abbr is not None and abbr.get_text() == "watchdog"
    assert abbr["title"].startswith("A timer")


def test_inline_roles_and_media(load_article: Callable[[str], BeautifulSoup]) -> None:
    soup = load_article("constructs")
    assert soup.find("span", class_="ts-smallcaps").get_text() == "Small caps"
    assert soup.find("kbd") is not None
    assert soup.find("mark", string="marked") is not None
    assert soup.find("u", string="underlined") is not None
    span = soup.find("span", id="span-id")
    assert span is not None and "custom" in span["class"] and span["lang"] == "fr"
    text = soup.get_text()
    assert "on the site" in text
    assert "in print" not in text


def test_unclosed_directive_keeps_its_bytes(load_article: Callable[[str], BeautifulSoup]) -> None:
    soup = load_article("constructs")
    text = soup.get_text()
    assert "::: pkg.module" in text
    assert "handler: python" in text
    link = soup.find_all("a", href="#fw:ota")[-1]
    assert link.get_text() == "FW-02"


def test_site_wide_numbering_across_pages(load_article: Callable[[str], BeautifulSoup]) -> None:
    numbering = load_article("numbering")
    # The series continue in navigation order.
    more = numbering.find("span", class_="ts-counter", id="fw:more")
    assert more is not None and more.get_text() == "FW-05"
    reset = numbering.find("span", class_="ts-counter", id="req:reset")
    assert reset is not None and reset.get_text() == "REQ-100"
    second = numbering.find("figure", id="fig:second")
    label = second.find("span", class_="ts-caption-label").get_text()
    assert label.startswith("Figure ") and label != "Figure 1:"
    # Cross-page references point at the defining page.
    assert numbering.find("a", href="../constructs/#fw:watchdog").get_text() == "FW-01"
    assert numbering.find("a", href="../constructs/#fw:log-wrap").get_text() == "FW-03"
    assert numbering.find("a", href="../constructs/#fig:trace").get_text() == "Figure 1"
    assert numbering.find("a", href="../constructs/#tbl:findings").get_text() == "Table 1"
    assert numbering.find("a", href="../constructs/#sec:counters").get_text() == "Counters"
    assert "[?fw:missing]" in numbering.get_text()
    # And the forward reference from the first page reaches the second.
    constructs = load_article("constructs")
    assert constructs.find("a", href="../numbering/#req:reset").get_text() == "REQ-100"


def test_stylesheet_and_extensions_are_injected(mkdocs_site: Path) -> None:
    css = mkdocs_site / "assets" / "texsmith" / "texsmith.css"
    assert css.exists()
    assert ".ts-aside" in css.read_text(encoding="utf-8")
    html = (mkdocs_site / "constructs" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<link[^>]*href="[^"]*assets/texsmith/texsmith\.css"', html)


def test_index_entries_reach_the_search_index(mkdocs_site: Path) -> None:
    index_path = mkdocs_site / "search" / "search_index.json"
    assert index_path.exists()
    docs = json.loads(index_path.read_text(encoding="utf-8"))["docs"]
    tagged = [doc for doc in docs if "watchdog::timer" in doc.get("tags", [])]
    assert tagged, "the {index}[watchdog][timer] entry was not injected"
    assert all(doc["location"].startswith("constructs/") for doc in tagged)
