"""The PDF book of a documentation site, built beside whatever serves it.

A book is one PDF assembled from a stretch of the site's navigation: each
section becomes a heading, each page a chapter, and the pages are read from
the Markdown they are written in — through ``tmark.parse`` and the same
reader path the CLI uses — never from the HTML a generator rendered. What a
page contributed to the site's numbering is kept: the resolution chain is
seeded where the site's chain stood before the book's first page, so
``FW-10`` is ``FW-10`` on both media.

Nothing here imports a site generator. MkDocs drives it from its
``on_post_build`` hook, converting its own navigation into the
:mod:`texsmith.site.nav` items below; Zensical has no hook to drive it from,
so ``texsmith site build`` reads the configuration file, resolves the
navigation itself and builds the same book. :func:`build_books` is that
path, and :class:`BookBuilder` is what both of them run.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
import logging
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
from typing import Any

from rich.console import Console
from slugify import slugify
import yaml

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
from texsmith.core.bibliography import BibliographyCollection
from texsmith.core.config import BookConfig, LaTeXConfig
from texsmith.core.context import DocumentState
from texsmith.core.conversion.core import convert_document
from texsmith.core.conversion.models import ConversionRequest
from texsmith.core.conversion.resolution import ResolutionChain, bibliography_paths
from texsmith.core.documents import Document, TitleStrategy
from texsmith.core.exceptions import LatexRenderingError, format_rendering_error
from texsmith.core.templates import (
    TemplateError,
    TemplateSlot,
    load_template_runtime,
    normalise_template_language,
    wrap_template_document,
)
from texsmith.diagnostics import LoggingEmitter, SinkEmitter
from texsmith.site.assets import snippet_dir
from texsmith.site.config import SiteConfig, option, site_counters, web_options
from texsmith.site.index import HEADING_PREFIXES, PageRecord, SiteIndex, SitePage
from texsmith.site.nav import (
    Navigation,
    NavItem,
    NavPage,
    NavSection,
    page_title,
    resolve_navigation,
)


__all__ = [
    "AUTO_BASE_LEVEL",
    "FULL_NAVIGATION_ROOT",
    "Book",
    "BookBuilder",
    "BookError",
    "BookExtras",
    "BookResult",
    "BookSettings",
    "NavEntry",
    "SiteMetadata",
    "book_build_root",
    "build_books",
    "coerce_paths",
    "env_flag_enabled",
    "find_item_by_title",
    "flatten_navigation",
    "item_children",
    "item_title",
    "load_book_settings",
    "match_slot",
    "nav_heading",
    "normalise_label",
    "normalise_press_overrides",
    "normalise_slot_requests",
    "relativise",
]

#: ``base_level`` asking the template to choose the level of a book's chapters.
AUTO_BASE_LEVEL = -2

#: The ``root`` that takes the whole navigation rather than one of its sections.
FULL_NAVIGATION_ROOT = "__texsmith_full_navigation__"

_log = logging.getLogger("texsmith.site")


class BookError(RuntimeError):
    """A book cannot be configured, rendered or compiled."""


def env_flag_enabled(raw: str | None) -> bool:
    """Whether an environment variable spells a truthy flag."""
    if raw is None:
        return False
    normalised = raw.strip().lower()
    return normalised not in {"", "0", "false", "no", "off"}


def coerce_paths(values: Iterable[Any], *, relative_to: Path) -> list[Path]:
    """Resolve each value against ``relative_to`` unless it is already absolute."""
    paths: list[Path] = []
    for raw in values:
        candidate = Path(raw)
        # Windows treats POSIX-style roots ("/tmp/foo") as missing a drive
        # letter, so pathlib reports them as relative. Preserve already-absolute
        # inputs by checking for either separator prefix as well.
        is_absolute = candidate.is_absolute() or os.fspath(raw).startswith(("/", "\\"))
        if not is_absolute:
            candidate = (relative_to / candidate).resolve()
        paths.append(candidate)
    return paths


def relativise(base: Path, target: Path) -> Path:
    """``target`` seen from ``base``, or ``target`` itself when they share no root."""
    try:
        return target.relative_to(base)
    except ValueError:
        try:
            return Path(os.path.relpath(target, base))
        except ValueError:
            return target


@dataclass(slots=True)
class BookExtras:
    """A book's options that :class:`BookConfig` has no field for."""

    template: str | None = None
    template_overrides: dict[str, Any] = field(default_factory=dict)
    bibliography: list[Path] = field(default_factory=list)
    slots: dict[str, set[str]] = field(default_factory=dict)
    press: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NavEntry:
    """One flattened navigation item: a chapter of the book, or a heading."""

    title: str
    level: int
    numbered: bool
    drop_title: bool
    part: str
    is_page: bool
    slot: str | None = None
    src_uri: str | None = None
    abs_src_path: Path | None = None


