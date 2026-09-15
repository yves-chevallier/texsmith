"""The Python-Markdown extension that lowers a TeXSmith site for Zensical.

Zensical's own pieces are used as Zensical uses them: the rendering context
extension carries the page, and the links extension marks the page's own
``Markdown`` instance — the one instance the extension may act on.
"""

from __future__ import annotations

from pathlib import Path
import textwrap
from typing import Any

from markdown import Markdown
import pytest

from texsmith.adapters.plugins import snippet
from texsmith.site import assets, web


context = pytest.importorskip("zensical.extensions.context")
links = pytest.importorskip("zensical.extensions.links")

MKDOCS_YML = """\
site_name: Test site
theme:
  name: material
plugins:
  - texsmith:
      declare:
        counters:
          req:
            name: Requirement
            format: "R-{n:02d}"
markdown_extensions:
  - attr_list
"""

PAGE_A = """\
# A

![x](x.png)

Figure: A figure. {#fig:one}
"""

PAGE_B = """\
# B

As shown in @fig:one, it works.
"""

RENDERING_EXTENSIONS = ("attr_list", "md_in_html", "pymdownx.superfences")


@pytest.fixture(autouse=True)
def _forget_the_site() -> Any:
    """The state is a module-level cache: no test inherits another's."""
    web._state = None
    yield
    web._state = None


def make_site(tmp_path: Path, pages: dict[str, str]) -> dict[str, Any]:
    """Write a site and return the configuration Zensical would hand Python."""
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    docs_dir = tmp_path / "docs"
    for name, text in pages.items():
        path = docs_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return {
        "root_dir": str(tmp_path),
        "docs_dir": "docs",
        "site_dir": "site",
        "use_directory_urls": True,
        "theme": {"language": "en"},
        "extra_css": [assets.CSS_URI],
        "exclude_docs": None,
        "nav": [],
    }


def render(
    config: dict[str, Any],
    src_uri: str,
    text: str,
    *,
    url: str | None = None,
    outer: bool = True,
    with_context: bool = True,
) -> str:
    """Render one page the way ``zensical.markdown.render`` does."""
    page = context.Page(url=src_uri.removesuffix(".md") + "/" if url is None else url, path=src_uri)
    extensions: list[Any] = [web.makeExtension(), *RENDERING_EXTENSIONS]
    if with_context:
        extensions.insert(0, context.ContextExtension(page=page, config=config))
    md = Markdown(extensions=extensions)
    if outer:
        links.LinksExtension(path=src_uri, use_directory_urls=True).extendMarkdown(md)
    return md.convert(text)


def test_nothing_happens_without_a_rendering_context(tmp_path: Path, monkeypatch) -> None:
    config = make_site(tmp_path, {"a.md": PAGE_A})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    html = render(config, "a.md", PAGE_A, with_context=False)

    assert "ts-caption-label" not in html
    assert "Figure: A figure." in html
    assert web._state is None


def test_an_inner_instance_is_left_alone(tmp_path: Path, monkeypatch) -> None:
    """mkdocstrings forwards the context to the instance of every docstring."""
    config = make_site(tmp_path, {"a.md": PAGE_A})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    html = render(config, "a.md", PAGE_A, outer=False)

    assert "ts-caption-label" not in html
    assert web._state is None


def test_a_page_is_lowered(tmp_path: Path, monkeypatch) -> None:
    config = make_site(tmp_path, {"a.md": PAGE_A, "b.md": PAGE_B})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    html = render(config, "a.md", PAGE_A)

    assert '<span class="ts-caption-label">Figure 1:</span>' in html
    assert 'id="fig:one"' in html


def test_a_reference_reaches_the_page_that_defines_the_label(tmp_path: Path, monkeypatch) -> None:
    config = make_site(tmp_path, {"a.md": PAGE_A, "b.md": PAGE_B})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    html = render(config, "b.md", PAGE_B)

    assert '<a href="../a/#fig:one">Figure 1</a>' in html


def test_the_site_language_and_counters_come_from_the_configuration(
    tmp_path: Path, monkeypatch
) -> None:
    """``theme.language`` is Zensical's; ``declare.counters`` is the file's."""
    page = "# T\n\n{counter}(req:boot) is one, and @req:boot names it.\n"
    config = make_site(tmp_path, {"a.md": page})
    config["theme"]["language"] = "fr"
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    html = render(config, "a.md", page)

    assert "R-01" in html
    assert web._state is not None
    assert web._state.index.lang == "fr"
    assert "req" in web._state.index.counters


def test_the_extension_never_writes_the_stylesheet(tmp_path: Path, monkeypatch, caplog) -> None:
    """It is a source of the site now: only ``texsmith site assets`` writes it."""
    config = make_site(tmp_path, {"a.md": PAGE_A})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    with caplog.at_level("WARNING", logger="texsmith.site"):
        render(config, "a.md", PAGE_A)

    assert not (tmp_path / "site").exists()
    assert not (tmp_path / "docs" / assets.CSS_URI).exists()
    assert "texsmith site assets" in caplog.text


def test_the_stylesheet_of_the_documentation_directory_is_left_alone(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    config = make_site(tmp_path, {"a.md": PAGE_A})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)
    assets.write_stylesheet(tmp_path / "docs")

    with caplog.at_level("WARNING", logger="texsmith.site"):
        render(config, "a.md", PAGE_A)

    assert "texsmith site assets" not in caplog.text


