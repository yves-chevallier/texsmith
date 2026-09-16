"""The book builder: its options, its flattening of a navigation, its build.

``texsmith.site.book`` is what both the MkDocs plugin and ``texsmith site
build`` run, so nothing here goes through a generator: a navigation is built
by hand or resolved from a temporary tree, and the settings are read from the
same ``texsmith:`` option mapping ``mkdocs.yml`` carries.
"""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from texsmith.adapters.latex.engines import EngineFeatures
from texsmith.core.config import BookConfig
from texsmith.diagnostics import NullEmitter
from texsmith.passes import snippet as snippet_pass
from texsmith.site.book import (
    FULL_NAVIGATION_ROOT,
    BookBuilder,
    BookError,
    NavEntry,
    book_build_root,
    build_books,
    coerce_paths,
    env_flag_enabled,
    find_item_by_title,
    flatten_navigation,
    load_book_settings,
    normalise_press_overrides,
    normalise_slot_requests,
)
from texsmith.site.config import load_site_config
from texsmith.site.index import SiteIndex, SitePage, site_index
from texsmith.site.nav import NavPage, NavSection, resolve_navigation


def page(src_uri: str, title: str | None = None) -> NavPage:
    return NavPage(title, src_uri, Path("/docs") / src_uri)


def shape(entries: list[NavEntry]) -> list[tuple[str, int, bool, str | None]]:
    """Each entry as ``(title, level, is_page, slot)``."""
    return [(entry.title, entry.level, entry.is_page, entry.slot) for entry in entries]


# The options.


def test_the_defaults_are_one_book_and_the_book_template(tmp_path: Path) -> None:
    settings = load_book_settings(
        {}, project_dir=tmp_path, build_dir=tmp_path / "press", language="fr-FR"
    )

    assert settings.template == "book"
    assert settings.copy_assets is True
    assert settings.embed_documents is False
    assert settings.latex.clean_assets is True
    assert settings.latex.language == "fr-FR"
    assert settings.build_dir == tmp_path / "press"
    assert len(settings.books) == 1
    assert settings.books[0].config.root is None


def test_a_book_keeps_the_options_its_model_has_no_field_for(tmp_path: Path) -> None:
    settings = load_book_settings(
        {
            "clean_assets": False,
            "copy_assets": False,
            "embed_documents": True,
            "template": "article",
            "bibliography": ["refs.bib"],
            "template_overrides": {"cover": "plain"},
            "books": [
                {
                    "title": "A book",
                    "folder": "a-book",
                    "root": FULL_NAVIGATION_ROOT,
                    "base_level": -1,
                    "template": "book",
                    "bibliography": ["extra.bib"],
                    "slots": {"preface": "Home", "backmatter": ["Licence", "Index"]},
                    "paper": "a5",
                    "press": {"paragraph": {"indent": 0}},
                }
            ],
        },
        project_dir=tmp_path,
        build_dir=tmp_path / "press",
    )

    (book,) = settings.books
    assert settings.template == "article"
    assert settings.embed_documents is True
    assert settings.copy_assets is False
    assert settings.latex.clean_assets is False
    assert settings.bibliography == [tmp_path / "refs.bib"]
    assert settings.template_overrides == {"cover": "plain"}
    assert book.config.title == "A book"
    assert book.config.base_level == -1
    assert book.config.folder == Path("a-book")
    assert book.extras.template == "book"
    assert book.extras.bibliography == [tmp_path / "extra.bib"]
    assert book.extras.slots == {"preface": {"home"}, "backmatter": {"licence", "index"}}
    assert book.extras.press == {"paragraph": {"indent": 0}, "paper": "a5"}


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"books": "one"}, "must be a list"),
        ({"books": ["one"]}, "is not a mapping"),
        ({"books": [{"nonsense": 1}]}, "Invalid book configuration #1"),
    ],
)
def test_a_broken_books_option_is_a_book_error(tmp_path: Path, options: dict, message: str) -> None:
    with pytest.raises(BookError, match=message):
        load_book_settings(options, project_dir=tmp_path, build_dir=tmp_path / "press")