@dataclass(slots=True)
class Book:
    """One configured book, and the navigation entries it is made of."""

    config: BookConfig
    extras: BookExtras
    entries: list[NavEntry] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class BookResult:
    """Where one book landed."""

    title: str
    output_root: Path
    tex_path: Path
    #: The compiled PDF, ``None`` when the engine was not run.
    pdf_path: Path | None = None


@dataclass(frozen=True, slots=True)
class SiteMetadata:
    """The site-level values a book falls back to for its cover."""

    name: str | None = None
    author: str | None = None
    description: str | None = None
    email: str | None = None
    year: int | None = None

    @staticmethod
    def read(source: Any) -> SiteMetadata:
        """Read the ``site_*`` settings of a configuration, live or parsed."""
        site_date = option(source, "site_date")
        return SiteMetadata(
            name=option(source, "site_name"),
            author=option(source, "site_author"),
            description=option(source, "site_description"),
            email=option(source, "site_email"),
            year=getattr(site_date, "year", None),
        )


@dataclass(slots=True)
class BookSettings:
    """The ``texsmith`` options every book of a site is built with."""

    #: The books' shared model, with ``build_dir``, ``project_dir`` and
    #: ``language`` propagated into each :class:`BookConfig`.
    latex: LaTeXConfig
    books: list[Book]
    template: str
    copy_assets: bool = True
    embed_documents: bool = False
    bibliography: list[Path] = field(default_factory=list)
    template_overrides: dict[str, Any] = field(default_factory=dict)
    snippet_base_paths: list[Path] = field(default_factory=list)

    @property
    def build_dir(self) -> Path:
        """The root every book's output folder sits under."""
        build_dir = self.latex.build_dir
        if build_dir is None:  # pragma: no cover - set by load_book_settings
            raise BookError("The books have no build directory.")
        return build_dir

    @property
    def project_dir(self) -> Path:
        """The directory every relative path of the configuration resolves against."""
        project_dir = self.latex.project_dir
        if project_dir is None:  # pragma: no cover - set by load_book_settings
            raise BookError("The books have no project directory.")
        return project_dir


def book_build_root(options: Mapping[str, Any], project_dir: Path) -> Path:
    """The ``build_dir`` option as an absolute directory."""
    setting = Path(options.get("build_dir") or "press")
    if setting.is_absolute():
        return setting.resolve()
    return (project_dir / setting).resolve()


def load_book_settings(
    options: Mapping[str, Any],
    *,
    project_dir: Path,
    build_dir: Path,
    language: str | None = None,
    snippet_base_paths: Sequence[Path] = (),
    logger: logging.Logger | None = None,
) -> BookSettings:
    """Read the ``texsmith`` options into the settings the books are built with.

    ``options`` is the plugin's option mapping — MkDocs' validated
    ``self.config`` or the ``texsmith:`` block of the configuration file.
    """
    log = logger or _log
    book_specs = options.get("books") or []
    if not isinstance(book_specs, list):
        raise BookError("The 'books' option must be a list.")

    books: list[Book] = []
    for index, raw in enumerate(book_specs, start=1):
        if not isinstance(raw, Mapping):
            raise BookError(f"Book definition #{index} is not a mapping.")
        books.append(_read_book(dict(raw), index=index, project_dir=project_dir, log=log))
    if not books:
        books = [Book(config=BookConfig(), extras=BookExtras())]

    latex = LaTeXConfig(
        build_dir=build_dir,
        project_dir=project_dir,
        language=language,
        books=[book.config for book in books],
        clean_assets=bool(options.get("clean_assets", True)),
    )
    return BookSettings(
        latex=latex,
        books=books,
        template=str(options.get("template") or "book"),
        copy_assets=bool(options.get("copy_assets", True)),
        embed_documents=bool(options.get("embed_documents", False)),
        bibliography=coerce_paths(options.get("bibliography") or [], relative_to=project_dir),
        template_overrides=dict(options.get("template_overrides") or {}),
        snippet_base_paths=list(snippet_base_paths),
    )


def _read_book(data: dict[str, Any], *, index: int, project_dir: Path, log: logging.Logger) -> Book:
    """One entry of ``books:`` as a :class:`Book` with no entries yet."""
    slot_requests = normalise_slot_requests(data.pop("slots", None), log=log)
    paper_override = data.pop("paper", None)
    press_overrides = normalise_press_overrides(data.pop("press", None), paper_override, log=log)
    extras = BookExtras(
        template=data.pop("template", None),
        template_overrides=dict(data.pop("template_overrides", {}) or {}),
        bibliography=coerce_paths(data.pop("bibliography", []), relative_to=project_dir),
        slots=slot_requests,
        press=press_overrides,
    )
    try:
        config = BookConfig(**data)
    except ValueError as exc:
        raise BookError(f"Invalid book configuration #{index}: {exc}") from exc
    return Book(config=config, extras=extras)


