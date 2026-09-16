"""The index entries of a site, in the lunr index MkDocs wrote.

One format only: lunr has a ``tags`` field the query reads and Material
boosts. Zensical's ``search.json`` is left exactly as its build wrote it —
the terms reach its search as a page's ``tags``, derived by
:func:`texsmith.site.search.index_terms` while the page renders.
"""

from __future__ import annotations

import json
from pathlib import Path

from texsmith.site import search


PAGE = """\
<h1 id="a">A<a class="headerlink" href="#a" title="Permanent link">&para;</a></h1>
<p>Some text <span class="ts-index" data-tag="cake"></span>.</p>
<h2 id="b">B<a class="headerlink" href="#b" title="Permanent link">&para;</a></h2>
<p>More <span class="ts-index" data-tag="cake" data-tag1="chocolate"></span>.</p>
"""


def lunr_index(site_dir: Path, *locations: str) -> Path:
    """A MkDocs search index holding one entry per location."""
    path = site_dir / search.LUNR_INDEX
    path.parent.mkdir(parents=True, exist_ok=True)
    docs = [{"location": location, "title": "T", "text": "Body."} for location in locations]
    path.write_text(json.dumps({"config": {}, "docs": docs}), encoding="utf-8")
    return path


def disco_index(site_dir: Path, *locations: str) -> Path:
    """A Zensical search index holding one entry per location."""
    path = site_dir / "search.json"
    items = [
        {
            "location": location,
            "level": 1,
            "title": "T",
            "text": "<p>Body.</p>",
            "path": "",
            "tags": [],
        }
        for location in locations
    ]
    path.write_text(json.dumps({"config": {}, "items": items}), encoding="utf-8")
    return path


def entries(path: Path, key: str) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["location"]: entry for entry in data[key]}


def test_the_tags_of_a_page_are_keyed_by_page_and_by_heading() -> None:
    tags = search.SearchTags()

    tags.collect(PAGE, "guide/a/")

    assert tags.tokens("guide/a/") == ["cake"]
    assert tags.tokens("guide/a/#b") == ["cake", "chocolate", "cake::chocolate"]
    assert tags.tokens("guide/b/") == []


def test_the_lunr_index_gains_the_tags_material_searches(tmp_path: Path) -> None:
    index = lunr_index(tmp_path, "guide/a/", "guide/a/#b", "other/")
    tags = search.SearchTags()
    tags.collect(PAGE, "guide/a/")

    assert tags.inject(tmp_path) == 2

    found = entries(index, "docs")
    assert found["guide/a/"]["tags"] == ["cake"]
    assert found["guide/a/#b"]["tags"] == ["cake", "chocolate", "cake::chocolate"]
    assert "tags" not in found["other/"]


def test_the_index_zensical_wrote_is_left_exactly_as_it_is(tmp_path: Path) -> None:
    """Its ``text`` is what the excerpt of a result is built from, in a shadow root.

    Terms put there showed as a tail of unrelated words under the excerpt, and
    no stylesheet a site ships reaches inside that root to hide them. The
    terms go to the ``tags`` of the page instead, which the *Filters* panel
    reads and which the extension writes while the page renders.
    """
    index = disco_index(tmp_path, "guide/a/", "guide/a/#b")
    before = index.read_text(encoding="utf-8")
    tags = search.SearchTags()
    tags.collect(PAGE, "guide/a/")

    assert tags.inject(tmp_path) == 0
    assert index.read_text(encoding="utf-8") == before


def test_only_the_lunr_index_of_a_directory_holding_both_is_patched(tmp_path: Path) -> None:
    lunr = lunr_index(tmp_path, "guide/a/")
    disco = disco_index(tmp_path, "guide/a/")
    before = disco.read_text(encoding="utf-8")
    tags = search.SearchTags()
    tags.collect(PAGE, "guide/a/")

    assert tags.inject(tmp_path) == 1
    assert entries(lunr, "docs")["guide/a/"]["tags"] == ["cake"]
    assert disco.read_text(encoding="utf-8") == before


def test_a_site_without_an_index_is_left_alone(tmp_path: Path) -> None:
    tags = search.SearchTags()
    tags.collect(PAGE, "guide/a/")

    assert tags.inject(tmp_path) == 0