def test_the_build_directory_is_resolved_against_the_project(tmp_path: Path) -> None:
    assert book_build_root({}, tmp_path) == (tmp_path / "press").resolve()
    assert book_build_root({"build_dir": "out/pdf"}, tmp_path) == (tmp_path / "out/pdf").resolve()
    absolute = tmp_path / "elsewhere"
    assert book_build_root({"build_dir": str(absolute)}, tmp_path) == absolute


def test_slot_and_press_options_that_make_no_sense_are_ignored() -> None:
    assert normalise_slot_requests(None) == {}
    assert normalise_slot_requests("preface") == {}
    assert normalise_slot_requests({"": "Home", "preface": 12}) == {}
    assert normalise_press_overrides("a5") == {}
    assert normalise_press_overrides(None, "a5") == {"paper": "a5"}


def test_a_relative_path_resolves_against_the_project(tmp_path: Path) -> None:
    assert coerce_paths(["a/b.bib"], relative_to=tmp_path) == [(tmp_path / "a/b.bib").resolve()]
    assert coerce_paths([Path("/tmp/x.bib")], relative_to=tmp_path) == [Path("/tmp/x.bib")]


def test_the_build_flag_reads_the_usual_spellings() -> None:
    assert env_flag_enabled("1") is True
    assert env_flag_enabled("true") is True
    assert env_flag_enabled("off") is False
    assert env_flag_enabled("") is False
    assert env_flag_enabled(None) is False


# The flattening.


def navigation_items() -> tuple:
    return (
        page("index.md", "Home"),
        NavSection(
            "Guide",
            (page("guide/one.md", "One"), page("guide/two.md", "Two")),
            index=page("guide/index.md", "Guide index"),
        ),
        NavSection("About", (page("about/licence.md", "Licence"),)),
    )


def test_a_section_becomes_a_heading_and_its_index_the_first_chapter() -> None:
    config = BookConfig(base_level=0, root=FULL_NAVIGATION_ROOT)
    entries: list[NavEntry] = []
    for item in navigation_items():
        entries.extend(flatten_navigation(item, config))

    assert shape(entries) == [
        ("Home", 0, True, None),
        ("Guide", 0, False, None),
        ("Guide index", 1, True, None),
        ("One", 1, True, None),
        ("Two", 1, True, None),
        ("About", 0, False, None),
        ("Licence", 1, True, None),
    ]


def test_a_slot_selector_routes_a_title_and_everything_under_it() -> None:
    config = BookConfig(base_level=0)
    slots = normalise_slot_requests({"preface": "Home", "backmatter": ["about"]})
    entries: list[NavEntry] = []
    for item in navigation_items():
        entries.extend(flatten_navigation(item, config, slots))

    assert [(entry.title, entry.slot) for entry in entries] == [
        ("Home", "preface"),
        ("Guide", None),
        ("Guide index", None),
        ("One", None),
        ("Two", None),
        ("About", "backmatter"),
        ("Licence", "backmatter"),
    ]


def test_one_root_section_is_the_whole_book() -> None:
    config = BookConfig(base_level=-1)
    root = find_item_by_title(navigation_items(), "Guide")

    assert root is not None
    assert shape(flatten_navigation(root, config)) == [
        ("Guide", -1, False, None),
        ("Guide index", 0, True, None),
        ("One", 0, True, None),
        ("Two", 0, True, None),
    ]


def test_a_title_no_navigation_item_carries_is_not_found() -> None:
    assert find_item_by_title(navigation_items(), "Nowhere") is None


def test_front_and_back_matter_titles_move_a_page_and_its_children() -> None:
    config = BookConfig(base_level=0, frontmatter=["Home"], backmatter=["About"])
    entries: list[NavEntry] = []
    for item in navigation_items():
        entries.extend(flatten_navigation(item, config))

    assert [(entry.title, entry.part) for entry in entries] == [
        ("Home", "frontmatter"),
        ("Guide", "mainmatter"),
        ("Guide index", "mainmatter"),
        ("One", "mainmatter"),
        ("Two", "mainmatter"),
        ("About", "backmatter"),
        ("Licence", "backmatter"),
    ]