def normalise_label(value: str | None) -> str:
    """A case-insensitive label suitable for slot matching."""
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def normalise_slot_requests(
    payload: Any, *, log: logging.Logger | None = None
) -> dict[str, set[str]]:
    """The ``slots:`` selectors of a book, normalised and keyed by slot name."""
    logger = log or _log
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        logger.warning(
            "Ignoring invalid 'slots' mapping: expected a mapping, got %r", type(payload)
        )
        return {}

    slots: dict[str, set[str]] = {}
    for slot_name, selectors in payload.items():
        name = str(slot_name).strip()
        if not name:
            continue
        titles: set[str] = set()
        if isinstance(selectors, str):
            titles.add(normalise_label(selectors))
        elif isinstance(selectors, Iterable) and not isinstance(selectors, bytes | Mapping | str):
            for selector in selectors:
                if isinstance(selector, str) and selector.strip():
                    titles.add(normalise_label(selector))
        elif selectors is not None:
            logger.warning(
                "Slot '%s' selectors must be strings or lists of strings; ignoring %r.",
                name,
                type(selectors),
            )
        if titles:
            slots[name] = titles
    return slots


def normalise_press_overrides(
    payload: Any, paper: Any | None = None, *, log: logging.Logger | None = None
) -> dict[str, Any]:
    """The ``press:`` overrides of a book, with the ``paper`` alias merged in."""
    logger = log or _log
    press: dict[str, Any] = {}
    if isinstance(payload, Mapping):
        press.update(payload)
    elif payload is not None:
        logger.warning(
            "Ignoring invalid 'press' override: expected a mapping, got %r", type(payload)
        )
    if paper is not None:
        press["paper"] = paper
    return press


def match_slot(title: str | None, slots: Mapping[str, set[str]]) -> str | None:
    """The slot a navigation title is routed to, if any."""
    if not slots:
        return None
    key = normalise_label(title)
    for slot, candidates in slots.items():
        if key and key in candidates:
            return slot
    return None


def item_title(item: NavItem) -> str:
    """The title a navigation item shows, whatever kind it is."""
    if isinstance(item, NavPage):
        return page_title(item)
    return item.title or ""


def item_children(item: NavItem) -> tuple[NavItem, ...]:
    """A section's items, its index page first; nothing for a page or a link."""
    if isinstance(item, NavSection):
        return (item.index, *item.children) if item.index is not None else item.children
    return ()


def flatten_navigation(
    root: NavItem,
    config: BookConfig,
    slots: Mapping[str, set[str]] | None = None,
) -> list[NavEntry]:
    """Walk one navigation item into the flat chapter list of a book."""
    entries: list[NavEntry] = []
    slots_map = slots or {}

    def walk(
        node: NavItem,
        level: int,
        numbered: bool,
        part: str,
        front_flag: bool,
        back_flag: bool,
        active_slot: str | None,
    ) -> None:
        title = item_title(node)
        is_page = isinstance(node, NavPage)
        is_front = front_flag or (title in config.frontmatter)
        is_back = back_flag or (title in config.backmatter)
        segment = "frontmatter" if is_front else "backmatter" if is_back else part
        resolved_slot = active_slot or match_slot(title, slots_map)

        drop_title = False
        node_numbered = numbered
        if is_page and config.index_is_foreword:
            assert isinstance(node, NavPage)
            if PurePosixPath(node.src_uri).stem == "index":
                node_numbered = False
                if config.drop_title_index:
                    drop_title = True

        entries.append(
            NavEntry(
                title=title,
                level=level,
                numbered=node_numbered,
                drop_title=drop_title,
                part=segment,
                is_page=is_page,
                slot=resolved_slot,
                src_uri=node.src_uri if isinstance(node, NavPage) else None,
                abs_src_path=node.abs_path if isinstance(node, NavPage) else None,
            )
        )

        for child in item_children(node):
            walk(child, level + 1, node_numbered, segment, is_front, is_back, resolved_slot)

    walk(root, config.base_level, True, "mainmatter", False, False, None)
    return entries


def find_item_by_title(items: Iterable[NavItem], title: str) -> NavItem | None:
    """The first navigation item with that title, searched depth-first."""
    for item in items:
        if item_title(item) == title:
            return item
        match = find_item_by_title(item_children(item), title)
        if match is not None:
            return match
    return None


