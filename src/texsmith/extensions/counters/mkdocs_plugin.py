"""MkDocs plugin rendering TeXSmith custom counters on a documentation site.

TeXSmith allocates counter values while converting a document, from the
``counters:`` front matter it parses itself. A MkDocs site never goes through
that path: it reads the front matter into ``page.meta`` and builds one throwaway
``Markdown`` instance per page. This plugin bridges the two.

It also makes the numbering *site-wide*. A pre-pass walks the navigation in
order and reserves a value for every marker it finds, so a reference on the
first page resolves to an item defined on the last one, and a cross-page
reference is rewritten to point at the page that actually defines the item.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from mkdocs.config import config_options
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import Files
from mkdocs.structure.nav import Navigation
from mkdocs.structure.pages import Page
from mkdocs.utils import get_relative_url

from texsmith.core.counters import (
    KEY_PATTERN,
    PREFIX_PATTERN,
    CounterSpec,
    CounterValidationError,
    clear_registry,
    get_registry,
)

from .markdown import COUNTER_PATTERN


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterator


logger = logging.getLogger("mkdocs.plugins.texsmith.counters")

#: The module path form; the entry-point spelling ``texsmith.counters`` and the
#: explicit ``…:CountersExtension`` form are recognised too.
EXTENSION_NAME = "texsmith.extensions.counters"
_EXTENSION_ALIASES = ("texsmith.extensions.counters", "texsmith.counters")

#: ``@prefix:key`` is half the feature and lives in its own extension; a site
#: that enables counters wants it too.
REFERENCE_EXTENSION = "texsmith.extensions.references"
_REFERENCE_ALIASES = ("texsmith.extensions.references", "texsmith.references")

_FENCE_RE = re.compile(r"^(?P<fence>```+|~~~+).*?^(?P=fence)[ \t]*$", re.DOTALL | re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

#: ``#{prefix:key}`` and the silent ``{#prefix:key}`` attribute list, in one
#: sweep so the pre-pass sees them in the order the reader will.
_MARKER_RE = re.compile(
    COUNTER_PATTERN
    + rf"|(?<!\\)\{{#(?P<attr_prefix>{PREFIX_PATTERN}):(?P<attr_key>{KEY_PATTERN})\}}"
)

_REFERENCE_RE = re.compile(rf'href="#(?P<prefix>{PREFIX_PATTERN}):(?P<key>[^"]+)"')


def _strip_code(source: str) -> str:
    """Drop fenced blocks and inline code spans before scanning for markers."""
    return _INLINE_CODE_RE.sub("", _FENCE_RE.sub("", source))


def _iter_markers(source: str, specs: dict[str, CounterSpec]) -> Iterator[tuple[str, str]]:
    """Yield the ``(prefix, key)`` of every declared marker, in document order."""
    for match in _MARKER_RE.finditer(_strip_code(source)):
        prefix = match.group("prefix") or match.group("attr_prefix")
        key = match.group("key") or match.group("attr_key")
        if prefix in specs and key:
            yield prefix, key


def _parse(payload: Any, *, origin: str) -> dict[str, CounterSpec]:
    """Validate a ``counters`` payload, reporting its origin on failure."""
    from texsmith.core.counters import parse_front_matter_counters

    try:
        return parse_front_matter_counters({"counters": payload})
    except CounterValidationError as exc:
        logger.warning("Invalid 'counters' declaration in %s: %s", origin, exc)
        return {}


class CountersPlugin(BasePlugin):
    """Declare, number and resolve TeXSmith custom counters across a site."""

    config_scheme = (
        ("inject_markdown_extension", config_options.Type(bool, default=True)),
        ("inject_reference_extension", config_options.Type(bool, default=True)),
        ("counters", config_options.Type(dict, default={})),
    )

    def __init__(self) -> None:
        self._site_specs: dict[str, CounterSpec] = {}
        self._known_specs: dict[str, CounterSpec] = {}
        self._page_specs: dict[str, dict[str, CounterSpec]] = {}
        self._page_of: dict[str, str] = {}
        self._extension_name = EXTENSION_NAME

    # -- configuration -----------------------------------------------------

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig:
        """Reset the registry, read the site-wide declarations, enable the extension."""
        clear_registry()
        self._known_specs.clear()
        self._page_specs.clear()
        self._page_of.clear()

        self._site_specs = _parse(self.config.get("counters") or {}, origin="mkdocs.yml")
        self._known_specs.update(self._site_specs)
        get_registry().declare(self._site_specs)

        extensions = list(config.markdown_extensions or [])
        declared = [name for name in extensions if name.startswith(_EXTENSION_ALIASES)]
        if declared:
            self._extension_name = declared[0]
        elif self.config.get("inject_markdown_extension", True):
            extensions.append(EXTENSION_NAME)
            self._extension_name = EXTENSION_NAME

        # Without the cross-reference shorthand the markers would render but
        # ``@prefix:key`` would stay literal, which is half a feature.
        if self.config.get("inject_reference_extension", True) and not any(
            name.startswith(_REFERENCE_ALIASES) for name in extensions
        ):
            extensions.append(REFERENCE_EXTENSION)

        config.markdown_extensions = extensions
        return config

    # -- numbering pre-pass ------------------------------------------------

    def on_nav(self, nav: Navigation, config: MkDocsConfig, files: Files) -> Navigation:
        """Reserve every counter value in navigation order, site-wide."""
        del config, files
        for page in nav.pages:
            source = self._read_source(page)
            if source is None:
                continue
            self._register_page(page, source)
        return nav

    def _read_source(self, page: Page) -> str | None:
        path = getattr(page.file, "abs_src_path", None)
        if not path:
            return None
        try:
            return Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - unreadable source
            logger.warning("Could not pre-scan '%s' for counters.", page.file.src_uri)
            return None

    def _register_page(self, page: Page, source: str) -> dict[str, CounterSpec]:
        """Declare a page's counters and reserve the values of its markers."""
        from texsmith.adapters.markdown import split_front_matter

        metadata, body = split_front_matter(source)
        specs = {
            **self._site_specs,
            **_parse((metadata or {}).get("counters"), origin=page.file.src_uri),
        }
        self._page_specs[page.file.src_uri] = specs
        # A counter declared on one page is referenceable from every other one,
        # so the whole site shares the declarations the pre-pass collected.
        self._known_specs.update(specs)
        if not specs:
            return specs

        registry = get_registry()
        registry.declare(specs)
        for prefix, key in _iter_markers(body, specs):
            registry.prepare(prefix, key)
            self._page_of.setdefault(f"{prefix}:{key}", page.url)
        return specs

    # -- per-page conversion ----------------------------------------------

    def on_page_markdown(
        self,
        markdown: str,
        page: Page,
        config: MkDocsConfig,
        files: Files,
    ) -> str:
        """Hand the page's declarations to the markdown extension."""
        del files
        specs = self._page_specs.get(page.file.src_uri)
        if specs is None:
            # A page outside the navigation never went through the pre-pass.
            specs = self._register_page(page, markdown)
        config.mdx_configs.setdefault(self._extension_name, {})["specs"] = {
            **self._known_specs,
            **specs,
        }
        return markdown

    def on_page_content(
        self,
        html: str,
        page: Page,
        config: MkDocsConfig,
        files: Files,
    ) -> str:
        """Point cross-page references at the page that defines the item."""
        del config, files
        if not self._page_of:
            return html

        def repoint(match: re.Match[str]) -> str:
            identifier = f"{match.group('prefix')}:{match.group('key')}"
            target = self._page_of.get(identifier)
            if target is None or target == page.url:
                return match.group(0)
            url = get_relative_url(target, page.url)
            return f'href="{url}#{identifier}"'

        return _REFERENCE_RE.sub(repoint, html)


__all__ = ["EXTENSION_NAME", "REFERENCE_EXTENSION", "CountersPlugin"]