def test_an_index_page_is_the_foreword_when_the_book_asks_for_one() -> None:
    config = BookConfig(base_level=0, index_is_foreword=True, drop_title_index=True)
    entries = flatten_navigation(navigation_items()[1], config)

    index_entry = entries[1]
    assert index_entry.title == "Guide index"
    assert index_entry.numbered is False
    assert index_entry.drop_title is True
    # The rest of the section keeps the numbering the foreword dropped.
    assert [entry.numbered for entry in entries] == [True, False, True, True]


# The build.


MKDOCS_YML = """\
site_name: Two pages
site_author: A. Author
plugins:
  - texsmith:
      build_dir: press
      books:
        - title: The Book
          folder: the-book
          root: "__texsmith_full_navigation__"
          base_level: -1
nav:
  - Home: index.md
  - Guide: guide/one.md
"""

INDEX_MD = "# Home\n\nA first page, pointing at @sec:one.\n"
ONE_MD = "# One {#sec:one}\n\nA second page.\n"


@pytest.fixture
def site(tmp_path: Path) -> Path:
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "guide").mkdir(parents=True)
    (docs / "index.md").write_text(INDEX_MD, encoding="utf-8")
    (docs / "guide" / "one.md").write_text(ONE_MD, encoding="utf-8")
    return tmp_path


def test_a_two_page_site_becomes_one_tex_with_both_pages(site: Path) -> None:
    (result,) = build_books(load_site_config(site / "mkdocs.yml"), compile_pdf=False)

    assert result.title == "The Book"
    assert result.pdf_path is None
    assert result.output_root == site / "press" / "the-book"
    assert result.tex_path == result.output_root / "the-book.tex"

    body = result.tex_path.read_text(encoding="utf-8")
    assert "\\input{pages/index-md.tex}" in body
    assert "\\input{pages/guide-one-md.tex}" in body
    # The cover falls back to the site's own metadata.
    assert "A. Author" in body
    # Each page's exact input is written next to the output.
    assert (result.output_root / "sources" / "index.md").is_file()
    assert (result.output_root / "sources" / "guide" / "one.md").is_file()


