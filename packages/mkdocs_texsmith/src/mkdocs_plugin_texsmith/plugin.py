"""The ``texsmith`` MkDocs plugin: one plugin, two media, one registry.

``specs/migration/web-profile.md`` §Interfaces, "What the plugin calls":

* ``on_config`` injects the Markdown extensions the lowering relies on
  (``attr_list``, ``md_in_html``, ``admonition``, ``pymdownx.details``,
  ``pymdownx.superfences``), registers ``texsmith.css`` and reads the
  site-wide ``declare.counters``;
* ``on_nav`` pre-passes every page (``tmark.parse`` + ``tmark.resolve`` with
  ``numbering: "all"``, ``start`` chained in navigation order) and builds
  the site label map;
* ``on_page_markdown`` (priority −50, after ``macros``) resolves the page
  against the site map and lowers it with ``tmark.lower_web``;
* ``on_page_content`` collects the ``ts-index`` tags for the search index;
* ``on_post_page`` rewrites the snippet URLs and corrects the page's HTML;
* ``on_post_build`` injects the tags into the lunr index and hands the
  navigation to :mod:`texsmith.site.book`, which builds every book.

The books themselves are not the plugin's: ``texsmith.site.book`` builds
them from the Markdown the pages are written in, and this module is the
adapter that gives it MkDocs' navigation (:func:`_nav_items`), MkDocs' site
metadata and the site index the hooks above filled in. ``texsmith site
build`` drives the same builder for a generator that has no hooks.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import os
from pathlib import Path
from typing import Any

from mkdocs.config import config_options
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.structure import StructureItem
from mkdocs.structure.files import File, Files
from mkdocs.structure.nav import Navigation
from mkdocs.structure.pages import Page
from mkdocs.utils import log
from texsmith.adapters.plugins import snippet
from texsmith.diagnostics import LoggingEmitter
from texsmith.site import assets
from texsmith.site.book import (
    BookBuilder,
    BookError,
    BookSettings,
    SiteMetadata,
    book_build_root,
    env_flag_enabled,
    load_book_settings,
)
from texsmith.site.config import (
    snippet_auto_append_from_extensions,
    snippet_base_paths_from_extensions,
    web_typography,
)
from texsmith.site.html import french_typography, unescape_table_pipes
from texsmith.site.index import SiteIndex, SitePage, site_index
from texsmith.site.nav import (
    Navigation as SiteNavigation,
    NavItem,
    NavLink,
    NavPage,
    NavSection,
)
from texsmith.site.search import SearchTags


#: What the lowering emits relies on these (spec Table ``tbl:extensions``).
REQUIRED_MARKDOWN_EXTENSIONS = (
    "attr_list",
    "md_in_html",
    "admonition",
    "pymdownx.details",
    "pymdownx.superfences",
)
#: Where the stylesheet lands in the site.
CSS_URI = assets.CSS_URI


def _site_page(page: Page) -> SitePage | None:
    """The :class:`SitePage` of an MkDocs page, ``None`` for a generated one.

    A page MkDocs made up (a redirect, a generated file) has no source on
    disk, and the index reads the file: such a page is not part of the site
    index. The metadata is left to the index, which reads the front matter
    itself — at ``on_nav`` MkDocs has not read the page yet, so ``page.meta``
    is still empty.
    """
    abs_src = getattr(page.file, "abs_src_path", None)
    if not abs_src:
        return None
    return SitePage(src_uri=page.file.src_uri, abs_src_path=Path(abs_src))


def _site_pages(pages: Iterable[Page]) -> Iterable[SitePage]:
    """Every page of ``pages`` that has a source on disk."""
    for page in pages:
        site_page = _site_page(page)
        if site_page is not None:
            yield site_page


def _nav_items(items: Iterable[StructureItem]) -> tuple[NavItem, ...]:
    """MkDocs' navigation as the :mod:`texsmith.site.nav` tree the book reads.

    MkDocs has resolved the titles by the time the book is built, so each page
    carries its own rather than leaving the resolver to infer one, and a
    section keeps its index page where MkDocs keeps it: among its children.
    """
    converted: list[NavItem] = []
    for item in items:
        if item.is_page:
            abs_src = getattr(item.file, "abs_src_path", None)
            if not abs_src:
                continue
            converted.append(NavPage(item.title, item.file.src_uri, Path(abs_src)))
        elif getattr(item, "is_link", False):
            converted.append(NavLink(item.title or "", str(getattr(item, "url", ""))))
        else:
            converted.append(
                NavSection(item.title or "", _nav_items(item.children or ()))
            )
    return tuple(converted)


class _MkdocsEmitter(LoggingEmitter):
    """Emitter that surfaces diagnostics through MkDocs' logger."""

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        if name == "snippet_build":
            digest = payload.get("digest") if isinstance(payload, Mapping) else None
            source = payload.get("source") if isinstance(payload, Mapping) else None
            source_hint = f" ({source})" if source else ""
            self._logger.info(
                "texsmith: building snippet %s%s", digest or "snippet", source_hint
            )
            return
        super().event(name, payload)


