"""MkDocs plugin injecting TeXSmith hashtag spans into the lunr search index."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import json
from pathlib import Path
import re
from typing import Any

from mkdocs import plugins
from mkdocs.config import config_options
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page


RE_HEADERLINK = re.compile(r'<a\s+[^>]*headerlink[^>]*href="(#[^"]+)"[^>]*>')
RE_HASHTAG = re.compile(r"<span\s+[^>]*class=\"[^\"]*ts-(?:hashtag|index)[^\"]*\"[^>]*>")
RE_DATA_TAG = re.compile(r"data-tag\d*=\"([^\"]+)\"")


def _expand_search_terms(tags: Iterable[str]) -> list[str]:
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


def _extract_tags(fragment: str) -> list[str]:
    return [value.strip() for value in RE_DATA_TAG.findall(fragment) if value.strip()]


class IndexPlugin(BasePlugin):
    """Collect hashtag spans and inject their tags into MkDocs search."""

    config_scheme = (("inject_markdown_extension", config_options.Type(bool, default=True)),)

    def __init__(self) -> None:
        self._collected: dict[str, set[tuple[str, ...]]] = defaultdict(set)

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig:
        """Optionally enable the markdown extension automatically."""
        self._collected.clear()
        if self.config.get("inject_markdown_extension", True):
            extension = "texsmith.index:TexsmithIndexExtension"
            extensions = list(config.markdown_extensions or [])
            if extension not in extensions:
                extensions.append(extension)
                config.markdown_extensions = extensions
        return config

    def on_page_content(
        self,
        html: str,
        page: Page,
        config: MkDocsConfig,
        files: Files,
    ) -> str:
        """Collect tags per page (and optionally per section heading)."""
        del config, files
        base = page.url or ""
        anchor = ""
        heading_count = 0

        for line in html.split("\n"):
            if header := RE_HEADERLINK.search(line):
                anchor = header.group(1)
                heading_count += 1

            for match in RE_HASHTAG.findall(line):
                tags = _extract_tags(match)
                if not tags:
                    continue
                location = f"{base}{anchor}" if anchor and heading_count > 1 else base
                self._collected[location].add(tuple(tags))

        return html

    @plugins.event_priority(-100)
    def on_post_build(self, config: MkDocsConfig) -> None:
        """Inject gathered tags into the lunr search index."""
        if not self._collected:
            return

        search_dir = Path(config.site_dir) / "search"
        index_path = search_dir / "search_index.json"
        if not index_path.exists():
            return

        data: dict[str, Any]
        with index_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        docs = data.get("docs")
        if not isinstance(docs, list):
            return

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
                for token in _expand_search_terms(tags):
                    if token not in seen:
                        seen.add(token)
                        payload.append(token)
            if payload:
                existing.extend(payload)

        with index_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle)


__all__ = ["IndexPlugin"]
