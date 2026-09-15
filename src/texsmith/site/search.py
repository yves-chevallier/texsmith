"""Index entries in the search index of a built site (``web-profile.md`` step 3).

The lowering renders ``{index}[a][b]`` as ``<span class="ts-index"
data-tag="a" data-tag1="b"></span>``: a marker the page shows nothing of, so
the term is searchable without being printed. :class:`SearchTags` collects
those markers per page and per section heading, and appends the terms to the
index the generator wrote.

Two generators, two index formats, one difference that matters:

* **MkDocs** writes ``search/search_index.json``, a list under ``docs`` whose
  entries lunr indexes with a ``tags`` field — Material's search boosts it
  above everything else, so a term lands there.
* **Zensical** writes ``search.json``, a list under ``items`` that already
  carries a ``tags`` list on every entry. Its front end does *not* search
  that field: the query is parsed against ``title``, ``text`` and ``path``
  (``assets/javascripts/workers/search.*.min.js``), while ``tags`` feeds the
  filter chips, an aggregation of exact values the reader clicks. Index
  terms put there would not be found by typing them, and would flood the
  filter list with one chip per term. They go into ``text`` instead, the
  field the query does read, wrapped in a ``ts-index`` span so a second run
  replaces them rather than appending them twice.

Both generators spell a location the same way — ``""`` for the home page,
``guide/mkdocs/`` for a page, ``guide/mkdocs/#anchor`` for a heading — so one
normalisation covers both, and matching is exact.

Nothing here imports a site generator: the MkDocs plugin feeds the collector
from ``on_page_content`` and injects in ``on_post_build``, and ``texsmith
site search`` walks the built site instead, after Zensical is done.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
import json
from pathlib import Path
import re
from typing import Any

from texsmith.site.assets import page_url


__all__ = [
    "DISCO_INDEX",
    "LUNR_INDEX",
    "SearchTags",
    "collect_site",
    "expand_search_terms",
    "extract_tags",
]

#: MkDocs' lunr index, relative to the site directory.
LUNR_INDEX = "search/search_index.json"

#: Zensical's index, relative to the site directory.
DISCO_INDEX = "search.json"

RE_HEADERLINK = re.compile(r'<a\s+[^>]*headerlink[^>]*href="(#[^"]+)"[^>]*>')
RE_HASHTAG = re.compile(r"<span\s+[^>]*class=\"[^\"]*ts-(?:hashtag|index)[^\"]*\"[^>]*>")
RE_DATA_TAG = re.compile(r"data-tag\d*=\"([^\"]+)\"")

#: What a previous injection left in an entry's ``text``, replaced on the next one.
RE_INJECTED = re.compile(r"\s*<span class=\"ts-index\">[^<]*</span>")


def expand_search_terms(tags: Iterable[str]) -> list[str]:
    """Return a list of search tokens derived from the hierarchy of tags."""
    tokens: list[str] = []
    collected: set[str] = set()
    hierarchy: list[str] = []
    for tag in tags:
        hierarchy.append(tag)
        direct = tag.strip()
        if direct and direct not in collected:
            collected.add(direct)
            tokens.append(direct)
        composite = "::".join(hierarchy)
        if composite not in collected:
            collected.add(composite)
            tokens.append(composite)
    return tokens


def extract_tags(fragment: str) -> list[str]:
    """The ``data-tag`` values of one ``ts-index`` span, in order."""
    return [value.strip() for value in RE_DATA_TAG.findall(fragment) if value.strip()]


def normalise_location(location: str) -> str:
    """One spelling for a location, whatever the generator wrote.

    A page is its directory (``guide/mkdocs/``) with directory URLs and its
    file (``guide/mkdocs.html``) without them; both generators agree, and the
    home page is the empty string on both. What differs between a collected
    location and an indexed one is at most a trailing ``index.html`` and a
    leading ``./``, so those go.
    """
    path, sep, anchor = location.partition("#")
    if path.startswith("./"):
        path = path[2:]
    if path == "index.html":
        path = ""
    elif path.endswith("/index.html"):
        path = path[: -len("index.html")]
    return f"{path}{sep}{anchor}"


class SearchTags:
    """Collect ``ts-index`` spans per location and inject them into the index."""

    def __init__(self) -> None:
        self._collected: dict[str, set[tuple[str, ...]]] = defaultdict(set)

    def clear(self) -> None:
        """Forget everything collected so far; a build starts empty."""
        self._collected.clear()

    def __bool__(self) -> bool:
        return bool(self._collected)

    def collect(self, html: str, page_url: str) -> None:
        """Collect the tags of one rendered page, per section heading past the first."""
        base = page_url or ""
        anchor = ""
        heading_count = 0

        for line in html.split("\n"):
            if header := RE_HEADERLINK.search(line):
                anchor = header.group(1)
                heading_count += 1

            for match in RE_HASHTAG.findall(line):
                tags = extract_tags(match)
                if not tags:
                    continue
                location = f"{base}{anchor}" if anchor and heading_count > 1 else base
                self._collected[normalise_location(location)].add(tuple(tags))

    def tokens(self, location: str) -> list[str]:
        """The search tokens collected for one location, deduplicated and ordered."""
        tag_sets = self._collected.get(normalise_location(location))
        if not tag_sets:
            return []
        tokens: list[str] = []
        seen: set[str] = set()
        for tags in sorted(tag_sets):
            for token in expand_search_terms(tags):
                if token not in seen:
                    seen.add(token)
                    tokens.append(token)
        return tokens

    def inject(self, site_dir: Path) -> int:
        """Append the collected tags to whichever index the site carries.

        Returns how many entries gained terms, over both formats: a site
        built by MkDocs has the lunr index, one built by Zensical the Disco
        index, and a directory holding both is patched twice.
        """
        if not self._collected:
            return 0
        root = Path(site_dir)
        return self._patch(root / LUNR_INDEX, "docs", self._append_tags) + self._patch(
            root / DISCO_INDEX, "items", self._append_text
        )

    def _patch(
        self,
        path: Path,
        key: str,
        append: Callable[[dict[str, Any], list[str]], bool],
        /,
    ) -> int:
        """Rewrite one index file, ``append`` deciding where the terms land."""
        if not path.is_file():
            return 0
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries = data.get(key) if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return 0

        patched = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            location = entry.get("location")
            if not isinstance(location, str):
                continue
            tokens = self.tokens(location)
            if tokens and append(entry, tokens):
                patched += 1

        if patched:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle)
        return patched

    @staticmethod
    def _append_tags(entry: dict[str, Any], tokens: list[str]) -> bool:
        """lunr: the terms join the ``tags`` field Material searches and boosts."""
        existing = entry.setdefault("tags", [])
        if not isinstance(existing, list):
            return False
        seen = {str(value) for value in existing}
        payload = [token for token in tokens if token not in seen]
        if not payload:
            return False
        existing.extend(payload)
        return True

    @staticmethod
    def _append_text(entry: dict[str, Any], tokens: list[str]) -> bool:
        """Disco: the terms join ``text``, the field its query actually reads.

        The span is the marker of a previous injection as much as it is
        markup: patching a site twice replaces it instead of piling terms up,
        and the entry's ``text`` already holds the page's own HTML, so one
        more element changes nothing for the reader.
        """
        text = entry.get("text")
        if not isinstance(text, str):
            return False
        stripped = RE_INJECTED.sub("", text)
        entry["text"] = f'{stripped} <span class="ts-index">{" ".join(tokens)}</span>'
        return True


def collect_site(site_dir: Path, *, use_directory_urls: bool = True) -> SearchTags:
    """Collect the ``ts-index`` markers of every page of a built site.

    The page's URL is what the index keys an entry by, and the built file is
    all there is left to read it from: it is the inverse of
    :func:`texsmith.site.assets.page_dest_uri`.
    """
    root = Path(site_dir)
    tags = SearchTags()
    for path in sorted(root.rglob("*.html")):
        try:
            html = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - unreadable page
            continue
        if "ts-index" not in html:
            continue
        dest_uri = path.relative_to(root).as_posix()
        tags.collect(html, page_url(dest_uri, use_directory_urls=use_directory_urls))
    return tags