class LatexPlugin(BasePlugin):
    """MkDocs plugin that exports documentation to LaTeX using TeXSmith."""

    config_scheme = (
        ("enabled", config_options.Type(bool, default=True)),
        ("build_dir", config_options.Type(str, default="press")),
        ("template", config_options.Type(str, default="book")),
        ("copy_assets", config_options.Type(bool, default=True)),
        ("clean_assets", config_options.Type(bool, default=True)),
        ("embed_documents", config_options.Type(bool, default=False)),
        ("language", config_options.Type((str, type(None)), default=None)),
        ("bibliography", config_options.Type(list, default=[])),
        ("books", config_options.Type(list, default=[])),
        ("template_overrides", config_options.Type(dict, default={})),
        # Site-wide declarations (``declare.counters``), as ``press.declare``
        # in a page's front matter; every page sees them.
        ("declare", config_options.Type(dict, default={})),
        # ``tmark.lower_web`` options: ``sections`` (``title`` | ``number``),
        # ``citations`` (``inline`` | ``passthrough``); plus the plugin's own
        # ``tags`` (``index`` | ``none``) and ``typography`` (``fr`` |
        # ``none``, the site language by default).
        ("web", config_options.Type(dict, default={})),
        ("inject_markdown_extensions", config_options.Type(bool, default=True)),
        ("css", config_options.Type(bool, default=True)),
    )

    def __init__(self) -> None:
        self._enabled = True
        self._is_serve = False
        self._mkdocs_config: MkDocsConfig | None = None
        self._settings: BookSettings | None = None
        self._project_dir: Path | None = None
        self._site_dir: Path | None = None
        self._nav: Navigation | None = None
        self._diagnostic_emitter: LoggingEmitter | None = None
        self._auto_build = False
        self._site: SiteIndex | None = None
        #: ``web.typography``: ``"fr"`` or ``None``, resolved once the site
        #: index knows the language (``on_config``).
        self._typography: str | None = None
        self._search = SearchTags()
        self._css_content: str | None = None

    # -- MkDocs lifecycle -------------------------------------------------

    def on_startup(self, command: str, dirty: bool) -> None:  # pragma: no cover - hook
        self._is_serve = command == "serve"

    def on_config(
        self, config: MkDocsConfig
    ) -> MkDocsConfig:  # pragma: no cover - hook
        self._enabled = bool(self.config.get("enabled", True))
        self._mkdocs_config = config
        self._auto_build = env_flag_enabled(os.environ.get("TEXSMITH_BUILD"))

        if not self._enabled:
            return config

        config_path = Path(config.config_file_path)
        self._project_dir = config_path.parent.resolve()
        self._site_dir = Path(config.site_dir).resolve()

        site_language: str | None = getattr(config, "site_language", None)
        config_get = getattr(config, "get", None)
        if not site_language and callable(config_get):
            site_language = config_get("site_language")

        snippet_paths = snippet_base_paths_from_extensions(
            getattr(config, "mdx_configs", None), self._project_dir
        )
        self._diagnostic_emitter = _MkdocsEmitter(
            logger_obj=log,
            debug_enabled=self._is_serve,
        )

        # The site on tmark.
        self._search.clear()
        self._site = site_index(
            self.config,
            project_dir=self._project_dir,
            theme=getattr(config, "theme", None),
            site_language=site_language,
            include_paths=snippet_paths,
            logger=log,
            emitter=self._diagnostic_emitter,
        )
        self._typography = web_typography(self.config, lang=self._site.lang, logger=log)
        try:
            self._settings = load_book_settings(
                self.config,
                project_dir=self._project_dir,
                build_dir=book_build_root(self.config, self._project_dir),
                language=self._site.lang,
                snippet_base_paths=snippet_paths,
                snippet_auto_append=snippet_auto_append_from_extensions(
                    getattr(config, "mdx_configs", None), snippet_paths
                ),
                docs_dir=Path(config["docs_dir"]),
                logger=log,
            )
        except BookError as exc:
            raise PluginError(str(exc)) from exc
        if self.config.get("inject_markdown_extensions", True):
            self._inject_markdown_extensions(config)
        if self.config.get("css", True):
            self._css_content = assets.stylesheet()
            extra_css = list(config.extra_css or [])
            if CSS_URI not in extra_css:
                extra_css.append(CSS_URI)
            config.extra_css = extra_css
        return config

    def on_files(
        self, files: Files, config: MkDocsConfig
    ) -> Files:  # pragma: no cover - hook
        if not self._enabled or self._css_content is None:
            return files
        if files.get_file_from_path(CSS_URI) is None:
            files.append(File.generated(config, CSS_URI, content=self._css_content))
        return files

    def on_nav(
        self,
        nav: Navigation,
        config: MkDocsConfig,
        files: Files,
    ) -> Navigation:  # pragma: no cover - hook
        if not self._enabled:
            return nav

        self._nav = nav
        if self._site is not None:
            # Navigation order first, then the pages outside the nav in file order.
            self._site.prepass(_site_pages(nav.pages))
            self._site.prepass(
                _site_pages(
                    file.page
                    for file in files.documentation_pages()
                    if file.page is not None
                    and file.page.file.src_uri not in self._site.records
                )
            )
        return nav

    @event_priority(-50)
    def on_page_markdown(
        self,
        markdown: str,
        page: Page,
        config: MkDocsConfig,
        files: Files,
    ) -> str:  # pragma: no cover - hook
        del config, files
        if not self._enabled or self._site is None:
            return markdown
        site_page = _site_page(page)
        if site_page is None:
            return markdown
        lowered = self._site.lower(site_page, markdown)
        if lowered is None:
            return markdown
        self._site.report(lowered)
        return lowered.text

    def on_page_content(
        self,
        html: str,
        page: Page,
        config: MkDocsConfig,
        files: Files,
    ) -> str:  # pragma: no cover - hook
        del config, files
        if self._enabled:
            self._search.collect(html, page.url or "")
        return html

    def on_post_page(
        self,
        output: str,
        page,
        config: MkDocsConfig,
    ) -> str:  # pragma: no cover - hook
        if not self._enabled:
            return output

        rewritten = snippet.rewrite_html_snippets(
            output,
            lambda block: self._build_snippet_urls(page, block),
            source_path=page.file.abs_src_path,
        )
        # The same Python-Markdown wart the Zensical extension corrects, and
        # the same correction: ``texsmith.site.html`` explains it.
        corrected = unescape_table_pipes(rewritten)
        # And the same typography, over the whole page rather than over the
        # content alone: this hook is handed the rendered template, so the
        # navigation and the headings of a French site are spaced with it.
        if self._typography == "fr":
            corrected = french_typography(corrected)
        return corrected

    @event_priority(-100)
    def on_post_build(self, config: MkDocsConfig) -> None:  # pragma: no cover - hook
        if not self._enabled:
            return

        # After the ``search`` plugin wrote its index.
        if patched := self._search.inject(Path(config.site_dir)):
            log.info("texsmith: index entries added to %d search entries.", patched)

        if self._is_serve:
            return

        if self._settings is None or self._site is None or self._nav is None:
            raise PluginError("TeXSmith plugin is not initialised correctly.")

        builder = BookBuilder(
            self._settings,
            index=self._site,
            metadata=SiteMetadata.read(config),
            emitter=self._diagnostic_emitter,
            logger=log,
            compile_pdf=self._auto_build,
            publish_snippets_to=self._site_dir_or_fail(),
        )
        navigation = SiteNavigation(_nav_items(self._nav.items))
        try:
            for book in builder.prepare(navigation):
                builder.render(book)
        except BookError as exc:
            raise PluginError(str(exc)) from exc

    # -- Site helpers -------------------------------------------------------

    @staticmethod
    def _inject_markdown_extensions(config: MkDocsConfig) -> None:
        """Enable the extensions the lowered Markdown relies on, when absent.

        ``markdown_extensions`` holds entry-point names, but another plugin
        (``autorefs``) may have appended an ``Extension`` instance; such an
        entry is matched by its module path and by its last segment, so
        ``markdown.extensions.admonition`` counts as ``admonition``.
        """
        extensions = list(config.markdown_extensions or [])
        present: set[str] = set()
        for entry in extensions:
            if isinstance(entry, str):
                present.add(entry.split(":", 1)[0])
                continue
            module = type(entry).__module__
            present.add(module)
            present.add(module.rsplit(".", 1)[-1])
        for name in REQUIRED_MARKDOWN_EXTENSIONS:
            if name not in present:
                extensions.append(name)
        config.markdown_extensions = extensions

    def _build_snippet_urls(
        self, page: Any, block: snippet.SnippetBlock
    ) -> tuple[str, str]:
        abs_src = getattr(page.file, "abs_src_path", None)
        if not abs_src:
            raise PluginError(
                "Unable to determine the source path for snippet rendering."
            )
        emitter = self._diagnostic_emitter or _MkdocsEmitter(
            logger_obj=log, debug_enabled=self._is_serve
        )
        site_dir = self._site_dir_or_fail()
        try:
            return assets.snippet_urls(
                block,
                root=site_dir,
                dest_uri=page.file.dest_uri,
                source_path=Path(abs_src),
                emitter=emitter,
            )
        except Exception as exc:  # pragma: no cover - passthrough
            raise PluginError(
                f"Failed to render snippet on page '{page.file.src_path}': {exc}"
            ) from exc

    def _site_dir_or_fail(self) -> Path:
        """The site directory, taken from the live configuration when needed."""
        site_dir = self._site_dir
        if site_dir is None:
            config_site = getattr(self._mkdocs_config, "site_dir", None)
            if not config_site:
                raise PluginError("MkDocs site directory is not initialised.")
            site_dir = Path(config_site).resolve()
            self._site_dir = site_dir
        return site_dir


__all__ = ["LatexPlugin"]