def test_nothing_collected_touches_nothing(tmp_path: Path) -> None:
    index = lunr_index(tmp_path, "guide/a/")
    before = index.read_text(encoding="utf-8")

    assert search.SearchTags().inject(tmp_path) == 0
    assert index.read_text(encoding="utf-8") == before


def test_the_built_site_is_walked_and_every_page_named_as_the_index_names_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "guide" / "a").mkdir(parents=True)
    (tmp_path / "guide" / "a" / "index.html").write_text(PAGE, encoding="utf-8")
    (tmp_path / "index.html").write_text(PAGE, encoding="utf-8")
    (tmp_path / "404.html").write_text("<p>Nothing.</p>", encoding="utf-8")

    tags = search.collect_site(tmp_path)

    assert tags.tokens("guide/a/") == ["cake"]
    assert tags.tokens("guide/a/#b") == ["cake", "chocolate", "cake::chocolate"]
    assert tags.tokens("") == ["cake"]
    assert tags.tokens("#b") == ["cake", "chocolate", "cake::chocolate"]


def test_a_site_without_directory_urls_names_the_file(tmp_path: Path) -> None:
    (tmp_path / "guide").mkdir()
    (tmp_path / "guide" / "a.html").write_text(PAGE, encoding="utf-8")

    tags = search.collect_site(tmp_path, use_directory_urls=False)

    assert tags.tokens("guide/a.html") == ["cake"]
    assert tags.tokens("guide/a.html#b") == ["cake", "chocolate", "cake::chocolate"]


def test_index_terms_keep_the_top_level_of_each_entry_once_and_in_order() -> None:
    assert search.index_terms(PAGE) == ["cake"]

    page = (
        '<span class="ts-index" data-tag="mémoire" data-tag1="allocation"></span>'
        '<span class="ts-index" data-tag="pointeur"></span>'
        '<span class="ts-index" data-tag="mémoire"></span>'
    )

    assert search.index_terms(page) == ["mémoire", "pointeur"]


def test_index_terms_read_the_lowered_markdown_and_the_legacy_hashtag() -> None:
    lowered = (
        'Un <span class="ts-index" data-tag=" byte order "></span> et un '
        '<span class="ts-hashtag" data-tag="endianness" data-main></span>.'
    )

    assert search.index_terms(lowered) == ["byte order", "endianness"]


def test_a_page_without_an_entry_has_no_terms() -> None:
    assert search.index_terms("<p>Nothing to see.</p>") == []
    assert search.index_terms('<span class="ts-index"></span>') == []


def test_an_inverted_entry_is_tagged_by_the_head_it_files_under() -> None:
    """``Boole, George`` files under ``Boole``; a chip reading the whole is a mistake."""
    page = (
        '<span class="ts-index" data-tag="Boole, George"></span>'
        '<span class="ts-index" data-tag="Hanoï, tours de"></span>'
        '<span class="ts-index" data-tag="EOL, fin de ligne"></span>'
        '<span class="ts-index" data-tag="bit, le"></span>'
        '<span class="ts-index" data-tag="pointeur"></span>'
    )

    assert search.index_terms(page) == ["Boole", "Hanoï", "EOL", "bit", "pointeur"]


def test_a_comma_with_nothing_after_it_is_not_an_inversion() -> None:
    assert search.entry_tag("virgule,") == "virgule,"
    assert search.entry_tag("Boole,  George") == "Boole"
    assert search.entry_tag("un, deux, trois") == "un"


def test_two_entries_that_file_under_one_head_make_one_tag() -> None:
    page = (
        '<span class="ts-index" data-tag="Boole, George"></span>'
        '<span class="ts-index" data-tag="Boole"></span>'
    )

    assert search.index_terms(page) == ["Boole"]


def test_a_term_written_with_entities_is_the_term_the_author_wrote() -> None:
    """``#[<complex.h>]`` lowers to ``&lt;complex.h&gt;``; the tag is not that."""
    page = '<span class="ts-index" data-tag="&lt;complex.h&gt;" data-tag1="C&amp;C"></span>'

    assert search.index_terms(page) == ["<complex.h>"]
    assert search.extract_tags(page) == ["<complex.h>", "C&C"]
