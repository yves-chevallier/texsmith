"""Index entries in the search index of a built site (``web-profile.md`` step 3).

The lowering renders ``{index}[a][b]`` as ``<span class="ts-index"
data-tag="a" data-tag1="b"></span>``: a marker the page shows nothing of, so
the term is searchable without being printed. :class:`SearchTags` collects
those markers per page and per section heading, and adds the terms to the
``tags`` field of MkDocs' ``search/search_index.json`` — the field lunr
indexes and Material boosts above every other. That is the whole of what is
patched into an index after a build.

**Zensical is not patched.** Its ``search.json`` carries a ``tags`` list on
every entry, and those are not searched: the query is parsed against
``title``, ``text`` and ``path`` (``assets/javascripts/workers/search.*.min.js``)
while ``tags`` feeds the *Filters* panel, an aggregation of exact values the
reader clicks. Putting the terms into ``text`` instead did make them typable,
and it cost more than it bought:

* the search dialog builds a result's excerpt from ``text``, and it renders
  it inside a **shadow root**, where no stylesheet a site ships can reach it.
  The injected span keeps its class and shows its terms as a tail of unrelated
  words under the excerpt; hiding it is not possible from the outside, and a
  hidden one would leave a result whose match cannot be seen at all;
* a term is almost always in the prose of the section that declares it —
  measured on a 142-page site, 91% of the entries word for word and 96% down
  to the word — so the query already finds the section without any help;
* what the remaining few buy is an *inverted* spelling (``Hanoï, tours de``),
  which nobody types, when the natural order is in the prose anyway;
* and a term that is nowhere in the prose is still typable, because the tags
  listing page is a page of the site like any other: a query for it returns
  the listing, which says which pages carry it.

So browsing is what the terms do on Zensical, and browsing only: the web
extension derives them into a page's ``tags`` metadata with
:func:`index_terms` while the page renders, and the generator turns those
into the chips under the content, the entries of the tags listing and the
*Filters* panel of the search.

Both generators spell a location the same way — ``""`` for the home page,
``guide/mkdocs/`` for a page, ``guide/mkdocs/#anchor`` for a heading — so one
normalisation covers both, and matching is exact.

Nothing here imports a site generator: the MkDocs plugin feeds the collector
from ``on_page_content`` and injects in ``on_post_build``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from html import unescape
import json
from pathlib import Path
import re
from typing import Any


__all__ = [
    "LUNR_INDEX",
    "SearchTags",
    "entry_tag",
    "expand_search_terms",
    "extract_tags",
    "index_terms",
]

#: MkDocs' lunr index, relative to the site directory.
LUNR_INDEX = "search/search_index.json"

RE_HEADERLINK = re.compile(r'<a\s+[^>]*headerlink[^>]*href="(#[^"]+)"[^>]*>')
RE_HASHTAG = re.compile(r"<span\s+[^>]*class=\"[^\"]*ts-(?:hashtag|index)[^\"]*\"[^>]*>")
RE_DATA_TAG = re.compile(r"data-tag\d*=\"([^\"]+)\"")

#: The top level of one entry: ``data-tag``, never a numbered ``data-tag1``.
RE_TOP_TAG = re.compile(r"data-tag=\"([^\"]+)\"")

#: An inverted index spelling: the head an entry is filed under, a comma, and
#: the qualifier that follows it — ``Boole, George``, ``Hanoï, tours de``,
#: ``bit, le``, ``EOL, fin de ligne``.
RE_INVERTED = re.compile(r"^(?P<head>[^,]+),\s*\S")


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
    """The ``data-tag`` values of one ``ts-index`` span, in order.

    The attribute holds HTML, so ``#[<complex.h>]`` reads back as
    ``&lt;complex.h&gt;``; the term the author wrote is what goes to a search
    index, so the entities are resolved here.
    """
    return [term for value in RE_DATA_TAG.findall(fragment) if (term := unescape(value).strip())]


def entry_tag(term: str) -> str:
    """One index entry as one tag: its filing head, when it has one.

    An index is written inverted — ``Boole, George``, ``Hanoï, tours de``,
    ``bit, le`` — so that the entry files under the word that matters. A tag
    is not: it is a chip a reader recognises and clicks, and a facet listing
    ``Gulliver, les voyages de`` next to ``pointeur`` reads as a mistake. The
    head of an inverted entry is exactly the word it is filed under, which is
    exactly the tag: ``Boole``, ``Hanoï``, ``bit``, ``EOL``.

    An entry with no comma is its own tag. The printed index is untouched by
    this: it keeps the author's spelling, inversion and all.
    """
    inverted = RE_INVERTED.match(term)
    return inverted.group("head").strip() if inverted else term


def index_terms(text: str) -> list[str]:
    """The page's index terms as tags: one per entry, its top level only.

    ``text`` is a lowered page — the Markdown ``tmark.lower_web`` returned or
    the HTML it became, since the ``ts-index`` spans read the same in both.
    A sub-entry (``#[mémoire][allocation]``) contributes its top level and
    nothing else: ``mémoire`` is what a reader browses by, where
    ``mémoire::allocation`` is the shape of a printed index, not of a chip.
    An inverted entry contributes its head, for the reason :func:`entry_tag`
    gives.

    Terms otherwise keep the author's spelling — accents, case and spaces —
    because a tag is shown as it is written and Zensical slugifies it itself
    for the anchor. They come back deduplicated in first-appearance order, so
    a page lists its terms the way it introduces them, and all of them: a
    page's index is what it is, and a page that would rather not show the
    chips says ``hide: [tags]`` in its front matter, which leaves the search
    filters alone.
    """
    terms: list[str] = []
    seen: set[str] = set()
    for match in RE_HASHTAG.findall(text):
        found = RE_TOP_TAG.search(match)
        if found is None:
            continue
        term = entry_tag(unescape(found.group(1)).strip())
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


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
        """Add the collected terms to the lunr index the site carries.

        Returns how many entries gained terms; zero for a site that has no
        lunr index, which is every site Zensical builds — the terms reach
        its search as the page's ``tags``, written while the page rendered.
        """
        if not self._collected:
            return 0
        path = Path(site_dir) / LUNR_INDEX
        if not path.is_file():
            return 0
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries = data.get("docs") if isinstance(data, dict) else None
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
            if tokens and self._append_tags(entry, tokens):
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
