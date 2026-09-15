"""``texsmith site assets``: the generated files a Zensical build needs as sources.

The previews themselves are LaTeX builds; the renderer is replaced by a
recorder, so what is checked is which fences are found, where their files go,
what is left alone and what is swept away.
"""

from __future__ import annotations

from pathlib import Path
import textwrap
from typing import Any

import pytest

from texsmith.adapters.plugins import snippet
from texsmith.site import assets
from texsmith.site.config import load_site_config


MKDOCS_YML = """\
site_name: Test site
markdown_extensions:
  - pymdownx.snippets:
      base_path: .
nav:
  - Home: index.md
  - Guide: guide/a.md
"""

INDEX = "# Home\n\nNothing here.\n"

PAGE_WITH_FENCE = textwrap.dedent("""\
    # A

    ```md {.snippet caption="A snippet"}
    Hello
    ```
    """)

PAGE_WITH_INCLUDE = textwrap.dedent("""\
    # A

    ```md {.snippet}
    --8<-- "shared/body.md"
    ```
    """)


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A two-page site whose second page holds one snippet fence."""
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "guide").mkdir(parents=True)
    (docs / "index.md").write_text(INDEX, encoding="utf-8")
    (docs / "guide" / "a.md").write_text(PAGE_WITH_FENCE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def rendered(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Path]]:
    """Record every preview asked for instead of running LaTeX."""
    calls: list[tuple[str, Path]] = []

    def record(block: snippet.SnippetBlock, *, output_dir: Path, **kwargs: Any) -> None:
        del kwargs
        calls.append((block.digest, output_dir))

    monkeypatch.setattr(snippet, "ensure_snippet_assets", record)
    return calls


def generate(root: Path) -> assets.GeneratedAssets:
    return assets.generate(load_site_config(root / "mkdocs.yml"))


def test_every_fence_of_the_site_is_rendered_under_the_documentation_directory(
    site: Path, rendered: list[tuple[str, Path]]
) -> None:
    report = generate(site)

    assert len(rendered) == 1
    assert rendered[0][1] == site / "docs" / "assets" / "snippets"
    assert [(preview.page, preview.built) for preview in report.previews] == [("guide/a.md", True)]
    assert report.previews[0].basename == f"snippet-{rendered[0][0]}"
    assert report.failures == ()


def test_the_stylesheet_is_written_beside_the_pages(
    site: Path, rendered: list[tuple[str, Path]]
) -> None:
    report = generate(site)

    assert report.stylesheet == site / "docs" / assets.CSS_URI
    assert report.stylesheet.read_text(encoding="utf-8") == assets.stylesheet()


def test_a_preview_that_is_already_there_is_not_rendered_again(
    site: Path, rendered: list[tuple[str, Path]]
) -> None:
    digest = generate(site).previews[0].basename
    previews = site / "docs" / "assets" / "snippets"
    for suffix in (".pdf", ".png"):
        (previews / f"{digest}{suffix}").write_text("x", encoding="utf-8")

    report = generate(site)

    assert [preview.built for preview in report.previews] == [False]


def test_a_preview_no_page_asks_for_is_pruned(site: Path, rendered: list[tuple[str, Path]]) -> None:
    previews = site / "docs" / "assets" / "snippets"
    previews.mkdir(parents=True, exist_ok=True)
    (previews / "snippet-stale.pdf").write_text("x", encoding="utf-8")
    (previews / "snippet-stale.png").write_text("x", encoding="utf-8")

    report = generate(site)

    assert report.pruned == ("snippet-stale.pdf", "snippet-stale.png")
    assert not (previews / "snippet-stale.pdf").exists()


def test_a_page_the_navigation_does_not_reach_is_scanned_too(
    site: Path, rendered: list[tuple[str, Path]]
) -> None:
    (site / "docs" / "unlisted.md").write_text(
        PAGE_WITH_FENCE.replace("Hello", "Unlisted"), encoding="utf-8"
    )

    report = generate(site)

    assert sorted(preview.page for preview in report.previews) == ["guide/a.md", "unlisted.md"]


def test_a_fence_splicing_a_file_is_hashed_over_what_the_file_holds(
    site: Path, rendered: list[tuple[str, Path]]
) -> None:
    """``pymdownx.snippets`` puts that text in the fence before the page renders."""
    shared = site / "shared"
    shared.mkdir()
    (shared / "body.md").write_text("Spliced.\n", encoding="utf-8")
    (site / "docs" / "guide" / "a.md").write_text(PAGE_WITH_INCLUDE, encoding="utf-8")

    report = generate(site)

    assert report.failures == ()
    expected = snippet.build_snippet_block(
        "Spliced.\n", language="md", host_path=site / "docs" / "guide" / "a.md"
    )
    assert expected is not None
    assert report.previews[0].basename == f"snippet-{expected.digest}"


def test_a_fence_whose_file_is_missing_is_a_failure_naming_its_page(
    site: Path, rendered: list[tuple[str, Path]]
) -> None:
    (site / "docs" / "guide" / "a.md").write_text(PAGE_WITH_INCLUDE, encoding="utf-8")

    report = generate(site)

    assert report.previews == ()
    assert [failure.page for failure in report.failures] == ["guide/a.md"]
    assert "shared/body.md" in report.failures[0].message


def test_a_preview_that_cannot_be_built_does_not_stop_the_others(
    site: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (site / "docs" / "index.md").write_text(
        PAGE_WITH_FENCE.replace("Hello", "First"), encoding="utf-8"
    )
    seen: list[str] = []

    def explode(block: snippet.SnippetBlock, **kwargs: Any) -> None:
        del kwargs
        seen.append(block.digest)
        if len(seen) == 1:
            raise RuntimeError("no LaTeX here")

    monkeypatch.setattr(snippet, "ensure_snippet_assets", explode)

    report = generate(site)

    assert [failure.message for failure in report.failures] == ["no LaTeX here"]
    assert [preview.page for preview in report.previews] == ["guide/a.md"]


def test_a_preview_whose_build_fails_is_not_pruned(
    site: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The page still links it; a failed rebuild is no reason to take it away."""

    def explode(block: snippet.SnippetBlock, **kwargs: Any) -> None:
        del kwargs
        digest = block.digest
        for suffix in (".pdf", ".png"):
            (site / "docs" / "assets" / "snippets" / f"snippet-{digest}{suffix}").write_text(
                "x", encoding="utf-8"
            )
        raise RuntimeError("no LaTeX here")

    monkeypatch.setattr(snippet, "ensure_snippet_assets", explode)

    report = generate(site)

    assert report.pruned == ()
    assert len(report.failures) == 1


