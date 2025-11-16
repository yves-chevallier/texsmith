from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
from typing import Any
import warnings
from warnings import WarningMessage

from mkdocs.config import config_options
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin
from mkdocs.structure import StructureItem
from mkdocs.structure.files import Files
from mkdocs.structure.nav import Navigation
from mkdocs.utils import log
from pybtex.exceptions import PybtexError
from slugify import slugify
from texsmith.adapters.latex import LaTeXFormatter, LaTeXRenderer
from texsmith.adapters.plugins import material
from texsmith.core.bibliography import (
    BibliographyCollection,
    DoiBibliographyFetcher,
    DoiLookupError,
    bibliography_data_from_inline_entry,
    bibliography_data_from_string,
)
from texsmith.core.config import BookConfig, LaTeXConfig
from texsmith.core.context import DocumentState
from texsmith.core.conversion import (
    ensure_fallback_converters,
    extract_front_matter_bibliography,
    render_with_fallback,
)
from texsmith.core.conversion.debug import format_rendering_error
from texsmith.core.conversion.inputs import (
    InlineBibliographyEntry,
    InlineBibliographyValidationError,
)
from texsmith.core.exceptions import LatexRenderingError
from texsmith.core.templates import (
    TemplateError,
    TemplateSlot,
    copy_template_assets,
    load_template_runtime,
    normalise_template_language,
)
import yaml


AUTO_BASE_LEVEL = -2
FULL_NAVIGATION_ROOT = "__texsmith_full_navigation__"


@dataclass(slots=True)
class BookExtras:
    """Container for plugin-specific book options."""

    template: str | None = None
    template_overrides: dict[str, Any] = field(default_factory=dict)
    bibliography: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class NavEntry:
    """Flattened navigation entry with rendering metadata."""

    title: str
    level: int
    numbered: bool
    drop_title: bool
    part: str
    is_page: bool
    src_path: str | None = None
    abs_src_path: Path | None = None