def test_a_snippet_fence_becomes_a_preview(tmp_path: Path, monkeypatch) -> None:
    """The previews are rendered by LaTeX; only their placement is checked.

    Under ``docs_dir``, never under the site directory Zensical clears.
    """
    page = textwrap.dedent("""\
        # T

        ```md {.snippet caption="A snippet"}
        Hello
        ```
        """)
    config = make_site(tmp_path, {"guide/a.md": page})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)
    built: list[Path] = []

    def record(block: Any, *, output_dir: Path, **kwargs: Any) -> None:
        del block, kwargs
        built.append(output_dir)

    monkeypatch.setattr(snippet, "ensure_snippet_assets", record)

    html = render(config, "guide/a.md", page)

    assert built == [tmp_path / "docs" / "assets" / "snippets"]
    assert 'class="ts-snippet"' in html
    assert 'src="../../assets/snippets/snippet-' in html
    assert 'href="../../assets/snippets/snippet-' in html


def test_a_snippet_that_cannot_be_built_leaves_the_page_alone(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    page = "# T\n\n```md {.snippet}\nHello\n```\n"
    config = make_site(tmp_path, {"a.md": page})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("no LaTeX here")

    monkeypatch.setattr(snippet, "ensure_snippet_assets", explode)

    with caplog.at_level("WARNING", logger="texsmith.site"):
        html = render(config, "a.md", page)

    assert "ts-snippet" not in html
    assert "no LaTeX here" in caplog.text
    assert "a.md" in caplog.text


def test_the_pre_pass_is_redone_when_a_page_changes(tmp_path: Path, monkeypatch) -> None:
    """``zensical serve`` renders in the process that holds the state."""
    config = make_site(tmp_path, {"a.md": PAGE_A, "b.md": PAGE_B})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    render(config, "b.md", PAGE_B)
    first = web._state
    assert first is not None
    assert web.site_state() is first

    (tmp_path / "docs" / "a.md").write_text(
        PAGE_A.replace("A figure", "Another figure"), encoding="utf-8"
    )
    second = web.site_state()

    assert second is not first
    assert second.index.record("a.md").body != first.index.record("a.md").body


def test_a_new_page_is_picked_up(tmp_path: Path, monkeypatch) -> None:
    config = make_site(tmp_path, {"a.md": PAGE_A})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    web.site_state()
    (tmp_path / "docs" / "b.md").write_text(PAGE_B, encoding="utf-8")

    assert "b.md" in web.site_state().index.records


@pytest.mark.parametrize(
    ("url", "directory_urls", "dest_uri", "prefix"),
    [
        ("", True, "index.html", ""),
        ("guide/a/", True, "guide/a/index.html", "../../"),
        ("index.html", False, "index.html", ""),
        ("guide/a.html", False, "guide/a.html", "../"),
    ],
)
def test_a_page_knows_how_deep_it_sits(
    url: str, directory_urls: bool, dest_uri: str, prefix: str
) -> None:
    resolved = assets.page_dest_uri(url, use_directory_urls=directory_urls)

    assert resolved == dest_uri
    assert assets.asset_prefix(resolved) == prefix


def test_a_drawio_image_points_at_the_exported_svg(tmp_path: Path, monkeypatch) -> None:
    """Zensical has no draw.io viewer; the page shows what the pre-step exported."""
    page = "# T\n\n![Diagram](d.drawio)\n"
    config = make_site(tmp_path, {"guide/a.md": page})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)
    (tmp_path / "docs" / "guide" / "d.drawio").write_text("<mxfile/>", encoding="utf-8")
    export = tmp_path / "docs" / assets.drawio_export_uri("guide/d.drawio")
    export.parent.mkdir(parents=True, exist_ok=True)
    export.write_text("<svg/>", encoding="utf-8")

    html = render(config, "guide/a.md", page)

    assert 'src="../../assets/drawio/guide/d.svg"' in html
    assert ".drawio" not in html


def test_a_drawio_image_without_an_export_keeps_its_tag(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    page = "# T\n\n![Diagram](d.drawio)\n"
    config = make_site(tmp_path, {"guide/a.md": page})
    monkeypatch.setattr("zensical.config.get_config", lambda: config)
    (tmp_path / "docs" / "guide" / "d.drawio").write_text("<mxfile/>", encoding="utf-8")

    with caplog.at_level("WARNING", logger="texsmith.site"):
        html = render(config, "guide/a.md", page)

    assert 'src="../d.drawio"' in html
    assert "texsmith site assets" in caplog.text
    assert "guide/d.drawio" in caplog.text


def test_a_page_the_site_excludes_is_lowered_without_reporting(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """Zensical builds what ``exclude_docs`` removes; those pages are not the site's."""
    page = "# Snippet source\n\nSee [^Key1999] for the details.\n"
    config = make_site(tmp_path, {"a.md": PAGE_A, "assets/part.md": page})
    config["exclude_docs"] = "assets/**/*.md"
    monkeypatch.setattr("zensical.config.get_config", lambda: config)

    with caplog.at_level("WARNING", logger="texsmith.site"):
        html = render(config, "assets/part.md", page)

    assert "Snippet source" in html
    assert "deprecated" not in caplog.text

    # The same page, once the site stops excluding it, reports as any other.
    web._state = None
    config["exclude_docs"] = None
    with caplog.at_level("WARNING", logger="texsmith.site"):
        render(config, "assets/part.md", page)

    assert "deprecated" in caplog.text
