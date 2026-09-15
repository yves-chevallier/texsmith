"""The index entries of a site, in the search index its generator wrote.

Two formats: MkDocs' lunr index, which has a searchable ``tags`` field, and
Zensical's, whose ``tags`` are filter chips and whose ``text`` is what a query
reads. One collector fills both.
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
    path = site_dir / search.DISCO_INDEX
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


def test_the_disco_index_gains_the_tags_in_the_text_it_searches(tmp_path: Path) -> None:
    """``tags`` there is a filter facet; the query reads ``title``, ``text``, ``path``."""
    index = disco_index(tmp_path, "guide/a/", "guide/a/#b")
    tags = search.SearchTags()
    tags.collect(PAGE, "guide/a/")

    assert tags.inject(tmp_path) == 2

    found = entries(index, "items")
    assert found["guide/a/"]["text"] == '<p>Body.</p> <span class="ts-index">cake</span>'
    assert found["guide/a/"]["tags"] == []
    assert "cake::chocolate" in found["guide/a/#b"]["text"]


def test_a_second_run_replaces_what_the_first_one_wrote(tmp_path: Path) -> None:
    index = disco_index(tmp_path, "guide/a/")
    tags = search.SearchTags()
    tags.collect(PAGE, "guide/a/")

    tags.inject(tmp_path)
    tags.inject(tmp_path)

    text = entries(index, "items")["guide/a/"]["text"]
    assert text.count("ts-index") == 1
    assert text == '<p>Body.</p> <span class="ts-index">cake</span>'


def test_both_indexes_of_one_directory_are_patched(tmp_path: Path) -> None:
    lunr = lunr_index(tmp_path, "guide/a/")
    disco = disco_index(tmp_path, "guide/a/")
    tags = search.SearchTags()
    tags.collect(PAGE, "guide/a/")

    assert tags.inject(tmp_path) == 2
    assert entries(lunr, "docs")["guide/a/"]["tags"] == ["cake"]
    assert "cake" in entries(disco, "items")["guide/a/"]["text"]


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