def test_a_fence_names_its_sources_from_the_page_that_holds_it(
    site: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``.snippet`` fence is read from the page, not from the copy of it.

    The book writes each page's exact input under ``sources/``; a fence's
    ``cwd`` and ``sources`` are written against the page the author wrote
    them in, and nothing of what they name sits under the build directory.
    """
    letter = site / "examples" / "letter"
    letter.mkdir(parents=True)
    (letter / "letter.md").write_text("# Letter\n\nDear reader.\n", encoding="utf-8")
    (site / "docs" / "guide" / "one.md").write_text(
        "# One {#sec:one}\n\n"
        '```yaml {.snippet caption="Download"}\n'
        "cwd: ../../examples/letter\n"
        "sources:\n"
        "  - letter.md\n"
        "```\n",
        encoding="utf-8",
    )

    seen: list[Path] = []

    def render(block: object, *, output_dir: Path, source_path: Path, emitter: object):
        from texsmith.adapters.plugins.snippet import SnippetAssets

        del emitter
        seen.append(source_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf = output_dir / "snippet.pdf"
        png = output_dir / "snippet.png"
        pdf.write_bytes(b"%PDF-1.4")
        png.write_bytes(b"\x89PNG\r\n")
        return SnippetAssets(pdf=pdf, png=png)

    monkeypatch.setattr(snippet_pass, "render_snippet_assets", render)

    (result,) = build_books(load_site_config(site / "mkdocs.yml"), compile_pdf=False)

    page_tex = (result.output_root / "pages" / "guide-one-md.tex").read_text(encoding="utf-8")
    assert seen == [site / "docs" / "guide" / "one.md"]
    assert "\\tsfigure" in page_tex or "includegraphics" in page_tex
    assert ".snippet" not in page_tex


def test_a_page_reaches_the_book_as_the_file_holds_it(site: Path) -> None:
    """One book path: the file, never what a site generator handed the lowering.

    Under MkDocs the plugin lowers a page after every other plugin rewrote
    its Markdown (``mkdocs-drawio`` appends ``.off-glb`` to an image,
    ``macros`` expands a moustache), and the book used to read that stored
    text. It reads the file, so the two commands write the same ``.tex``.
    """
    config = load_site_config(site / "mkdocs.yml")
    index = site_index({}, project_dir=site)
    page = SitePage(src_uri="guide/one.md", abs_src_path=site / "docs" / "guide" / "one.md")
    index.prepass([SitePage(src_uri="index.md", abs_src_path=site / "docs" / "index.md"), page])
    lowered = index.lower(page, ONE_MD.replace("A second page.", "A REWRITTEN page."))
    assert lowered is not None and "REWRITTEN" in lowered.text

    settings = load_book_settings(
        config.plugin, project_dir=site, build_dir=site / "press", docs_dir=config.docs_dir
    )
    builder = BookBuilder(settings, index=index)
    (book,) = builder.prepare(
        resolve_navigation(config.docs_dir, config.nav or None, exclude_docs=config.exclude_docs)
    )
    result = builder.render(book)

    page_tex = (result.output_root / "pages" / "guide-one-md.tex").read_text(encoding="utf-8")
    assert "A second page." in page_tex
    assert "REWRITTEN" not in page_tex


def test_a_diagnostic_of_a_book_page_names_the_page(
    site: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The page is parsed under its own path, not under the copy in ``sources/``."""
    (site / "docs" / "guide" / "one.md").write_text(
        "---\ntitle: One\n---\n\n# One {#sec:one}\n\nSee @fw:nowhere.\n", encoding="utf-8"
    )

    with caplog.at_level(logging.WARNING, logger="texsmith.site"):
        build_books(load_site_config(site / "mkdocs.yml"), compile_pdf=False)

    messages = [record.getMessage() for record in caplog.records]
    assert any("docs/guide/one.md:7:6: warning ref-unresolved" in message for message in messages)
    assert not any("sources/" in message for message in messages)


def test_a_diagnostic_of_an_appended_snippet_names_the_appended_file(
    site: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """``auto_append`` lines fall past the page's end; they keep their own file."""
    (site / "mkdocs.yml").write_text(
        MKDOCS_YML.replace(
            "nav:",
            "markdown_extensions:\n"
            "  - pymdownx.snippets:\n"
            "      auto_append:\n"
            "        - shared/tail.md\n"
            "nav:",
        ),
        encoding="utf-8",
    )
    shared = site / "shared"
    shared.mkdir()
    (shared / "tail.md").write_text("*[HTTP]: Hypertext\n\nSee @fw:nowhere.\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="texsmith.site"):
        build_books(load_site_config(site / "mkdocs.yml"), compile_pdf=False)

    messages = [record.getMessage() for record in caplog.records]
    assert any("shared/tail.md:3:6: warning ref-unresolved" in message for message in messages)
    assert not any("one.md:" in message and "ref-unresolved" in message for message in messages)


def test_an_anchor_of_another_page_is_a_reference_style_link_target(site: Path) -> None:
    """``[text][id]`` reaches an anchor of a sibling page (the book is one document)."""
    docs = site / "docs"
    (docs / "guide" / "one.md").write_text(
        "# One {#sec:one}\n\nA []{#cheese} anchor and a [span]{#brie}.\n",
        encoding="utf-8",
    )
    (docs / "index.md").write_text(
        "# Home\n\nSee the [academic paper][cheese] and the [wheel][brie], "
        "but @cheese and @brie and @nowhere.\n",
        encoding="utf-8",
    )

    (result,) = build_books(load_site_config(site / "mkdocs.yml"), compile_pdf=False)

    page_tex = (result.output_root / "pages" / "index-md.tex").read_text(encoding="utf-8")
    assert "\\hyperref[cheese]{academic paper}" in page_tex
    assert "\\hyperref[brie]{wheel}" in page_tex
    # A page that defines the anchor carries the label the link points at.
    one_tex = (result.output_root / "pages" / "guide-one-md.tex").read_text(encoding="utf-8")
    assert "\\label{cheese}" in one_tex
    # ``@key`` writes text, not a link: a sibling anchor shows what a local
    # one shows — its span text, else its id — and an unknown key stays
    # visibly unresolved.
    assert "but cheese and span and [?nowhere]" in page_tex


def test_a_book_reads_its_cover_and_imprint_from_the_project(site: Path) -> None:
    """A path in ``mkdocs.yml`` starts where ``copy_files`` starts: the project."""
    tex = site / "tex"
    tex.mkdir()
    (tex / "cover.tex").write_text(
        "\\begin{titlingpage}HEIG-VD\\end{titlingpage}", encoding="utf-8"
    )
    (tex / "imprint.tex").write_text("Imprime en Suisse.", encoding="utf-8")
    config = load_site_config(site / "mkdocs.yml")
    config.plugin["books"][0]["press"] = {
        "titlepage": "tex/cover.tex",
        "imprint": "tex/imprint.tex",
        "preamble": "\\usepackage{heiglogo}",
    }

    (result,) = build_books(config, compile_pdf=False)

    body = result.tex_path.read_text(encoding="utf-8")
    assert "\\begin{titlingpage}HEIG-VD\\end{titlingpage}" in body
    assert "Imprime en Suisse." in body
    assert "\\usepackage{heiglogo}" in body
    assert "\\maketitle" not in body


def test_the_build_directory_can_be_moved_and_one_book_named(site: Path) -> None:
    config = load_site_config(site / "mkdocs.yml")
    elsewhere = site / "build" / "books"

    (result,) = build_books(config, compile_pdf=False, build_dir=elsewhere, title="the book")

    assert result.output_root == elsewhere / "the-book"
    with pytest.raises(BookError, match="No book titled"):
        build_books(config, compile_pdf=False, title="Another")


def test_a_disabled_plugin_builds_nothing(tmp_path: Path) -> None:
    (tmp_path / "mkdocs.yml").write_text(
        textwrap.dedent("""\
            site_name: Off
            plugins:
              - texsmith:
                  enabled: false
            """),
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")

    with pytest.raises(BookError, match="disabled"):
        build_books(load_site_config(tmp_path / "mkdocs.yml"), compile_pdf=False)


def test_a_root_that_names_nothing_is_reported(site: Path) -> None:
    config = load_site_config(site / "mkdocs.yml")
    config.plugin["books"][0]["root"] = "Nowhere"

    with pytest.raises(BookError, match="Root section 'Nowhere' not found"):
        build_books(config, compile_pdf=False)


# What the builder may import.

NO_MKDOCS = """\
import sys


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name == "mkdocs" or name.startswith("mkdocs."):
            raise ImportError(f"{name} is blocked")
        return None


sys.meta_path.insert(0, Blocker())

from texsmith.site.book import build_books  # noqa: E402,F401
from texsmith.ui.cli.commands.site import site_build  # noqa: E402,F401

leaked = sorted(name for name in sys.modules if name.split(".")[0] == "mkdocs")
assert not leaked, leaked
"""


def test_the_book_builds_with_no_mkdocs_on_its_path() -> None:
    """``texsmith site build`` runs beside Zensical, which does not install MkDocs."""
    result = subprocess.run(
        [sys.executable, "-c", NO_MKDOCS], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


# The engine's side of the bundle.


def builder(tmp_path: Path) -> BookBuilder:
    settings = load_book_settings({}, project_dir=tmp_path, build_dir=tmp_path / "press")
    return BookBuilder(settings, index=SiteIndex())


def page_entry(src_uri: str, abs_src: Path) -> NavEntry:
    """One chapter of a book, the way ``flatten_navigation`` builds it."""
    return NavEntry(
        title=src_uri,
        level=0,
        numbered=True,
        drop_title=False,
        part="mainmatter",
        is_page=True,
        src_uri=src_uri,
        abs_src_path=abs_src,
    )


def test_a_latexmk_project_gets_the_rc_file_the_engine_needs(tmp_path: Path) -> None:
    tex_path = tmp_path / "press" / "book.tex"
    tex_path.parent.mkdir(parents=True)
    tex_path.write_text("", encoding="utf-8")
    features = EngineFeatures(
        requires_shell_escape=False, bibliography=False, has_index=False, has_glossary=False
    )

    rc_path = builder(tmp_path)._ensure_latexmkrc(
        tex_path=tex_path, engine="lualatex", features=features
    )

    assert rc_path is not None and rc_path.exists()
    content = rc_path.read_text(encoding="utf-8")
    assert "lualatex" in content
    assert "book" in content


def test_the_bundle_says_how_to_compile_it_by_hand(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    output_root = tmp_path / "press" / "book"
    with caplog.at_level("INFO", logger="texsmith.site"):
        builder(tmp_path)._announce_latexmk_command(output_root, output_root / "texsmith-docs.tex")

    message = caplog.records[-1].getMessage()
    assert "Press bundle ready" in message
    assert "latexmk -cd press/book/texsmith-docs.tex" in message


def test_the_auto_appended_snippet_follows_every_page_s_body(tmp_path: Path) -> None:
    """``pymdownx.snippets``' ``auto_append`` reaches the sources the PDF reads.

    An abbreviation reaches the glossary only through a definition in the
    page that uses it, so the site's shared list has to follow every body —
    which is exactly what the extension does on the web.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    page = docs / "intro.md"
    page.write_text("---\ntitle: Intro\n---\n\n# Intro\n\nA POSIX system.\n", encoding="utf-8")
    appended = tmp_path / "abbreviations.md"
    appended.write_text("*[POSIX]: Portable Operating System Interface\n", encoding="utf-8")

    settings = load_book_settings(
        {},
        project_dir=tmp_path,
        build_dir=tmp_path / "press",
        snippet_auto_append=[appended],
    )
    index = SiteIndex(project_dir=tmp_path)
    index.prepass([SitePage(src_uri="intro.md", abs_src_path=page)])
    record = index.record("intro.md")
    assert record is not None

    BookBuilder(settings, index=index)._page_document(
        page_entry("intro.md", page),
        abs_src=page,
        base_level=0,
        output_root=tmp_path / "press" / "book",
        emitter=NullEmitter(),
    )

    written = tmp_path / "press" / "book" / "sources" / "intro.md"
    source = written.read_text(encoding="utf-8")
    assert source.startswith("---\ntitle: Intro\n")
    assert "A POSIX system." in source
    assert source.rstrip().endswith("*[POSIX]: Portable Operating System Interface")


def test_a_page_source_carries_nothing_extra_without_auto_append(tmp_path: Path) -> None:
    """A site with no ``auto_append`` writes the page's own body and no more."""
    docs = tmp_path / "docs"
    docs.mkdir()
    page = docs / "intro.md"
    page.write_text("# Intro\n\nBody.\n", encoding="utf-8")

    index = SiteIndex(project_dir=tmp_path)
    index.prepass([SitePage(src_uri="intro.md", abs_src_path=page)])
    record = index.record("intro.md")
    assert record is not None

    builder(tmp_path)._page_document(
        page_entry("intro.md", page),
        abs_src=page,
        base_level=0,
        output_root=tmp_path / "press" / "book",
        emitter=NullEmitter(),
    )

    written = tmp_path / "press" / "book" / "sources" / "intro.md"
    assert written.read_text(encoding="utf-8") == "# Intro\n\nBody.\n"
