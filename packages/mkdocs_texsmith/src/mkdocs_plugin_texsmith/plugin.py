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
  against the site map, lowers it with ``tmark.lower_web`` and stores the
  source for the PDF;
* ``on_page_content`` collects the ``ts-index`` tags for the search index;
* ``on_post_page`` captures the rendered HTML (the ``press.reader: html``
  fallback) and rewrites the snippet URLs;
* ``on_post_build`` builds the books from the stored sources through the
  tmark reader path and injects the tags into the lunr index.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from importlib import resources
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import sys
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
from rich.console import Console
from slugify import slugify
from texsmith.adapters.latex.engines import (
    EngineFeatures,
    LatexMessage,
    LatexMessageSeverity,
    build_engine_command,
    build_tex_env,
    compute_features,
    ensure_command_paths,
    missing_dependencies,
    resolve_engine,
    run_engine_command,
)
from texsmith.adapters.latex.latexmk import build_latexmkrc_content
from texsmith.adapters.latex.tectonic import (
    BiberAcquisitionError,
    MakeglossariesAcquisitionError,
    TectonicAcquisitionError,
    select_biber_binary,
    select_makeglossaries,
    select_tectonic_binary,
)
from texsmith.adapters.plugins import snippet
from texsmith.core.bibliography import (
    BibliographyCollection,
)
from texsmith.core.config import BookConfig, LaTeXConfig
from texsmith.core.context import DocumentState
from texsmith.core.conversion.core import convert_document
from texsmith.core.conversion.debug import format_rendering_error
from texsmith.core.conversion.models import ConversionRequest
from texsmith.core.conversion.resolution import ResolutionChain, bibliography_paths
from texsmith.core.diagnostics import LoggingEmitter
from texsmith.core.documents import Document, TitleStrategy
from texsmith.core.exceptions import LatexRenderingError
from texsmith.core.templates import (
    TemplateError,
    TemplateSlot,
    load_template_runtime,
    normalise_template_language,
    wrap_template_document,
)
from texsmith.diagnostics import FileTable
import yaml

from .search import SearchTags
from .site import HEADING_PREFIXES, PageRecord, SiteIndex


AUTO_BASE_LEVEL = -2
FULL_NAVIGATION_ROOT = "__texsmith_full_navigation__"

#: What the lowering emits relies on these (spec Table ``tbl:extensions``).
REQUIRED_MARKDOWN_EXTENSIONS = (
    "attr_list",
    "md_in_html",
    "admonition",
    "pymdownx.details",
    "pymdownx.superfences",
)
#: Where the stylesheet lands in the site.
CSS_URI = "assets/texsmith/texsmith.css"


def _snippet_base_paths(config: MkDocsConfig) -> list[Path]:
    """The ``base_path`` of the site's ``pymdownx.snippets``, as directories.

    The deprecated ``--8<-- "path"`` include resolves against that base path,
    not against the page, so the PDF export has to search it too. MkDocs keeps
    every extension's options in ``config.mdx_configs``, keyed by the
    extension name, exactly as written in ``mkdocs.yml``; the value may be one
    path or a list, and a ``!relative`` tag arrives as a placeholder object
    that spells itself out through :func:`os.fspath` (``!relative $config_dir``
    is the directory of ``mkdocs.yml``). Anything else — the extension absent,
    an option we cannot read as a path — yields no search path rather than a
    guess.
    """
    configs = getattr(config, "mdx_configs", None)
    if not isinstance(configs, Mapping):
        return []
    section = configs.get("pymdownx.snippets")
    if not isinstance(section, Mapping):
        return []
    raw = section.get("base_path")
    if raw is None:
        return []
    candidates = raw if isinstance(raw, list | tuple) else [raw]
    paths: list[Path] = []
    for candidate in candidates:
        try:
            path = Path(os.fspath(candidate))
        except TypeError:
            log.warning(
                "Ignoring 'pymdownx.snippets.base_path' entry %r: not a path.",
                candidate,
            )
            continue
        if not path.is_absolute():
            path = Path(config.config_file_path).parent / path
        resolved = Path(os.path.normpath(path))
        if resolved not in paths:
            paths.append(resolved)
    return paths


@dataclass(slots=True)
class BookExtras:
    """Container for plugin-specific book options."""

    template: str | None = None
    template_overrides: dict[str, Any] = field(default_factory=dict)
    bibliography: list[Path] = field(default_factory=list)
    slots: dict[str, set[str]] = field(default_factory=dict)
    press: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NavEntry:
    """Flattened navigation entry with rendering metadata."""

    title: str
    level: int
    numbered: bool
    drop_title: bool
    part: str
    is_page: bool
    slot: str | None = None
    src_path: str | None = None
    src_uri: str | None = None
    abs_src_path: Path | None = None