PAGE_WITH_DIAGRAM = "# A\n\n![One](one.drawio)\n\n![Again](one.drawio)\n"


@pytest.fixture
def exported(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, str]]:
    """Answer every draw.io export from a recorder instead of draw.io."""
    calls: list[tuple[Path, str]] = []

    def record(source: Path, *, output_dir: Path, **options: Any) -> Path:
        calls.append((Path(source), str(options.get("format"))))
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{Path(source).stem}.svg"
        target.write_text(f"<svg>{Path(source).name}</svg>", encoding="utf-8")
        return target

    monkeypatch.setattr(assets, "drawio_export", record)
    return calls


def test_every_diagram_an_image_names_is_exported(
    site: Path, rendered: list[tuple[str, Path]], exported: list[tuple[Path, str]]
) -> None:
    """Two images of one diagram on a page ask for one export, and it is an SVG."""
    docs = site / "docs"
    (docs / "guide" / "a.md").write_text(PAGE_WITH_DIAGRAM, encoding="utf-8")
    (docs / "guide" / "one.drawio").write_text("<mxfile/>", encoding="utf-8")
    (docs / "index.md").write_text("# Home\n\n![Two](guide/one.drawio)\n", encoding="utf-8")

    report = generate(site)

    assert [fmt for _source, fmt in exported] == ["svg", "svg"]
    assert [drawing.uri for drawing in report.drawings] == [
        "assets/drawio/guide/one.svg",
        "assets/drawio/guide/one.svg",
    ]
    assert [drawing.page for drawing in report.drawings] == ["index.md", "guide/a.md"]
    assert (docs / "assets" / "drawio" / "guide" / "one.svg").read_text(
        encoding="utf-8"
    ) == "<svg>one.drawio</svg>"
    assert report.failures == ()


def test_an_export_that_is_already_there_is_not_written_again(
    site: Path, rendered: list[tuple[str, Path]], exported: list[tuple[Path, str]]
) -> None:
    docs = site / "docs"
    (docs / "guide" / "a.md").write_text("# A\n\n![One](one.drawio)\n", encoding="utf-8")
    (docs / "guide" / "one.drawio").write_text("<mxfile/>", encoding="utf-8")

    assert [drawing.built for drawing in generate(site).drawings] == [True]
    assert [drawing.built for drawing in generate(site).drawings] == [False]


def test_an_export_no_page_asks_for_is_pruned(
    site: Path, rendered: list[tuple[str, Path]], exported: list[tuple[Path, str]]
) -> None:
    stale = site / "docs" / "assets" / "drawio" / "gone" / "old.svg"
    stale.parent.mkdir(parents=True)
    stale.write_text("<svg/>", encoding="utf-8")

    report = generate(site)

    assert report.pruned == ("assets/drawio/gone/old.svg",)
    assert not stale.exists()
    assert not stale.parent.exists()


def test_a_diagram_that_is_not_there_is_a_failure_naming_its_page(
    site: Path, rendered: list[tuple[str, Path]], exported: list[tuple[Path, str]]
) -> None:
    (site / "docs" / "guide" / "a.md").write_text(
        "# A\n\n![Missing](nowhere.drawio)\n", encoding="utf-8"
    )

    report = generate(site)

    assert report.drawings == ()
    assert [failure.page for failure in report.failures] == ["guide/a.md"]
    assert "guide/nowhere.drawio" in report.failures[0].message


def test_an_export_that_fails_does_not_stop_the_others(
    site: Path, rendered: list[tuple[str, Path]], monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = site / "docs"
    (docs / "index.md").write_text("# Home\n\n![One](one.drawio)\n", encoding="utf-8")
    (docs / "guide" / "a.md").write_text("# A\n\n![Two](two.drawio)\n", encoding="utf-8")
    (docs / "one.drawio").write_text("<mxfile/>", encoding="utf-8")
    (docs / "guide" / "two.drawio").write_text("<mxfile/>", encoding="utf-8")

    def explode(source: Path, *, output_dir: Path, **options: Any) -> Path:
        del options
        if Path(source).stem == "one":
            raise RuntimeError("no draw.io here")
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / "two.svg"
        target.write_text("<svg/>", encoding="utf-8")
        return target

    monkeypatch.setattr(assets, "drawio_export", explode)

    report = generate(site)

    assert [failure.message for failure in report.failures] == ["'one.drawio': no draw.io here"]
    assert [drawing.uri for drawing in report.drawings] == ["assets/drawio/guide/two.svg"]