def nav_heading(title: str, *, level: int, numbered: bool, lang: str | None) -> str:
    """The LaTeX heading of a nav section — a nav entry that is not a page.

    A section of the nav has no source, so there is nothing to parse: build the
    one-header document the writer expects and let ``tmark.write`` choose the
    sectioning command for ``level``, exactly as it does for a page's own
    headers.
    """
    import tmark
    from tmark.ir import codec, model

    from texsmith.core.conversion.bodies import build_writer_options

    document = model.Document(blocks=(model.Header(level=1, content=(model.Str(text=title),)),))
    payload = codec.encode_document(document)
    payload["tmark"] = tmark.version()
    options = build_writer_options(
        backend="latex", language=lang, base_level=level, numbered=numbered
    )
    return str(tmark.write(payload, "latex", options).get("text") or "")


class BookBuilder:
    """Render the books of a site from the Markdown its pages are written in."""

    def __init__(
        self,
        settings: BookSettings,
        *,
        index: SiteIndex,
        metadata: SiteMetadata | None = None,
        emitter: SinkEmitter | None = None,
        logger: logging.Logger | None = None,
        compile_pdf: bool = False,
        publish_snippets_to: Path | None = None,
        on_written: Callable[[BookResult], None] | None = None,
    ) -> None:
        self.settings = settings
        self.index = index
        self.metadata = metadata or SiteMetadata()
        self.logger = logger or _log
        self.emitter = emitter or LoggingEmitter(logger_obj=self.logger)
        self.compile_pdf = compile_pdf
        #: Where the book's snippet previews are copied once it is rendered,
        #: for a generator that publishes what the build wrote (MkDocs).
        self.publish_snippets_to = publish_snippets_to
        #: Called once the bundle is written and before the engine runs, which
        #: is where ``--strict`` stops a run with the ``.tex`` there to read.
        self.on_written = on_written

    # Planning.

    def prepare(self, navigation: Navigation) -> list[Book]:
        """Fill every book's chapter list from the site's navigation."""
        for book in self.settings.books:
            self._prepare(book, navigation)
        return self.settings.books

    def _prepare(self, book: Book, navigation: Navigation) -> None:
        config = book.config
        if config.root is None:
            first = next(iter(navigation.pages()), None)
            if first is None:
                raise BookError(
                    "Unable to infer the root section for a book; "
                    "specify 'root' in the plugin configuration."
                )
            config.root = page_title(first)

        config.title = config.title or self.metadata.name
        config.author = config.author or self.metadata.author
        config.subtitle = config.subtitle or self.metadata.description
        if config.year is None:
            config.year = self.metadata.year
        config.email = config.email or self.metadata.email

        if config.root == FULL_NAVIGATION_ROOT:
            entries: list[NavEntry] = []
            for item in navigation.items:
                entries.extend(flatten_navigation(item, config, book.extras.slots))
        else:
            root_item = find_item_by_title(navigation.items, config.root)
            if root_item is None:
                raise BookError(f"Root section '{config.root}' not found in navigation.")
            entries = flatten_navigation(root_item, config, book.extras.slots)
        book.entries = entries

    # Rendering.

    def render(self, book: Book) -> BookResult:
        """Write one book's ``.tex`` and, when asked, compile its PDF."""
        settings = self.settings
        output_root = self._output_root(book.config)
        output_root.mkdir(parents=True, exist_ok=True)
        emitter = self.emitter

        template_name = book.extras.template or settings.template
        try:
            template_runtime = load_template_runtime(template_name)
        except TemplateError as exc:
            raise BookError(f"Failed to load template '{template_name}': {exc}") from exc

        self._resolve_base_level(book, template_runtime)

        copy_assets = settings.copy_assets
        bibliography_files = [*settings.bibliography, *book.extras.bibliography]
        # The shared ``.bib`` files; each page's context clones it and adds
        # the page's inline entries, and the clone becomes the next page's
        # base, so the collection written at the end holds every entry.
        bibliography_collection: BibliographyCollection | None = None
        if bibliography_files:
            bibliography_collection = BibliographyCollection()
            bibliography_collection.load_files(bibliography_files)
        bibliography_map: dict[str, dict[str, Any]] = (
            bibliography_collection.to_dict() if bibliography_collection is not None else {}
        )
        seen_bibliography_issues: set[tuple[str, str | None, str | None]] = set()

        document_state: DocumentState | None = None
        assets_map: dict[str, Path] = {}

        raw_language = book.config.language or settings.latex.language
        language = normalise_template_language(raw_language)
        runtime_language = language or raw_language

        overrides = self._template_overrides(book, language)
        embed_documents = settings.embed_documents

        slot_buffers_embed: dict[str, list[str]] = {name: [] for name in template_runtime.slots}
        slot_buffers_embed.setdefault(template_runtime.default_slot, [])
        slot_buffers_link: dict[str, list[str]] = {name: [] for name in template_runtime.slots}
        slot_buffers_link.setdefault(template_runtime.default_slot, [])
        default_base_level = book.config.base_level
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
                    self.logger.warning(
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
            copy_assets=copy_assets,
            language=runtime_language,
            default_include_paths=list(settings.snippet_base_paths),
            emitter=emitter,
        )
        chain = ResolutionChain(
            bibliography=bibliography_paths(bibliography_files),
            start=self._book_start(book),
            lang=runtime_language,
        )
        template_base = template_runtime.base_level or 0
        template_slot_levels = {
            name: slot.resolve_level(template_base) for name, slot in template_runtime.slots.items()
        }

        for page_index, entry in enumerate(book.entries):
            target_slot = select_slot(entry)
            slot_base = slot_base_levels.get(target_slot, default_base_level)
            target_buffer_embed = slot_buffers_embed[target_slot]
            target_buffer_link = slot_buffers_link[target_slot]
            effective_level = entry.level
            if slot_base is not None:
                effective_level = slot_base + (entry.level - default_base_level)

            if not entry.is_page:
                if entry.title and effective_level >= slot_base:
                    fragment = nav_heading(
                        entry.title,
                        level=effective_level,
                        numbered=entry.numbered,
                        lang=runtime_language,
                    )
                    target_buffer_embed.append(fragment)
                    target_buffer_link.append(fragment)
                continue

            if not entry.src_uri:
                self.logger.warning("Skipping page '%s': it has no source.", entry.title)
                continue
            if entry.abs_src_path is None:
                self.logger.warning(
                    "Cannot determine source path for page '%s'; skipping.", entry.title
                )
                continue

            document = self._page_document(
                entry,
                abs_src=entry.abs_src_path,
                base_level=effective_level - template_slot_levels.get(target_slot, template_base),
                output_root=output_root,
                emitter=emitter,
            )

            chain.book = self._book_labels(book, entry)
            try:
                result = convert_document(
                    document,
                    output_dir=output_root,
                    request=request,
                    slot_overrides=None,
                    template_overrides=overrides,
                    state=document_state,
                    template_runtime=template_runtime,
                    emitter=emitter,
                    preloaded_bibliography=bibliography_collection,
                    seen_bibliography_issues=seen_bibliography_issues,
                    resolution=chain,
                )
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.exception("TeXSmith failed while rendering page '%s'.", entry.title)
                detail = (
                    format_rendering_error(exc)
                    if isinstance(exc, LatexRenderingError)
                    else str(exc)
                )
                raise BookError(
                    f"LaTeX rendering failed for page '{entry.title}': {detail}"
                ) from exc

            document_state = result.document_state or document_state
            if result.context is not None and result.context.bibliography_collection:
                bibliography_collection = result.context.bibliography_collection
                bibliography_map = dict(result.context.bibliography_map)

            fragment = result.latex_output
            page_rel_path = _page_fragment_path(entry, page_index)
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

        final_state = document_state or DocumentState(bibliography=dict(bibliography_map))

        slot_outputs_embed = {
            name: "\n\n".join(parts) for name, parts in slot_buffers_embed.items()
        }
        slot_outputs_link = {name: "\n\n".join(parts) for name, parts in slot_buffers_link.items()}

        bibliography_output: Path | None = None
        if bibliography_collection is not None and final_state.citations and bibliography_map:
            bibliography_output = output_root / "texsmith-bibliography.bib"
            bibliography_output.parent.mkdir(parents=True, exist_ok=True)
            bibliography_collection.write_bibtex(bibliography_output, keys=final_state.citations)
            overrides.setdefault("bibliography", bibliography_output.stem)
            overrides.setdefault("bibliography_resource", bibliography_output.name)

        fragment_names = (
            overrides.get("fragments") or template_runtime.extras.get("fragments") or []
        )

        folder = book.config.folder
        stem = folder.name if isinstance(folder, Path) else folder if folder else "index"

        try:
            wrap_result = wrap_template_document(
                template=template_runtime.instance,
                default_slot=template_runtime.default_slot,
                slot_outputs=slot_outputs_embed,
                slot_output_overrides=None if embed_documents else slot_outputs_link,
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
            raise BookError(f"Failed to wrap LaTeX document: {exc}") from exc

        template_context = wrap_result.template_context or {}
        tex_path = wrap_result.output_path or (output_root / f"{stem}.tex")
        self.logger.info("TeXSmith wrote '%s'.", relativise(settings.build_dir, tex_path))
        self._announce_latexmk_command(output_root, tex_path)

        template_assets: list[Path] = list(wrap_result.asset_paths or [])
        template_assets.extend(
            Path(destination) for _, destination in getattr(wrap_result, "asset_pairs", [])
        )

        if assets_map:
            self._write_assets_manifest(output_root, assets_map)

        if settings.latex.clean_assets and copy_assets:
            referenced_assets = [*assets_map.values(), *template_assets]
            _prune_unused_assets(output_root, referenced_assets)

        self._copy_extra_files(book.config, output_root)
        self._publish_snippet_assets(output_root)
        written = BookResult(
            title=book.config.title or stem,
            output_root=output_root,
            tex_path=tex_path,
        )
        if self.on_written is not None:
            self.on_written(written)
        if not self.compile_pdf:
            return written
        return replace(
            written,
            pdf_path=self._run_pdf_build(
                output_root=output_root,
                tex_path=tex_path,
                template_context=template_context,
                document_state=final_state,
                bibliography_present=bool(bibliography_output),
            ),
        )

    # The book's shape.

    def _output_root(self, config: BookConfig) -> Path:
        base_dir = Path(config.build_dir or self.settings.build_dir)
        folder = config.folder
        candidate = base_dir if not folder else base_dir / folder
        return candidate.resolve()

    def _resolve_base_level(self, book: Book, template_runtime: Any) -> None:
        """Replace an ``auto`` base level by the one the template asks for."""
        original = book.config.base_level
        if original != AUTO_BASE_LEVEL:
            return
        template_base_level = template_runtime.base_level
        default_slot_name = template_runtime.default_slot
        default_slot: TemplateSlot | None = (
            template_runtime.slots.get(default_slot_name)
            if default_slot_name in template_runtime.slots
            else None
        )
        if template_base_level is not None:
            resolved = template_base_level
        elif default_slot is not None:
            resolved = default_slot.resolve_level(template_base_level or 0)
        else:
            resolved = 1

        if resolved != original:
            shift = resolved - original
            book.config.base_level = resolved
            for entry in book.entries:
                entry.level += shift

    def _template_overrides(self, book: Book, language: str | None) -> dict[str, Any]:
        """The template attributes of a book: the site's, then its own, then its cover."""
        overrides = dict(self.settings.template_overrides)
        overrides.update(book.extras.template_overrides)
        press_section = overrides.get("press")
        base_press = dict(press_section) if isinstance(press_section, Mapping) else {}
        if book.extras.press:
            base_press.update(book.extras.press)
        if base_press:
            overrides["press"] = base_press

        config = book.config
        for key, value in (
            ("title", config.title),
            ("subtitle", config.subtitle),
            ("author", config.author),
            ("email", config.email),
            ("year", config.year),
        ):
            if value is not None:
                overrides.setdefault(key, value)
        if language:
            overrides.setdefault("language", language)
        overrides.setdefault("cover", config.cover.name)
        overrides.setdefault("covercolor", config.cover.color)
        if config.cover.logo:
            overrides.setdefault("logo", config.cover.logo)
        return overrides

    # The pages.

    def _book_start(self, book: Book) -> dict[str, int]:
        """Where the site's chain stood before the book's first page."""
        for entry in book.entries:
            if entry.is_page and entry.src_uri:
                record = self.index.record(entry.src_uri)
                if record is not None:
                    return dict(record.start)
        return {}

    def _book_labels(self, book: Book, entry: NavEntry) -> list[dict[str, Any]]:
        """The labels of the book's other pages, for the ``resolve`` of ``entry``.

        The LaTeX writer prints a sibling as text (design 06 §Sibling
        documents), so only labels whose text is the same on both media are
        handed over: user counters (tmark numbers them in print too) and
        headings (their title). A backend-numbered float of another page
        stays ``[?key]`` rather than carrying the site's number into the PDF.
        """
        labels: list[dict[str, Any]] = []
        for other in book.entries:
            if not other.is_page or not other.src_uri or other.src_uri == entry.src_uri:
                continue
            record = self.index.record(other.src_uri)
            if record is None:
                continue
            for label in record.labels:
                prefix = label.get("prefix")
                kind = label.get("kind")
                heading = kind == "header"
                user_counter = bool(prefix) and (
                    prefix in self.index.counters or prefix in record.page_counters
                )
                if not (heading or user_counter):
                    continue
                item = dict(label)
                if heading and prefix not in HEADING_PREFIXES:
                    item["kind"] = "counter_item"
                labels.append(item)
        return labels

    def _page_document(
        self,
        entry: NavEntry,
        *,
        abs_src: Path,
        base_level: int,
        output_root: Path,
        emitter: SinkEmitter,
    ) -> Document:
        """The :class:`Document` of a page for the book: its source through tmark.

        The source is the Markdown the page is written in, with the page
        metadata and the site declarations back in front of it, written under
        ``sources/`` of the book so the exact input of the PDF is inspectable.
        """
        assert entry.src_uri is not None
        record = self.index.record(entry.src_uri)
        meta: Mapping[str, Any] = record.meta if record is not None else {}
        title_strategy = TitleStrategy.DROP if entry.drop_title else TitleStrategy.KEEP
        numbered = entry.numbered
        declared_numbered = meta.get("numbered")
        if isinstance(declared_numbered, bool):
            numbered = declared_numbered

        source_path = (
            self._persist_source(output_root, entry.src_uri, record)
            if record is not None
            else abs_src
        )
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

    def _persist_source(self, output_root: Path, src_uri: str, record: PageRecord) -> Path:
        """Write the page's source as the PDF reads it: merged metadata, stored body."""
        meta = dict(record.meta)
        page_counters = meta.pop("counters", None)
        merged_counters: dict[str, Any] = dict(self.index.counters)
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
            header = "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n"
        target = output_root / "sources" / Path(src_uri)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(header + record.body, encoding="utf-8")
        return target

    # The bundle beside the ``.tex``.

    def _write_assets_manifest(self, output_root: Path, assets_map: dict[str, Path]) -> None:
        manifest = {
            key: relativise(output_root, path).as_posix() for key, path in assets_map.items()
        }
        manifest_path = output_root / "assets_map.yml"
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=True), encoding="utf-8")

    def _copy_extra_files(self, config: BookConfig, output_root: Path) -> None:
        project_dir = self.settings.project_dir

        for pattern, destination in config.copy_files.items():
            src_pattern = (project_dir / pattern).resolve()
            dest_candidate = output_root / destination

            matched = list(src_pattern.parent.glob(src_pattern.name))
            if not matched:
                self.logger.warning("Copy pattern '%s' resolved no files.", pattern)
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
                self.logger.info("Copied '%s' to '%s'.", src, target)

    def _publish_snippet_assets(self, output_root: Path) -> None:
        """Copy the book's snippet previews where the generator publishes them."""
        root = self.publish_snippets_to
        source_dir = output_root / snippet.SNIPPET_DIR
        if root is None or not source_dir.exists():
            return
        target_dir = snippet_dir(root)
        for suffix in ("*.pdf", "*.png"):
            for asset in source_dir.glob(suffix):
                shutil.copy2(asset, target_dir / asset.name)

    def _announce_latexmk_command(self, output_root: Path, tex_path: Path) -> None:
        """Log a helpful hint showing how to compile the generated project."""
        bundle_path = relativise(self.settings.project_dir, output_root)
        try:
            tex_rel = tex_path.relative_to(output_root)
        except ValueError:
            tex_rel = tex_path

        self.logger.info(
            "Press bundle ready in '%s'. Run 'latexmk -cd %s/%s' to build the documentation.",
            bundle_path.as_posix(),
            bundle_path.as_posix(),
            tex_rel.as_posix(),
        )

    # The engine.

    def _run_pdf_build(
        self,
        *,
        output_root: Path,
        tex_path: Path,
        template_context: Mapping[str, Any],
        document_state: DocumentState,
        bibliography_present: bool,
    ) -> Path:
        env_engine = os.environ.get("TEXSMITH_ENGINE")
        engine_preference = env_engine.strip() if env_engine else "tectonic"
        use_system_tectonic = env_flag_enabled(os.environ.get("TEXSMITH_SYSTEM_TECTONIC"))

        template_engine = None
        raw_engine = template_context.get("latex_engine")
        if isinstance(raw_engine, str) and raw_engine.strip():
            template_engine = raw_engine.strip()

        engine_choice = resolve_engine(engine_preference, template_engine)

        features = compute_features(
            requires_shell_escape=bool(template_context.get("requires_shell_escape", False)),
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
                selection = select_tectonic_binary(use_system_tectonic, console=None)
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
                raise BookError(str(exc)) from exc

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
            raise BookError(
                f"LaTeX build skipped for '{tex_path.name}': missing dependencies ({readable})."
            )

        if engine_choice.backend == "latexmk":
            self._ensure_latexmkrc(
                tex_path=tex_path, engine=engine_choice.latexmk_engine, features=features
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
        console = Console(file=sys.stdout, force_terminal=False, color_system=None, no_color=True)

        engine_label = (
            engine_choice.latexmk_engine if engine_choice.backend == "latexmk" else "tectonic"
        )
        bundle_label = relativise(self.settings.project_dir or output_root, tex_path.parent)
        self.logger.info(
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
            log_path = relativise(tex_path.parent, result.log_path)
            raise BookError(f"LaTeX build failed for '{tex_path.name}' (see {log_path}).")

        pdf_path = result.pdf_path
        if not pdf_path.is_absolute():
            pdf_path = (tex_path.parent / pdf_path).resolve()
        pdf_label = relativise(self.settings.project_dir or tex_path.parent, pdf_path)
        self.logger.info("LaTeX build complete: %s", pdf_label)
        return pdf_path

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
            self.logger.warning("Unable to prepare latexmkrc for '%s': %s", tex_path.name, exc)
            return None

        try:
            rc_path.write_text(content, encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem
            self.logger.warning("Failed to write latexmkrc for '%s': %s", tex_path.name, exc)
            return None

        return rc_path

    def _log_engine_messages(self, messages: Iterable[LatexMessage]) -> None:
        for message in messages:
            summary = message.summary.strip()
            details = "; ".join(part.strip() for part in message.details if part.strip())
            payload = f"{summary}: {details}" if details else summary

            if message.severity is LatexMessageSeverity.ERROR:
                self.logger.error("LaTeX: %s", payload)
            elif message.severity is LatexMessageSeverity.WARNING:
                self.logger.warning("LaTeX: %s", payload)
            else:
                self.logger.info("LaTeX: %s", payload)


def _page_fragment_path(entry: NavEntry, index: int) -> Path:
    """Where one page's rendered body is written under the book's ``pages/``."""
    base = entry.src_uri or entry.title or f"page-{index}"
    normalised = slugify(base.replace("/", "-"), separator="-")
    if not normalised:
        normalised = f"page-{index}"
    return Path("pages") / f"{normalised}.tex"


def _prune_unused_assets(output_root: Path, referenced: Iterable[Path]) -> None:
    """Delete every file under ``assets/`` the rendered book does not name."""
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


def build_books(
    config: SiteConfig,
    *,
    emitter: SinkEmitter | None = None,
    logger: logging.Logger | None = None,
    build_dir: Path | None = None,
    title: str | None = None,
    compile_pdf: bool = True,
    on_written: Callable[[BookResult], None] | None = None,
) -> list[BookResult]:
    """Build every book a site configuration declares.

    The navigation is resolved from the configuration file, every page is
    pre-passed in navigation order — so the book's counters and cross-page
    references carry the numbers the site gives them — and each book is
    written under ``build_dir``.

    Args:
        config: The site's configuration, as :func:`load_site_config` read it.
        emitter: Where the diagnostics of the render go.
        logger: Where the progress lines go.
        build_dir: Overrides the ``build_dir`` option.
        title: Build only the book with that title.
        compile_pdf: Run the LaTeX engine once the ``.tex`` is written.
        on_written: Called with each book once its bundle is written and
            before its engine runs.

    Returns:
        One result per book built, in configuration order.
    """
    log = logger or _log
    options = config.plugin
    if not options.get("enabled", True):
        raise BookError(f"The 'texsmith' options are disabled in {config.config_path}.")

    language = options.get("language") or config.language
    settings = load_book_settings(
        options,
        project_dir=config.project_dir,
        build_dir=build_dir.resolve()
        if build_dir
        else book_build_root(options, config.project_dir),
        language=language,
        snippet_base_paths=config.snippet_base_paths,
        logger=log,
    )

    navigation = resolve_navigation(
        config.docs_dir, config.nav or None, exclude_docs=config.exclude_docs
    )
    index = SiteIndex(
        counters=site_counters(options, logger=log),
        lang=language,
        web_options=web_options(options, logger=log),
        project_dir=config.project_dir,
        logger=log,
        emitter=emitter,
    )
    index.prepass(
        SitePage(src_uri=page.src_uri, abs_src_path=page.abs_path)
        for page in (*navigation.pages(), *navigation.unlisted())
    )

    builder = BookBuilder(
        settings,
        index=index,
        metadata=SiteMetadata.read(config.data),
        emitter=emitter,
        logger=log,
        compile_pdf=compile_pdf,
        on_written=on_written,
    )
    books = builder.prepare(navigation)
    if title is not None:
        wanted = normalise_label(title)
        books = [book for book in books if normalise_label(book.config.title) == wanted]
        if not books:
            raise BookError(f"No book titled '{title}' in {config.config_path}.")
    return [builder.render(book) for book in books]