@dataclass(slots=True)
class BookRuntime:
    """Runtime representation of a configured book."""

    config: BookConfig
    extras: BookExtras
    section: StructureItem | None = None
    entries: list[NavEntry] = field(default_factory=list)


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
        ("parser", config_options.Type(str, default="lxml")),
        ("copy_assets", config_options.Type(bool, default=True)),
        ("clean_assets", config_options.Type(bool, default=True)),
        ("save_html", config_options.Type(bool, default=False)),
        ("embed_fragments", config_options.Type(bool, default=False)),
        ("language", config_options.Type((str, type(None)), default=None)),
        ("bibliography", config_options.Type(list, default=[])),
        ("books", config_options.Type(list, default=[])),
        ("template_overrides", config_options.Type(dict, default={})),
        # Site-wide declarations (``declare.counters``), as ``press.declare``
        # in a page's front matter; every page sees them.
        ("declare", config_options.Type(dict, default={})),
        # ``tmark.lower_web`` options: ``sections`` (``title`` | ``number``),
        # ``citations`` (``inline`` | ``passthrough``).
        ("web", config_options.Type(dict, default={})),
        ("inject_markdown_extensions", config_options.Type(bool, default=True)),
        ("css", config_options.Type(bool, default=True)),
    )

    def __init__(self) -> None:
        self._enabled = True
        self._is_serve = False
        self._mkdocs_config: MkDocsConfig | None = None
        self._latex_config: LaTeXConfig | None = None
        self._books: list[BookRuntime] = []
        self._book_extras: list[BookExtras] = []
        self._build_root: Path | None = None
        self._project_dir: Path | None = None
        self._site_dir: Path | None = None
        self._page_content: dict[str, str] = {}
        self._page_meta: dict[str, dict[str, Any]] = {}
        self._page_sources: dict[str, Path] = {}
        self._global_bibliography: list[Path] = []
        self._global_template_overrides: dict[str, Any] = {}
        self._snippet_base_paths: list[Path] = []
        self._nav: Navigation | None = None
        self._diagnostic_emitter: LoggingEmitter | None = None
        self._auto_build = False
        self._site: SiteIndex | None = None
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
        self._auto_build = self._env_flag_enabled(os.environ.get("TEXSMITH_BUILD"))

        if not self._enabled:
            return config

        config_path = Path(config.config_file_path)
        self._project_dir = config_path.parent.resolve()
        self._site_dir = Path(config.site_dir).resolve()

        build_dir_setting = Path(self.config.get("build_dir") or "press")
        if not build_dir_setting.is_absolute():
            base_dir = self._project_dir or Path.cwd()
            self._build_root = (base_dir / build_dir_setting).resolve()
        else:
            self._build_root = build_dir_setting.resolve()

        theme_language: str | None = None
        theme_locale: str | None = None
        theme = getattr(config, "theme", None)
        if theme is not None:
            theme_get = getattr(theme, "get", None)
            if callable(theme_get):
                theme_language = theme_get("language")
                locale = theme_get("locale")
                if locale is not None:
                    theme_locale = getattr(locale, "language", None) or str(locale)
            else:
                theme_language = getattr(theme, "language", None)
                locale = getattr(theme, "locale", None)
                if locale is not None:
                    theme_locale = getattr(locale, "language", None) or str(locale)

        site_language: str | None = getattr(config, "site_language", None)
        config_get = getattr(config, "get", None)
        if not site_language and callable(config_get):
            site_language = config_get("site_language")

        language = (
            self.config.get("language")
            or theme_language
            or theme_locale
            or site_language
        )

        self._global_bibliography = self._coerce_paths(
            self.config.get("bibliography") or []
        )
        self._snippet_base_paths = _snippet_base_paths(config)
        self._global_template_overrides = dict(
            self.config.get("template_overrides") or {}
        )

        self._latex_config = self._build_latex_config(language)
        self._diagnostic_emitter = _MkdocsEmitter(
            logger_obj=log,
            debug_enabled=self._is_serve,
            files=FileTable(),
        )

        # -- the site on tmark ------------------------------------------------
        self._page_content.clear()
        self._page_meta.clear()
        self._page_sources.clear()
        self._search.clear()
        self._books.clear()
        self._site = SiteIndex(
            counters=self._site_counters(),
            lang=language,
            web_options=self._web_options(),
            project_dir=self._project_dir,
            logger=log,
        )
        if self.config.get("inject_markdown_extensions", True):
            self._inject_markdown_extensions(config)
        if self.config.get("css", True):
            self._css_content = _stylesheet()
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
            self._site.prepass(nav.pages)
            self._site.prepass(
                file.page
                for file in files.documentation_pages()
                if file.page is not None
                and file.page.file.src_uri not in self._site.records
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
        if not getattr(page.file, "abs_src_path", None):
            return markdown
        lowered = self._site.lower(page, markdown)
        if lowered is None:
            return markdown
        self._site.report(
            lowered,
            emitter=_MkdocsEmitter(
                logger_obj=log, debug_enabled=self._is_serve, files=lowered.files
            ),
        )
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

        src_uri = page.file.src_uri
        self._page_content[src_uri] = page.content
        self._page_meta[src_uri] = dict(page.meta or {})
        self._page_sources[src_uri] = Path(page.file.abs_src_path)
        rewritten = snippet.rewrite_html_snippets(
            output,
            lambda block: self._build_snippet_urls(page, block),
            source_path=page.file.abs_src_path,
        )
        return rewritten

    @event_priority(-100)
    def on_post_build(self, config: MkDocsConfig) -> None:  # pragma: no cover - hook
        if not self._enabled:
            return

        # After the ``search`` plugin wrote its index.
        if self._search.inject(Path(config.site_dir)):
            log.info("texsmith: index entries added to the search index.")

        if self._is_serve:
            return

        if self._latex_config is None or self._build_root is None:
            raise PluginError("TeXSmith plugin is not initialised correctly.")

        self._prepare_books_if_needed()

        for runtime in self._books:
            self._render_book(runtime)

    # -- Site helpers -------------------------------------------------------

    def _site_counters(self) -> dict[str, Any]:
        declare = self.config.get("declare") or {}
        counters = declare.get("counters") if isinstance(declare, Mapping) else None
        if counters is None:
            return {}
        if not isinstance(counters, Mapping):
            log.warning(
                "texsmith: 'declare.counters' must map a prefix to its declaration; "
                "ignoring %r.",
                type(counters).__name__,
            )
            return {}
        return dict(counters)

    def _web_options(self) -> dict[str, Any]:
        raw = self.config.get("web") or {}
        options: dict[str, Any] = {}
        if not isinstance(raw, Mapping):
            log.warning(
                "texsmith: 'web' must be a mapping; ignoring %r.", type(raw).__name__
            )
            return options
        for key in ("sections", "citations", "css_prefix"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                options[key] = value.strip()
        return options

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

    # -- Helpers ----------------------------------------------------------

    @staticmethod
    def _env_flag_enabled(raw: str | None) -> bool:
        if raw is None:
            return False
        normalised = raw.strip().lower()
        return normalised not in {"", "0", "false", "no", "off"}

    def _build_latex_config(self, language: str | None) -> LaTeXConfig:
        project_dir = self._project_dir
        build_root = self._build_root

        if project_dir is None or build_root is None:
            raise PluginError("Project directories are not prepared.")

        book_specs = self.config.get("books") or []
        if not isinstance(book_specs, list):
            raise PluginError("The 'books' option must be a list.")

        book_configs: list[BookConfig] = []
        extras: list[BookExtras] = []

        for idx, raw in enumerate(book_specs, start=1):
            if not isinstance(raw, dict):
                raise PluginError(f"Book definition #{idx} is not a mapping.")

            data = dict(raw)
            slot_requests = self._normalise_slot_requests(data.pop("slots", None))
            paper_override = data.pop("paper", None)
            press_overrides = self._normalise_press_overrides(
                data.pop("press", None), paper_override
            )
            book_extra = BookExtras(
                template=data.pop("template", None),
                template_overrides=dict(data.pop("template_overrides", {}) or {}),
                bibliography=self._coerce_paths(
                    data.pop("bibliography", []), relative_to=project_dir
                ),
                slots=slot_requests,
                press=press_overrides,
            )
            try:
                book_config = BookConfig(**data)
            except ValueError as exc:
                raise PluginError(f"Invalid book configuration #{idx}: {exc}") from exc

            book_configs.append(book_config)
            extras.append(book_extra)

        if not book_configs:
            book_configs = [BookConfig()]
            extras = [BookExtras()]

        latex_config = LaTeXConfig(
            build_dir=build_root,
            save_html=bool(self.config.get("save_html", False)),
            project_dir=project_dir,
            language=language,
            books=book_configs,
            clean_assets=bool(self.config.get("clean_assets", True)),
        )

        self._book_extras = extras
        return latex_config

    def _prepare_books_if_needed(self) -> None:
        if self._books:
            return

        if (
            self._latex_config is None
            or self._mkdocs_config is None
            or self._nav is None
        ):
            raise PluginError("Navigation is not available to prepare books.")

        nav = self._nav
        self._books.clear()
        for book_config, book_extra in zip(
            self._latex_config.books, self._book_extras, strict=False
        ):
            self._prepare_book(book_config, book_extra, nav, self._mkdocs_config)

    def _prepare_book(
        self,
        book_config: BookConfig,
        extras: BookExtras,
        nav: Navigation,
        mkdocs_config: MkDocsConfig,
    ) -> None:
        if book_config.root is None:
            if nav.pages:
                book_config.root = nav.pages[0].title
            else:
                raise PluginError(
                    "Unable to infer the root section for a book; "
                    "specify 'root' in the plugin configuration."
                )

        book_config.title = book_config.title or mkdocs_config.site_name
        book_config.author = book_config.author or getattr(
            mkdocs_config, "site_author", None
        )
        book_config.subtitle = book_config.subtitle or getattr(
            mkdocs_config, "site_description", None
        )

        site_date = getattr(mkdocs_config, "site_date", None)
        if book_config.year is None:
            if hasattr(site_date, "year"):
                book_config.year = site_date.year
        book_config.email = book_config.email or getattr(
            mkdocs_config, "site_email", None
        )

        entries: list[NavEntry]
        root_item: StructureItem | None = None

        if book_config.root == FULL_NAVIGATION_ROOT:
            entries = self._flatten_full_navigation(nav, book_config, extras.slots)
        else:
            root_item = self._find_item_by_title(nav.items, book_config.root)
            if root_item is None:
                raise PluginError(
                    f"Root section '{book_config.root}' not found in navigation."
                )
            entries = self._flatten_navigation(root_item, book_config, extras.slots)

        runtime = BookRuntime(config=book_config, extras=extras, section=root_item)
        runtime.entries = entries
        self._books.append(runtime)

    def _render_book(self, runtime: BookRuntime) -> None:
        output_root = self._resolve_output_root(runtime.config)
        output_root.mkdir(parents=True, exist_ok=True)
        emitter = self._diagnostic_emitter or _MkdocsEmitter(
            logger_obj=log, debug_enabled=self._is_serve
        )

        template_name = runtime.extras.template or self.config.get("template")
        try:
            template_runtime = (
                load_template_runtime(template_name)
                if template_name
                else load_template_runtime("book")
            )
        except TemplateError as exc:
            raise PluginError(
                f"Failed to load template '{template_name}': {exc}"
            ) from exc

        original_base_level = runtime.config.base_level
        resolved_base_level = original_base_level
        if original_base_level == AUTO_BASE_LEVEL:
            template_base_level = template_runtime.base_level
            default_slot_name = template_runtime.default_slot
            default_slot: TemplateSlot | None = (
                template_runtime.slots.get(default_slot_name)
                if default_slot_name in template_runtime.slots
                else None
            )

            if template_base_level is not None:
                resolved_base_level = template_base_level
            elif default_slot is not None:
                fallback_level = template_base_level or 0
                resolved_base_level = default_slot.resolve_level(fallback_level)
            else:
                resolved_base_level = 1

        if resolved_base_level != original_base_level:
            level_shift = resolved_base_level - original_base_level
            runtime.config.base_level = resolved_base_level
            for entry in runtime.entries:
                entry.level += level_shift

        parser_backend = self.config.get("parser") or "lxml"
        copy_assets = bool(self.config.get("copy_assets", True))

        bibliography_files = [
            *self._global_bibliography,
            *runtime.extras.bibliography,
        ]
        # The shared ``.bib`` files; each page's context clones it and adds
        # the page's inline entries, and the clone becomes the next page's
        # base, so the collection written at the end holds every entry.
        bibliography_collection: BibliographyCollection | None = None
        if bibliography_files:
            bibliography_collection = BibliographyCollection()
            bibliography_collection.load_files(bibliography_files)
        bibliography_map: dict[str, dict[str, Any]] = (
            bibliography_collection.to_dict()
            if bibliography_collection is not None
            else {}
        )
        seen_bibliography_issues: set[tuple[str, str | None, str | None]] = set()

        document_state: DocumentState | None = None
        assets_map: dict[str, Path] = {}

        raw_language = runtime.config.language or self._latex_config.language
        language = normalise_template_language(raw_language)
        runtime_language = language or raw_language

        overrides = dict(self._global_template_overrides)
        overrides.update(runtime.extras.template_overrides)
        press_section = overrides.get("press")
        base_press = dict(press_section) if isinstance(press_section, Mapping) else {}
        if runtime.extras.press:
            base_press.update(runtime.extras.press)
        if base_press:
            overrides["press"] = base_press

        def _set_override(key: str, value: Any) -> None:
            if value is not None:
                overrides.setdefault(key, value)

        _set_override("title", runtime.config.title)
        _set_override("subtitle", runtime.config.subtitle)
        _set_override("author", runtime.config.author)
        _set_override("email", runtime.config.email)
        _set_override("year", runtime.config.year)
        if language:
            overrides.setdefault("language", language)
        overrides.setdefault("cover", runtime.config.cover.name)
        overrides.setdefault("covercolor", runtime.config.cover.color)
        if runtime.config.cover.logo:
            overrides.setdefault("logo", runtime.config.cover.logo)

        embed_fragments = bool(self.config.get("embed_fragments", False))

        slot_buffers_embed: dict[str, list[str]] = {
            name: [] for name in template_runtime.slots
        }
        slot_buffers_embed.setdefault(template_runtime.default_slot, [])
        slot_buffers_link: dict[str, list[str]] = {
            name: [] for name in template_runtime.slots
        }
        slot_buffers_link.setdefault(template_runtime.default_slot, [])
        default_base_level = runtime.config.base_level
        if default_base_level is None:
            default_base_level = 0
        slot_base_levels = {
            name: slot.resolve_level(default_base_level)
            for name, slot in template_runtime.slots.items()
        }
        missing_slot_warnings: set[str] = set()

        def select_slot(entry: NavEntry) -> str:
            if entry.slot:
                target = entry.slot
            elif entry.part == "frontmatter" and "frontmatter" in slot_buffers_embed:
                target = "frontmatter"
            elif entry.part == "backmatter" and "backmatter" in slot_buffers_embed:
                target = "backmatter"
            else:
                target = template_runtime.default_slot

            if target not in slot_buffers_embed:
                if target not in missing_slot_warnings:
                    missing_slot_warnings.add(target)
                    log.warning(
                        "Requested slot '%s' is not defined by template '%s'; "
                        "falling back to '%s'.",
                        target,
                        template_runtime.name,
                        template_runtime.default_slot,
                    )
                return template_runtime.default_slot
            return target

        # The tmark reader path (``web-profile.md`` step 4): one request for
        # the book, one resolution chain seeded where the site's chain stood
        # before the book's first page, so ``FW-10`` is ``FW-10`` on both media.
        request = ConversionRequest(
            bibliography_files=list(bibliography_files),
            template=template_runtime.name,
            parser=parser_backend,
            copy_assets=copy_assets,
            language=runtime_language,
            default_include_paths=list(self._snippet_base_paths),
            emitter=emitter,
        )
        chain = ResolutionChain(
            bibliography=bibliography_paths(bibliography_files),
            start=self._book_start(runtime),
            lang=runtime_language,
        )
        template_base = template_runtime.base_level or 0
        template_slot_levels = {
            name: slot.resolve_level(template_base)
            for name, slot in template_runtime.slots.items()
        }

        for page_index, entry in enumerate(runtime.entries):
            target_slot = select_slot(entry)
            slot_base = slot_base_levels.get(target_slot, default_base_level)
            target_buffer_embed = slot_buffers_embed[target_slot]
            target_buffer_link = slot_buffers_link[target_slot]
            effective_level = entry.level
            if slot_base is not None:
                effective_level = slot_base + (entry.level - default_base_level)

            if not entry.is_page:
                if entry.title and effective_level >= slot_base:
                    fragment = _nav_heading(
                        entry.title,
                        level=effective_level,
                        numbered=entry.numbered,
                        lang=runtime_language,
                    )
                    target_buffer_embed.append(fragment)
                    target_buffer_link.append(fragment)
                continue

            if not entry.src_uri:
                log.warning("Skipping page '%s': it has no source.", entry.title)
                continue
            abs_src = entry.abs_src_path or self._page_sources.get(entry.src_uri)
            if abs_src is None:
                log.warning(
                    "Cannot determine source path for page '%s'; skipping.",
                    entry.title,
                )
                continue

            html = self._page_content.get(entry.src_uri)
            if runtime.config.save_html and html is not None:
                self._persist_html_snapshot(output_root, entry.src_uri, html)

            document = self._page_document(
                entry,
                abs_src=abs_src,
                html=html,
                base_level=effective_level
                - template_slot_levels.get(target_slot, template_base),
                output_root=output_root,
                emitter=emitter,
            )
            if document is None:
                continue

            chain.book = self._book_labels(runtime, entry)
            try:
                result = convert_document(
                    document,
                    output_dir=output_root,
                    request=request,
                    slot_overrides=None,
                    template_overrides=overrides,
                    state=document_state,
                    template_runtime=template_runtime,
                    wrap_document=False,
                    emitter=emitter,
                    preloaded_bibliography=bibliography_collection,
                    seen_bibliography_issues=seen_bibliography_issues,
                    resolution=chain,
                )
            except PluginError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                log.exception("TeXSmith failed while rendering page '%s'.", entry.title)
                detail = (
                    format_rendering_error(exc)
                    if isinstance(exc, LatexRenderingError)
                    else str(exc)
                )
                raise PluginError(
                    f"LaTeX rendering failed for page '{entry.title}': {detail}"
                ) from exc

            document_state = result.document_state or document_state
            if result.context is not None and result.context.bibliography_collection:
                bibliography_collection = result.context.bibliography_collection
                bibliography_map = dict(result.context.bibliography_map)

            fragment = result.latex_output
            page_rel_path = self._resolve_page_fragment_path(entry, page_index)
            page_abs_path = output_root / page_rel_path
            page_abs_path.parent.mkdir(parents=True, exist_ok=True)
            page_abs_path.write_text(fragment, encoding="utf-8")
            target_buffer_embed.append(fragment)
            target_buffer_link.append(f"\\input{{{page_rel_path.as_posix()}}}")
            # A page's front matter may route parts of it to other slots.
            for slot_name, slot_text in result.slot_outputs.items():
                if slot_name == result.default_slot or not slot_text.strip():
                    continue
                if slot_name in slot_buffers_embed:
                    slot_buffers_embed[slot_name].append(slot_text)
                    slot_buffers_link[slot_name].append(slot_text)

            assets_map.update(result.assets_map)

        final_state = document_state or DocumentState(
            bibliography=dict(bibliography_map)
        )

        slot_outputs_embed = {
            name: "\n\n".join(parts) for name, parts in slot_buffers_embed.items()
        }
        slot_outputs_link = {
            name: "\n\n".join(parts) for name, parts in slot_buffers_link.items()
        }

        bibliography_output: Path | None = None
        if (
            bibliography_collection is not None
            and final_state.citations
            and bibliography_map
        ):
            bibliography_output = output_root / "texsmith-bibliography.bib"
            bibliography_output.parent.mkdir(parents=True, exist_ok=True)
            bibliography_collection.write_bibtex(
                bibliography_output, keys=final_state.citations
            )
            overrides.setdefault("bibliography", bibliography_output.stem)
            overrides.setdefault("bibliography_resource", bibliography_output.name)

        fragment_names = (
            overrides.get("fragments") or template_runtime.extras.get("fragments") or []
        )

        folder = runtime.config.folder
        stem = (
            folder.name if isinstance(folder, Path) else folder if folder else "index"
        )

        try:
            wrap_result = wrap_template_document(
                template=template_runtime.instance,
                default_slot=template_runtime.default_slot,
                slot_outputs=slot_outputs_embed,
                slot_output_overrides=None if embed_fragments else slot_outputs_link,
                document_state=final_state,
                template_overrides=overrides,
                output_dir=output_root,
                copy_assets=copy_assets,
                output_name=f"{stem}.tex",
                bibliography_path=bibliography_output,
                emitter=emitter,
                fragments=fragment_names,
                template_runtime=template_runtime,
            )
        except TemplateError as exc:
            raise PluginError(f"Failed to wrap LaTeX document: {exc}") from exc

        template_context = wrap_result.template_context or {}
        tex_path = wrap_result.output_path or (output_root / f"{stem}.tex")
        log.info("TeXSmith wrote '%s'.", tex_path.relative_to(self._build_root))
        self._announce_latexmk_command(output_root, tex_path)

        template_assets: list[Path] = list(wrap_result.asset_paths or [])
        template_assets.extend(
            Path(destination)
            for _, destination in getattr(wrap_result, "asset_pairs", [])
        )

        if assets_map:
            self._write_assets_manifest(output_root, assets_map)

        if self._latex_config.clean_assets and copy_assets:
            referenced_assets = [*assets_map.values(), *template_assets]
            self._prune_unused_assets(output_root, referenced_assets)

        self._copy_extra_files(runtime.config, output_root)
        self._publish_snippet_assets(output_root)
        if self._auto_build:
            self._run_pdf_build(
                output_root=output_root,
                tex_path=tex_path,
                template_context=template_context,
                document_state=final_state,
                bibliography_present=bool(bibliography_output),
            )

    # -- Page documents (the PDF input) ------------------------------------

    def _book_start(self, runtime: BookRuntime) -> dict[str, int]:
        """Where the site's chain stood before the book's first page."""
        if self._site is None:
            return {}
        for entry in runtime.entries:
            if entry.is_page and entry.src_uri:
                record = self._site.record(entry.src_uri)
                if record is not None:
                    return dict(record.start)
        return {}

    def _book_labels(
        self, runtime: BookRuntime, entry: NavEntry
    ) -> list[dict[str, Any]]:
        """The labels of the book's other pages, for the ``resolve`` of ``entry``.

        The LaTeX writer prints a sibling as text (design 06 §Sibling
        documents), so only labels whose text is the same on both media are
        handed over: user counters (tmark numbers them in print too) and
        headings (their title). A backend-numbered float of another page
        stays ``[?key]`` rather than carrying the site's number into the PDF.
        """
        if self._site is None:
            return []
        book: list[dict[str, Any]] = []
        for other in runtime.entries:
            if not other.is_page or not other.src_uri or other.src_uri == entry.src_uri:
                continue
            record = self._site.record(other.src_uri)
            if record is None:
                continue
            for label in record.labels:
                prefix = label.get("prefix")
                kind = label.get("kind")
                heading = kind == "header"
                user_counter = bool(prefix) and (
                    prefix in self._site.counters or prefix in record.page_counters
                )
                if not (heading or user_counter):
                    continue
                item = dict(label)
                if heading and prefix not in HEADING_PREFIXES:
                    item["kind"] = "counter_item"
                book.append(item)
        return book

    def _page_document(
        self,
        entry: NavEntry,
        *,
        abs_src: Path,
        html: str | None,
        base_level: int,
        output_root: Path,
        emitter: LoggingEmitter,
    ) -> Document | None:
        """The :class:`Document` of a page for the book: its source through tmark.

        The source is the text MkDocs handed ``on_page_markdown`` (macros
        expanded), with the page metadata and the site declarations back in
        front of it, written under ``sources/`` of the book so the exact input
        of the PDF is inspectable. A page with ``press.reader: html`` in its
        front matter is read from its rendered ``page.content`` instead.
        """
        assert entry.src_uri is not None
        record = self._site.record(entry.src_uri) if self._site is not None else None
        meta = (
            record.meta
            if record is not None
            else self._page_meta.get(entry.src_uri) or {}
        )
        title_strategy = TitleStrategy.DROP if entry.drop_title else TitleStrategy.KEEP
        numbered = entry.numbered
        declared_numbered = meta.get("numbered")
        if isinstance(declared_numbered, bool):
            numbered = declared_numbered

        if _press_reader(meta) == "html":
            if html is None:
                log.warning(
                    "Skipping page '%s': 'press.reader: html' "
                    "but no rendered HTML was captured.",
                    entry.title,
                )
                return None
            snapshot = self._persist_html_snapshot(output_root, entry.src_uri, html)
            document = Document.from_html(
                snapshot,
                full_document=True,
                base_level=base_level,
                title_strategy=title_strategy,
                numbered=numbered,
                emitter=emitter,
            )
            # Relative assets resolve against the page, not the snapshot.
            return document.evolve(source_path=abs_src)

        if record is None or not record.lowered:
            source_path = abs_src
        else:
            source_path = self._persist_source(output_root, entry.src_uri, record)
        document = Document.from_markdown(
            source_path,
            base_level=base_level,
            title_strategy=title_strategy,
            numbered=numbered,
            emitter=emitter,
        )
        if source_path != abs_src:
            document = document.evolve(source_path=abs_src)
        return document

    def _persist_source(
        self, output_root: Path, src_uri: str, record: PageRecord
    ) -> Path:
        """Write the page's source as the PDF reads it: merged metadata, stored body."""
        meta = dict(record.meta)
        counters = self._site.counters if self._site is not None else {}
        page_counters = meta.pop("counters", None)
        merged_counters: dict[str, Any] = dict(counters)
        press = meta.get("press")
        press = dict(press) if isinstance(press, Mapping) else {}
        declare = press.get("declare")
        declare = dict(declare) if isinstance(declare, Mapping) else {}
        if isinstance(declare.get("counters"), Mapping):
            merged_counters.update(declare["counters"])
        if isinstance(page_counters, Mapping):
            merged_counters.update(page_counters)
        if merged_counters:
            declare["counters"] = merged_counters
            press["declare"] = declare
        if press:
            meta["press"] = press
        header = ""
        if meta:
            header = (
                "---\n"
                + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
                + "---\n"
            )
        target = output_root / "sources" / Path(src_uri)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(header + record.body, encoding="utf-8")
        return target

    def _flatten_navigation(
        self,
        root: StructureItem,
        config: BookConfig,
        slots: Mapping[str, set[str]] | None = None,
    ) -> list[NavEntry]:
        entries: list[NavEntry] = []
        slots_map = slots or {}

        def walk(
            node: StructureItem,
            level: int,
            numbered: bool,
            part: str,
            front_flag: bool,
            back_flag: bool,
            active_slot: str | None,
        ) -> None:
            is_front = front_flag or (node.title in config.frontmatter)
            is_back = back_flag or (node.title in config.backmatter)
            segment = "frontmatter" if is_front else "backmatter" if is_back else part
            resolved_slot = active_slot or self._match_slot(node.title, slots_map)

            drop_title = False
            node_numbered = numbered
            if node.is_page and config.index_is_foreword:
                filename = getattr(node.file, "name", "")
                if filename == "index":
                    node_numbered = False
                    if config.drop_title_index:
                        drop_title = True

            entry = NavEntry(
                title=node.title or "",
                level=level,
                numbered=node_numbered,
                drop_title=drop_title,
                part=segment,
                is_page=node.is_page,
                slot=resolved_slot,
                src_path=getattr(node.file, "src_path", None) if node.is_page else None,
                src_uri=getattr(node.file, "src_uri", None) if node.is_page else None,
                abs_src_path=Path(node.file.abs_src_path)
                if node.is_page and getattr(node.file, "abs_src_path", None)
                else None,
            )
            entries.append(entry)

            next_level = level + 1
            for child in node.children or []:
                walk(
                    child,
                    next_level,
                    node_numbered,
                    segment,
                    is_front,
                    is_back,
                    resolved_slot,
                )

        walk(root, config.base_level, True, "mainmatter", False, False, None)
        return entries

    def _flatten_full_navigation(
        self,
        nav: Navigation,
        config: BookConfig,
        slots: Mapping[str, set[str]] | None = None,
    ) -> list[NavEntry]:
        entries: list[NavEntry] = []
        for item in nav.items:
            entries.extend(self._flatten_navigation(item, config, slots))
        return entries

    def _find_item_by_title(
        self, items: Iterable[StructureItem], title: str
    ) -> StructureItem | None:
        for item in items:
            if item.title == title:
                return item
            match = self._find_item_by_title(item.children or [], title)
            if match is not None:
                return match
        return None

    def _resolve_output_root(self, config: BookConfig) -> Path:
        base_dir = Path(config.build_dir or self._build_root)
        folder = config.folder
        candidate = base_dir if not folder else base_dir / folder
        return candidate.resolve()

    @staticmethod
    def _normalise_label(value: str | None) -> str:
        """Return a case-insensitive label suitable for slot matching."""
        if value is None:
            return ""
        return " ".join(str(value).split()).casefold()

    def _normalise_slot_requests(self, payload: Any) -> dict[str, set[str]]:
        """Return normalised slot selectors keyed by slot name."""
        if payload is None:
            return {}
        if not isinstance(payload, Mapping):
            log.warning(
                "Ignoring invalid 'slots' mapping: expected a mapping, got %r",
                type(payload),
            )
            return {}

        slots: dict[str, set[str]] = {}
        for slot_name, selectors in payload.items():
            name = str(slot_name).strip()
            if not name:
                continue
            titles: set[str] = set()
            if isinstance(selectors, str):
                titles.add(self._normalise_label(selectors))
            elif isinstance(selectors, Iterable) and not isinstance(
                selectors, (bytes, Mapping, str)
            ):
                for selector in selectors:
                    if isinstance(selector, str) and selector.strip():
                        titles.add(self._normalise_label(selector))
            elif selectors is not None:
                log.warning(
                    (
                        "Slot '%s' selectors must be strings or lists of strings; "
                        "ignoring %r."
                    ),
                    name,
                    type(selectors),
                )
            if titles:
                slots[name] = titles
        return slots

    def _match_slot(
        self, title: str | None, slots: Mapping[str, set[str]]
    ) -> str | None:
        """Return the slot name matching the provided title, if any."""
        if not slots:
            return None
        key = self._normalise_label(title)
        for slot, candidates in slots.items():
            if key and key in candidates:
                return slot
        return None

    def _normalise_press_overrides(
        self, payload: Any, paper: Any | None
    ) -> dict[str, Any]:
        """Return press overrides merged with a paper alias."""
        press: dict[str, Any] = {}
        if isinstance(payload, Mapping):
            press.update(payload)
        elif payload is not None:
            log.warning(
                "Ignoring invalid 'press' override: expected a mapping, got %r",
                type(payload),
            )

        if paper is not None:
            press["paper"] = paper
        return press

    def _build_snippet_urls(
        self, page: Any, block: snippet.SnippetBlock
    ) -> tuple[str, str]:
        self._ensure_site_snippet_assets(page, block)
        pdf_name = snippet.asset_filename(block.digest, ".pdf")
        png_name = snippet.asset_filename(block.digest, ".png")
        return (
            self._relative_snippet_path(page, pdf_name),
            self._relative_snippet_path(page, png_name),
        )

    def _relative_snippet_path(self, page: Any, filename: str) -> str:
        file_attr = getattr(page, "file", None)
        dest_path = getattr(file_attr, "dest_path", "") if file_attr else ""
        parent = PurePosixPath(dest_path).parent
        if str(parent) in {"", "."}:
            prefix = ""
        else:
            depth = len([part for part in parent.parts if part and part != "."])
            prefix = "../" * depth
        return f"{prefix}assets/{snippet.SNIPPET_DIR}/{filename}"

    def _publish_snippet_assets(self, output_root: Path) -> None:
        source_dir = output_root / snippet.SNIPPET_DIR
        site_dir = self._site_dir
        if site_dir is None or not source_dir.exists():
            return
        target_dir = site_dir / "assets" / snippet.SNIPPET_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        for asset in source_dir.glob("*.pdf"):
            shutil.copy2(asset, target_dir / asset.name)
        for asset in source_dir.glob("*.png"):
            shutil.copy2(asset, target_dir / asset.name)

    def _run_pdf_build(
        self,
        *,
        output_root: Path,
        tex_path: Path,
        template_context: Mapping[str, Any],
        document_state: DocumentState,
        bibliography_present: bool,
    ) -> None:
        env_engine = os.environ.get("TEXSMITH_ENGINE")
        engine_preference = env_engine.strip() if env_engine else "tectonic"
        use_system_tectonic = self._env_flag_enabled(
            os.environ.get("TEXSMITH_SYSTEM_TECTONIC")
        )

        template_engine = None
        raw_engine = template_context.get("latex_engine")
        if isinstance(raw_engine, str) and raw_engine.strip():
            template_engine = raw_engine.strip()

        engine_choice = resolve_engine(engine_preference, template_engine)

        features = compute_features(
            requires_shell_escape=bool(
                template_context.get("requires_shell_escape", False)
            ),
            bibliography=bibliography_present,
            document_state=document_state,
            template_context=template_context,
        )

        tectonic_binary: Path | None = None
        biber_binary: Path | None = None
        makeglossaries_binary: Path | None = None
        bundled_bin: Path | None = None
        if engine_choice.backend == "tectonic":
            try:
                selection = select_tectonic_binary(
                    use_system_tectonic,
                    console=None,
                )
                tectonic_binary = selection.path
                if features.bibliography and not use_system_tectonic:
                    biber_binary = select_biber_binary(console=None)
                    bundled_bin = biber_binary.parent
                if features.has_glossary:
                    glossaries = select_makeglossaries(console=None)
                    makeglossaries_binary = glossaries.path
                    if glossaries.source == "bundled":
                        bundled_bin = bundled_bin or glossaries.path.parent
            except (
                TectonicAcquisitionError,
                BiberAcquisitionError,
                MakeglossariesAcquisitionError,
            ) as exc:
                raise PluginError(str(exc)) from exc

        available_bins: dict[str, Path] = {}
        if biber_binary:
            available_bins["biber"] = biber_binary
        if makeglossaries_binary:
            available_bins["makeglossaries"] = makeglossaries_binary

        missing = missing_dependencies(
            engine_choice,
            features,
            use_system_tectonic=use_system_tectonic
            if engine_choice.backend == "tectonic"
            else False,
            available_binaries=available_bins or None,
        )
        if missing:
            readable = ", ".join(sorted(set(missing)))
            raise PluginError(
                f"LaTeX build skipped for '{tex_path.name}': "
                f"missing dependencies ({readable})."
            )

        if engine_choice.backend == "latexmk":
            self._ensure_latexmkrc(
                tex_path=tex_path,
                engine=engine_choice.latexmk_engine,
                features=features,
            )

        command_plan = ensure_command_paths(
            build_engine_command(
                engine_choice,
                features,
                main_tex_path=tex_path,
                tectonic_binary=tectonic_binary,
            )
        )

        env = build_tex_env(
            tex_path.parent,
            isolate_cache=False,
            extra_path=bundled_bin,
            biber_path=biber_binary,
        )
        console = Console(
            file=sys.stdout,
            force_terminal=False,
            color_system=None,
            no_color=True,
        )

        engine_label = (
            engine_choice.latexmk_engine
            if engine_choice.backend == "latexmk"
            else "tectonic"
        )
        bundle_label = self._relativise(
            self._project_dir or output_root, tex_path.parent
        )
        log.info(
            "TEXSMITH_BUILD enabled: building '%s' with %s.",
            bundle_label.as_posix(),
            engine_label,
        )

        result = run_engine_command(
            command_plan,
            backend=engine_choice.backend,
            workdir=tex_path.parent,
            env=env,
            console=console,
            verbosity=1,
        )

        if result.messages:
            self._log_engine_messages(result.messages)

        if result.returncode != 0:
            log_path = self._relativise(tex_path.parent, result.log_path)
            raise PluginError(
                f"LaTeX build failed for '{tex_path.name}' (see {log_path})."
            )

        pdf_path = result.pdf_path
        if not pdf_path.is_absolute():
            pdf_path = (tex_path.parent / pdf_path).resolve()
        pdf_label = self._relativise(self._project_dir or tex_path.parent, pdf_path)
        log.info("LaTeX build complete: %s", pdf_label)

    def _ensure_latexmkrc(
        self, *, tex_path: Path, engine: str | None, features: EngineFeatures
    ) -> Path | None:
        rc_path = tex_path.parent / ".latexmkrc"
        if rc_path.exists():
            return rc_path

        try:
            content = build_latexmkrc_content(
                root_filename=tex_path.stem,
                engine=engine,
                requires_shell_escape=features.requires_shell_escape,
                bibliography=features.bibliography,
                index_engine=features.index_engine,
                has_index=features.has_index,
                has_glossary=features.has_glossary,
            )
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Unable to prepare latexmkrc for '%s': %s", tex_path.name, exc)
            return None

        try:
            rc_path.write_text(content, encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem
            log.warning("Failed to write latexmkrc for '%s': %s", tex_path.name, exc)
            return None

        return rc_path

    def _log_engine_messages(self, messages: Iterable[LatexMessage]) -> None:
        for message in messages:
            summary = message.summary.strip()
            details = "; ".join(
                part.strip() for part in message.details if part.strip()
            )
            payload = f"{summary}: {details}" if details else summary

            if message.severity is LatexMessageSeverity.ERROR:
                log.error("LaTeX: %s", payload)
            elif message.severity is LatexMessageSeverity.WARNING:
                log.warning("LaTeX: %s", payload)
            else:
                log.info("LaTeX: %s", payload)

    def _ensure_site_snippet_assets(
        self, page: Any, block: snippet.SnippetBlock
    ) -> None:
        dest_dir = self._site_snippet_dir()
        emitter = self._diagnostic_emitter or _MkdocsEmitter(
            logger_obj=log, debug_enabled=self._is_serve
        )
        abs_src = getattr(page.file, "abs_src_path", None)
        if not abs_src:
            raise PluginError(
                "Unable to determine the source path for snippet rendering."
            )
        source_path = Path(abs_src)
        try:
            snippet.ensure_snippet_assets(
                block,
                output_dir=dest_dir,
                source_path=source_path,
                emitter=emitter,
            )
        except Exception as exc:  # pragma: no cover - passthrough
            raise PluginError(
                f"Failed to render snippet on page '{page.file.src_path}': {exc}"
            ) from exc

    def _site_snippet_dir(self) -> Path:
        site_dir = self._site_dir
        if site_dir is None:
            config_site = getattr(self._mkdocs_config, "site_dir", None)
            if config_site:
                site_dir = Path(config_site).resolve()
                self._site_dir = site_dir
            else:
                raise PluginError("MkDocs site directory is not initialised.")
        target_dir = site_dir / "assets" / snippet.SNIPPET_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def _persist_html_snapshot(
        self, output_root: Path, src_path: str, html: str
    ) -> Path:
        snapshot_path = output_root / "html" / Path(src_path).with_suffix(".html")
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(html, encoding="utf-8")
        return snapshot_path

    def _write_assets_manifest(
        self, output_root: Path, assets_map: dict[str, Path]
    ) -> None:
        manifest = {
            key: self._relativise(output_root, path).as_posix()
            for key, path in assets_map.items()
        }
        manifest_path = output_root / "assets_map.yml"
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=True), encoding="utf-8"
        )

    def _prune_unused_assets(
        self, output_root: Path, referenced: Iterable[Path]
    ) -> None:
        assets_dir = output_root / "assets"
        if not assets_dir.exists():
            return
        resolved_paths: set[Path] = set()
        for path in referenced:
            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = (output_root / candidate).resolve()
            else:
                try:
                    candidate = candidate.resolve()
                except OSError:
                    continue
            resolved_paths.add(candidate)

        for candidate in assets_dir.rglob("*"):
            if not candidate.is_file():
                continue
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved not in resolved_paths:
                candidate.unlink()

    def _copy_extra_files(self, config: BookConfig, output_root: Path) -> None:
        project_dir = self._project_dir
        if project_dir is None:
            return

        for pattern, destination in config.copy_files.items():
            src_pattern = (project_dir / pattern).resolve()
            dest_candidate = output_root / destination

            matched = list(src_pattern.parent.glob(src_pattern.name))
            if not matched:
                log.warning("Copy pattern '%s' resolved no files.", pattern)
                continue

            for src in matched:
                if dest_candidate.is_dir() or destination.endswith("/"):
                    target = dest_candidate / src.name
                elif dest_candidate.suffix:
                    target = dest_candidate
                else:
                    target = dest_candidate / src.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                log.info("Copied '%s' to '%s'.", src, target)

    def _resolve_page_fragment_path(self, entry: NavEntry, index: int) -> Path:
        base = entry.src_path or entry.title or f"page-{index}"
        normalised = slugify(base.replace("/", "-"), separator="-")
        if not normalised:
            normalised = f"page-{index}"
        return Path("pages") / f"{normalised}.tex"

    def _announce_latexmk_command(self, output_root: Path, tex_path: Path) -> None:
        """Log a helpful hint showing how to compile the generated project."""
        base_dir = self._project_dir or output_root
        bundle_path = self._relativise(base_dir, output_root)
        try:
            tex_rel = tex_path.relative_to(output_root)
        except ValueError:
            tex_rel = tex_path

        log.info(
            (
                "Press bundle ready in '%s'. "
                "Run 'latexmk -cd %s/%s' to build the documentation."
            ),
            bundle_path.as_posix(),
            bundle_path.as_posix(),
            tex_rel.as_posix(),
        )

    def _inline_bibliography_source_path(self, label: str) -> Path:
        slug = slugify(label, separator="-")
        if not slug:
            slug = "frontmatter"
        return Path(f"frontmatter-{slug}.bib")

    def _coerce_paths(
        self, values: Iterable[str], *, relative_to: Path | None = None
    ) -> list[Path]:
        base = relative_to or self._project_dir or Path.cwd()
        paths: list[Path] = []
        for raw in values:
            candidate = Path(raw)
            raw_path = os.fspath(raw)
            # Windows treats POSIX-style roots ("/tmp/foo") as missing a drive
            # letter, so pathlib reports them as relative. Preserve already-absolute
            # inputs by checking for either separator prefix as well.
            is_absolute = (
                os.path.isabs(raw_path)
                or posixpath.isabs(raw_path)
                or raw_path.startswith(("/", "\\"))
            )
            if not is_absolute:
                candidate = (base / candidate).resolve()
            paths.append(candidate)
        return paths

    def _relativise(self, base: Path, target: Path) -> Path:
        try:
            return target.relative_to(base)
        except ValueError:
            try:
                return Path(os.path.relpath(target, base))
            except ValueError:
                return target


def _nav_heading(title: str, *, level: int, numbered: bool, lang: str | None) -> str:
    """The LaTeX heading of a nav section — a nav entry that is not a page.

    A section of the nav has no source, so there is nothing to parse: build the
    one-header document the writer expects and let ``tmark.write`` choose the
    sectioning command for ``level``, exactly as it does for a page's own
    headers.
    """
    from texsmith.core.conversion.bodies import build_writer_options
    from texsmith.ir import codec, model
    import tmark

    document = model.Document(
        blocks=(model.Header(level=1, content=(model.Str(text=title),)),)
    )
    payload = codec.encode_document(document)
    payload["tmark"] = tmark.version()
    options = build_writer_options(
        backend="latex", language=lang, base_level=level, numbered=numbered
    )
    return str(tmark.write(payload, "latex", options).get("text") or "")


def _press_reader(meta: Mapping[str, Any]) -> str | None:
    """``press.reader`` of a page's front matter (``html``: the HtmlReader fallback)."""
    press = meta.get("press")
    if isinstance(press, Mapping):
        reader = press.get("reader")
        if isinstance(reader, str) and reader.strip():
            return reader.strip().lower()
    reader = meta.get("press.reader")
    if isinstance(reader, str) and reader.strip():
        return reader.strip().lower()
    return None


def _stylesheet() -> str:
    """The ``texsmith.css`` shipped with the plugin."""
    return (
        resources.files(__package__)
        .joinpath("assets/texsmith.css")
        .read_text(encoding="utf-8")
    )


__all__ = ["LatexPlugin"]
