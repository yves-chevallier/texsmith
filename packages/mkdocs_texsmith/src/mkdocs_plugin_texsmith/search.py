"""Index entries into the lunr search index (``web-profile.md`` step 3).

The lowering renders ``{index}[a][b]`` as ``<span class="ts-index"
data-tag="a" data-tag1="b"></span>``; the plugin collects those spans per
page and section in ``on_page_content`` and, once MkDocs' ``search`` plugin
has written ``search_index.json``, appends the tags to the matching entries.
Moved unchanged from the former ``texsmith.index`` plugin.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import json
from pathlib import Path
import re
from typing import Any


__all__ = ["SearchTags", "expand_search_terms", "extract_tags"]

RE_HEADERLINK = re.compile(r'<a\s+[^>]*headerlink[^>]*href="(#[^"]+)"[^>]*>')
RE_HASHTAG = re.compile(
    r"<span\s+[^>]*class=\"[^\"]*ts-(?:hashtag|index)[^\"]*\"[^>]*>"
)
RE_DATA_TAG = re.compile(r"data-tag\d*=\"([^\"]+)\"")


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
    return [value.strip() for value in RE_DATA_TAG.findall(fragment) if value.strip()]


class SearchTags:
    """Collect ``ts-index`` spans per location and inject them into lunr."""

    def __init__(self) -> None:
        self._collected: dict[str, set[tuple[str, ...]]] = defaultdict(set)

    def clear(self) -> None:
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
                self._collected[location].add(tuple(tags))

    def inject(self, site_dir: Path) -> bool:
        """Append the collected tags to ``search_index.json``; ``True`` when written."""
        if not self._collected:
            return False

        index_path = Path(site_dir) / "search" / "search_index.json"
        if not index_path.exists():
            return False

        data: dict[str, Any]
        with index_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        docs = data.get("docs")
        if not isinstance(docs, list):
            return False

        for entry in docs:
            location = entry.get("location")
            if not isinstance(location, str):
                continue
            tag_sets = self._collected.get(location)
            if not tag_sets:
                continue
            existing = entry.setdefault("tags", [])
            if not isinstance(existing, list):
                continue
            payload: list[str] = []
            seen: set[str] = set(map(str, existing))
            for tags in sorted(tag_sets):
                for token in expand_search_terms(tags):
                    if token not in seen:
                        seen.add(token)
                        payload.append(token)
            if payload:
                existing.extend(payload)

        with index_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return True