@dataclass(slots=True)
class BookRuntime:
    """Runtime representation of a configured book."""

    config: BookConfig
    extras: BookExtras
    section: StructureItem | None = None
    entries: list[NavEntry] = field(default_factory=list)


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
        ("language", config_options.Type((str, type(None)), default=None)),
        ("bibliography", config_options.Type(list, default=[])),
        ("books", config_options.Type(list, default=[])),
        ("template_overrides", config_options.Type(dict, default={})),
        ("register_material", config_options.Type(bool, default=True)),
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
        self._nav: Navigation | None = None

    # -- MkDocs lifecycle -------------------------------------------------

    def on_startup(self, command: str, dirty: bool) -> None:  # pragma: no cover - hook
        self._is_serve = command == "serve"

    def on_config(
        self, config: MkDocsConfig
    ) -> MkDocsConfig:  # pragma: no cover - hook
        self._enabled = bool(self.config.get("enabled", True))
        self._mkdocs_config = config

        if not self._enabled or self._is_serve:
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
        self._global_template_overrides = dict(
            self.config.get("template_overrides") or {}
        )

        self._latex_config = self._build_latex_config(language)
        ensure_fallback_converters()
        return config

    def on_nav(
        self,
        nav: Navigation,
        config: MkDocsConfig,
        files: Files,  # noqa: ARG002 - required by MkDocs
    ) -> Navigation:  # pragma: no cover - hook
        if not self._enabled or self._is_serve:
            return nav

        self._nav = nav
        return nav

    def on_post_page(
        self,
        output: str,
        page,
        config: MkDocsConfig,
    ) -> str:  # pragma: no cover - hook
        if not self._enabled or self._is_serve:
            return output

        src_path = page.file.src_path
        self._page_content[src_path] = page.content
        self._page_meta[src_path] = dict(page.meta or {})
        self._page_sources[src_path] = Path(page.file.abs_src_path)
        return output

    def on_post_build(self, config: MkDocsConfig) -> None:  # pragma: no cover - hook
        if not self._enabled or self._is_serve:
            return

        if self._latex_config is None or self._build_root is None:
            raise PluginError("TeXSmith plugin is not initialised correctly.")

        self._prepare_books_if_needed()

        for runtime in self._books:
            self._render_book(runtime)

    # -- Helpers ----------------------------------------------------------

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
            book_extra = BookExtras(
                template=data.pop("template", None),
                template_overrides=dict(data.pop("template_overrides", {}) or {}),
                bibliography=self._coerce_paths(
                    data.pop("bibliography", []), relative_to=project_dir
                ),
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
            entries = self._flatten_full_navigation(nav, book_config)
        else:
            root_item = self._find_item_by_title(nav.items, book_config.root)
            if root_item is None:
                raise PluginError(
                    f"Root section '{book_config.root}' not found in navigation."
                )
            entries = self._flatten_navigation(root_item, book_config)

        runtime = BookRuntime(config=book_config, extras=extras, section=root_item)
        runtime.entries = entries
        self._books.append(runtime)

    def _render_book(self, runtime: BookRuntime) -> None:
        output_root = self._resolve_output_root(runtime.config)
        output_root.mkdir(parents=True, exist_ok=True)

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

        formatter_overrides = dict(template_runtime.formatter_overrides)
        heading_formatter = LaTeXFormatter()
        for name, override_path in formatter_overrides.items():
            heading_formatter.override_template(name, override_path)

        def renderer_factory() -> LaTeXRenderer:
            formatter = LaTeXFormatter()
            for name, override_path in formatter_overrides.items():
                formatter.override_template(name, override_path)
            renderer = LaTeXRenderer(
                config=runtime.config,
                formatter=formatter,
                output_root=output_root,
                parser=parser_backend,
                copy_assets=copy_assets,
            )
            if self.config.get("register_material", True):
                material.register(renderer)
            return renderer

        inline_bibliography_specs: list[
            tuple[str, str, dict[str, InlineBibliographyEntry]]
        ] = []
        for entry in runtime.entries:
            if not entry.is_page or not entry.src_path:
                continue
            page_meta = self._page_meta.get(entry.src_path) or {}
            try:
                inline_map = extract_front_matter_bibliography(page_meta)
            except InlineBibliographyValidationError as exc:
                log.warning(
                    "Inline bibliography on page '%s' is invalid: %s",
                    entry.title or entry.src_path,
                    exc,
                )
                inline_map = {}
            if inline_map:
                inline_bibliography_specs.append(
                    (entry.src_path, entry.title or entry.src_path, inline_map)
                )

        bibliography_files = [
            *self._global_bibliography,
            *runtime.extras.bibliography,
        ]
        bibliography_collection: BibliographyCollection | None = None
        bibliography_map: dict[str, dict[str, Any]] = {}
        if bibliography_files or inline_bibliography_specs:
            bibliography_collection = BibliographyCollection()
            if bibliography_files:
                bibliography_collection.load_files(bibliography_files)
            if inline_bibliography_specs:
                fetcher = DoiBibliographyFetcher()
                for src_path, label, mapping in inline_bibliography_specs:
                    self._load_inline_bibliography(
                        bibliography_collection,
                        mapping,
                        source_label=label or src_path,
                        fetcher=fetcher,
                    )
            bibliography_map = bibliography_collection.to_dict()
            for issue in bibliography_collection.issues:
                prefix = f"[{issue.key}] " if issue.key else ""
                source = f" ({issue.source})" if issue.source else ""
                log.warning("%s%s%s", prefix, issue.message, source)

        frontmatter: list[str] = []
        mainmatter: list[str] = []
        backmatter: list[str] = []

        document_state: DocumentState | None = None
        assets_map: dict[str, Path] = {}
        last_renderer: LaTeXRenderer | None = None

        def track_renderer() -> LaTeXRenderer:
            nonlocal last_renderer
            last_renderer = renderer_factory()
            return last_renderer

        raw_language = runtime.config.language or self._latex_config.language
        language = normalise_template_language(raw_language)
        runtime_language = language or raw_language

        for page_index, entry in enumerate(runtime.entries):
            target_buffer = (
                frontmatter
                if entry.part == "frontmatter"
                else backmatter
                if entry.part == "backmatter"
                else mainmatter
            )

            if not entry.is_page:
                if entry.level > runtime.config.base_level:
                    fragment = heading_formatter.heading(
                        entry.title, level=entry.level, numbered=entry.numbered
                    )
                    target_buffer.append(fragment)
                continue

            if not entry.src_path or entry.src_path not in self._page_content:
                log.warning(
                    "Skipping page '%s' because no rendered HTML was captured.",
                    entry.title,
                )
                continue

            html = self._page_content[entry.src_path]
            abs_src = entry.abs_src_path or self._page_sources.get(entry.src_path)
            if abs_src is None:
                log.warning(
                    "Cannot determine source path for page '%s'; skipping.",
                    entry.title,
                )
                continue

            if runtime.config.save_html:
                self._persist_html_snapshot(output_root, entry.src_path, html)

            runtime_payload = {
                "base_level": entry.level,
                "numbered": entry.numbered,
                "drop_title": entry.drop_title,
                "source_dir": abs_src.parent,
                "document_path": abs_src,
                "language": runtime_language,
                "template": template_runtime.name,
                "copy_assets": copy_assets,
            }

            try:
                with warnings.catch_warnings(record=True) as captured_warnings:
                    warnings.simplefilter("always")
                    fragment, document_state = render_with_fallback(
                        track_renderer,
                        html,
                        runtime_payload,
                        bibliography_map,
                        state=document_state,
                    )
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

            for warning in captured_warnings:
                self._log_render_warning(entry, warning)

            page_rel_path = self._resolve_page_fragment_path(entry, page_index)
            page_abs_path = output_root / page_rel_path
            page_abs_path.parent.mkdir(parents=True, exist_ok=True)
            page_abs_path.write_text(fragment, encoding="utf-8")
            target_buffer.append(f"\\input{{{page_rel_path.as_posix()}}}")

            if last_renderer is not None:
                for key, path in last_renderer.assets.items():
                    assets_map[key] = path

        final_state = document_state or DocumentState(
            bibliography=dict(bibliography_map)
        )

        overrides = dict(self._global_template_overrides)
        overrides.update(runtime.extras.template_overrides)
        overrides.setdefault("title", runtime.config.title)
        overrides.setdefault("subtitle", runtime.config.subtitle)
        overrides.setdefault("author", runtime.config.author)
        overrides.setdefault("email", runtime.config.email)
        overrides.setdefault("year", runtime.config.year)
        if language:
            overrides.setdefault("language", language)
        overrides.setdefault("cover", runtime.config.cover.name)
        overrides.setdefault("covercolor", runtime.config.cover.color)
        if runtime.config.cover.logo:
            overrides.setdefault("logo", runtime.config.cover.logo)

        template_context = template_runtime.instance.prepare_context(
            "\n\n".join(mainmatter),
            overrides=overrides,
        )
        template_context["frontmatter"] = "\n\n".join(frontmatter)
        template_context["mainmatter"] = "\n\n".join(mainmatter)
        template_context["backmatter"] = "\n\n".join(backmatter)
        template_context["index_entries"] = final_state.has_index_entries
        index_terms = list(dict.fromkeys(getattr(final_state, "index_entries", [])))
        template_context["has_index"] = bool(index_terms)
        template_context["index_terms"] = [tuple(term) for term in index_terms]
        try:
            from texsmith.index import get_registry
        except ModuleNotFoundError:
            template_context["index_registry"] = [tuple(term) for term in index_terms]
        else:
            template_context["index_registry"] = [
                tuple(term) for term in sorted(get_registry().snapshot())
            ]
        template_context["acronyms"] = final_state.acronyms.copy()
        template_context["glossary"] = final_state.glossary.copy()
        template_context["solutions"] = list(final_state.solutions)
        template_context["citations"] = list(final_state.citations)
        template_context["bibliography_entries"] = final_state.bibliography.copy()

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
            template_context["bibliography"] = bibliography_output.stem
            template_context["bibliography_resource"] = bibliography_output.name

        try:
            latex_document = template_runtime.instance.wrap_document(
                template_context.get(template_runtime.default_slot, ""),
                context=template_context,
            )
        except TemplateError as exc:
            raise PluginError(f"Failed to wrap LaTeX document: {exc}") from exc

        folder = runtime.config.folder
        stem = (
            folder.name if isinstance(folder, Path) else folder if folder else "index"
        )
        tex_path = output_root / f"{stem}.tex"
        tex_path.write_text(latex_document, encoding="utf-8")
        log.info("TeXSmith wrote '%s'.", tex_path.relative_to(self._build_root))
        self._announce_latexmk_command(output_root, tex_path)

        try:
            copy_template_assets(
                template_runtime.instance,
                output_root,
                context=template_context,
                overrides=overrides,
            )
        except TemplateError as exc:
            raise PluginError(f"Failed to copy template assets: {exc}") from exc

        if assets_map:
            self._write_assets_manifest(output_root, assets_map)

        if self._latex_config.clean_assets and copy_assets:
            self._prune_unused_assets(output_root, assets_map.values())

        self._copy_extra_files(runtime.config, output_root)

    def _flatten_navigation(
        self,
        root: StructureItem,
        config: BookConfig,
    ) -> list[NavEntry]:
        entries: list[NavEntry] = []

        def walk(
            node: StructureItem,
            level: int,
            numbered: bool,
            part: str,
            front_flag: bool,
            back_flag: bool,
        ) -> None:
            is_front = front_flag or (node.title in config.frontmatter)
            is_back = back_flag or (node.title in config.backmatter)
            segment = "frontmatter" if is_front else "backmatter" if is_back else part

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
                src_path=getattr(node.file, "src_path", None) if node.is_page else None,
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
                )

        walk(root, config.base_level, True, "mainmatter", False, False)
        return entries

    def _flatten_full_navigation(
        self,
        nav: Navigation,
        config: BookConfig,
    ) -> list[NavEntry]:
        entries: list[NavEntry] = []
        for item in nav.items:
            entries.extend(self._flatten_navigation(item, config))
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

    def _persist_html_snapshot(
        self, output_root: Path, src_path: str, html: str
    ) -> None:
        snapshot_path = output_root / "html" / Path(src_path).with_suffix(".html")
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(html, encoding="utf-8")

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

    def _log_render_warning(self, entry: NavEntry, warning: WarningMessage) -> None:
        """Surface warnings raised during page rendering as MkDocs warnings."""
        page_label = entry.title or entry.src_path or "page"
        message = str(warning.message).strip()
        category = getattr(warning.category, "__name__", "Warning")

        location = ""
        filename = getattr(warning, "filename", "") or ""
        if filename:
            candidate = Path(filename)
            try:
                candidate = candidate.resolve()
            except OSError:
                pass
            project_dir = self._project_dir
            if project_dir is not None:
                try:
                    candidate = candidate.relative_to(project_dir)
                except ValueError:
                    try:
                        candidate = Path(os.path.relpath(candidate, project_dir))
                    except ValueError:
                        pass
            location = f" ({candidate}:{warning.lineno})"

        log.warning(
            "TeXSmith warning on page '%s': %s%s [%s]",
            page_label,
            message,
            location,
            category,
        )

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

    def _load_inline_bibliography(
        self,
        collection: BibliographyCollection,
        entries: Mapping[str, InlineBibliographyEntry],
        *,
        source_label: str,
        fetcher: DoiBibliographyFetcher,
    ) -> None:
        if not entries:
            return

        source_path = self._inline_bibliography_source_path(source_label)
        for key, entry in entries.items():
            if entry.doi:
                try:
                    payload = fetcher.fetch(entry.doi)
                except DoiLookupError as exc:
                    log.warning(
                        "Failed to resolve DOI '%s' for entry '%s': %s",
                        entry.doi,
                        key,
                        exc,
                    )
                    continue
                try:
                    data = bibliography_data_from_string(payload, key)
                except PybtexError as exc:
                    log.warning(
                        "Failed to parse bibliography entry '%s': %s",
                        key,
                        exc,
                    )
                    continue
                collection.load_data(data, source=source_path)
                continue

            if entry.is_manual:
                try:
                    data = bibliography_data_from_inline_entry(key, entry)
                except (ValueError, PybtexError) as exc:
                    log.warning(
                        "Failed to materialise bibliography entry '%s': %s",
                        key,
                        exc,
                    )
                    continue
                collection.load_data(data, source=source_path)
                continue

            log.warning(
                "Skipping bibliography entry '%s': no DOI and no manual fields.",
                key,
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
            if not candidate.is_absolute():
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


__all__ = ["LatexPlugin"]
