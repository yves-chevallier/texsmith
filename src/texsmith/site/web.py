"""TeXSmith's web lowering as a Python-Markdown extension, for Zensical.

Zensical has no plugin hooks: it renders every page through Python-Markdown
and offers nothing else on the Python side. So what the MkDocs plugin does
in ``on_nav``, ``on_page_markdown`` and ``on_post_page`` is done here by a
preprocessor and a postprocessor around the same :mod:`texsmith.site` code —
the site pre-pass, the per-page lowering onto ``tmark.lower_web`` and the
snippet previews.

What the extension may *not* do is produce a file the build then publishes.
Zensical clears the site directory before a build and caches rendered pages,
so a warm build replays a page's HTML without calling Python: anything
written while a page renders is deleted, and the render that wrote it never
happens again. The generated files are therefore sources, written under
``docs_dir`` by ``texsmith site assets`` before the build — the stylesheet
among them, which the extension only checks for. A preview is the one
exception the extension still writes, and it writes it under ``docs_dir``
too: ``zensical serve`` watches that directory, so a snippet added or edited
between two builds appears in the rebuild the new file triggers.

Listing ``texsmith.site.web`` under ``markdown_extensions`` is harmless
under MkDocs: the extension acts only when Zensical's rendering context is
on the ``Markdown`` instance, and under MkDocs the plugin does the work
through its hooks.

Two things have to be true for the extension to act, and the second is the
subtle one. mkdocstrings forwards the configured extensions — Zensical's
context extension included — to the ``Markdown`` instance it builds for each
docstring, so a preprocessor that only checked for the context would run
once per docstring (449 times for 96 pages on this site). Zensical registers
its ``LinksExtension`` on the page's own instance and deliberately not on
the inner ones, so its ``zrelpath`` postprocessor is the mark of the outer
instance.

Zensical's own view of the configuration is not enough to drive this: it
drops the plugins it does not know, ``texsmith`` among them, and resolves
``nav`` in Rust. The ``texsmith:`` options and the navigation are therefore
read from the configuration file, and everything Zensical does understand —
where the sources are, the URL style, the language — is taken from the live
configuration, which is what its Rust side uses.

What does not carry over: the PDF books and ``mike`` versioning. The search
index is not written here either — Zensical writes it in Rust once Python is
done — but it is not lost: ``texsmith site search`` patches the index the
build wrote, after the build.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
import sys
import threading
from typing import Any

from markdown import Extension, Markdown
from markdown.postprocessors import Postprocessor
from markdown.preprocessors import Preprocessor

from texsmith.adapters.plugins import snippet
from texsmith.diagnostics import LoggingEmitter
from texsmith.site import assets
from texsmith.site.config import (
    config_file_in,
    language_from_mapping,
    load_site_config,
    site_counters,
    web_options,
)
from texsmith.site.index import SiteIndex, SitePage
from texsmith.site.nav import resolve_navigation


__all__ = ["TexsmithExtension", "makeExtension"]

_log = logging.getLogger("texsmith.site")

#: The postprocessor Zensical registers on a page's own ``Markdown``
#: instance, and on no inner one: the mark of the outer instance.
OUTER_MARKER = "zrelpath"

#: After ``macros`` (35) and before ``pymdownx.snippets`` (32), the place
#: MkDocs gives the plugin's ``on_page_markdown``.
LOWER_PRIORITY = 34

#: Last, once the stashed raw HTML of the snippet fences is back in the page.
SNIPPET_PRIORITY = 0

#: Just before the snippets; any postprocessor sees the ``src`` of an image
#: already rewritten relative to the page's URL, since Zensical rewrites the
#: links in a tree processor, which Python-Markdown runs first.
DRAWIO_PRIORITY = 1

#: Matches one ``<img>`` tag and the ``src`` it carries.
RE_IMG = re.compile(r"<img\b[^>]*?\bsrc=\"([^\"]+)\"[^>]*>", re.IGNORECASE)
#: An image wrapped in a link, the shape glightbox gives a figure: the anchor
#: names the same file the image does.
RE_LINKED_IMG = re.compile(
    r"<a\b[^>]*?\bhref=\"([^\"]+)\"[^>]*>\s*<img\b[^>]*?\bsrc=\"([^\"]+)\"[^>]*>\s*</a>",
    re.IGNORECASE,
)


@dataclass(slots=True)
class SiteState:
    """The site as the pre-pass left it, shared by every page of a build."""

    index: SiteIndex
    docs_dir: Path
    use_directory_urls: bool
    #: The live configuration this state was built from; Zensical parses a
    #: new one when the configuration file changes.
    config: Any
    #: ``page -> (mtime, size)`` when the pre-pass ran, so an edit invalidates it.
    mtimes: dict[str, tuple[int, int]]


_lock = threading.Lock()
_state: SiteState | None = None


def makeExtension(**kwargs: Any) -> TexsmithExtension:  # noqa: N802 - Python-Markdown's name
    """Build the extension; Python-Markdown calls this by name."""
    return TexsmithExtension(**kwargs)


class TexsmithExtension(Extension):
    """Lower a page's TMark constructs into the HTML the theme renders."""

    name = "texsmith.site.web"

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802 - Python-Markdown's name
        """Register the lowering and the snippet rewriting."""
        md.preprocessors.register(LowerPreprocessor(md), "texsmith_lower", LOWER_PRIORITY)
        md.postprocessors.register(DrawioPostprocessor(md), "texsmith_drawio", DRAWIO_PRIORITY)
        md.postprocessors.register(SnippetPostprocessor(md), "texsmith_snippets", SNIPPET_PRIORITY)


class LowerPreprocessor(Preprocessor):
    """Resolve the page against the site map and splice its constructs."""

    def run(self, lines: list[str]) -> list[str]:
        """Return the lowered Markdown of the page being rendered."""
        page = _page(self.md)
        if page is None:
            return lines
        state = site_state()
        if state is None:
            return lines
        # A page the site's own navigation excludes — ``exclude_docs``, which
        # Zensical ignores — was not pre-passed. It is lowered like any other,
        # so it reads, but its diagnostics are not the site's: MkDocs never
        # builds that page at all, and an include source that happens to sit
        # under ``docs_dir`` would otherwise report its every deprecation
        # against a page nobody meant to publish.
        excluded = state.index.record(page.path) is None
        lowered = state.index.lower(
            SitePage(
                src_uri=page.path,
                abs_src_path=state.docs_dir / page.path,
                meta=dict(page.meta or {}),
            ),
            "\n".join(lines),
        )
        if lowered is None:
            return lines
        if not excluded:
            state.index.report(lowered)
        return lowered.text.split("\n")


class DrawioPostprocessor(Postprocessor):
    """Point every ``.drawio`` image at the SVG the pre-step exported for it.

    MkDocs shows a draw.io diagram through the ``drawio`` plugin's viewer,
    which Zensical does not run: the page would keep an ``<img>`` pointing at
    an XML file no browser draws. ``texsmith site assets`` exports each
    diagram to an SVG under ``docs_dir``, and this rewrites the tag to it —
    only when the export is there, so a diagram nobody exported keeps its tag
    rather than pointing at a file the build would not publish.

    An image glightbox wrapped in a link to the very same file has its
    ``href`` rewritten with it: the lightbox otherwise offers the ``.drawio``
    XML for download. That shape — an anchor naming the diagram its own image
    shows — is the only ``href`` touched, so a link an author wrote to the
    source file is left as it is.
    """

    def run(self, text: str) -> str:
        """Return the page's HTML with every draw.io image pointing at its SVG."""
        if ".drawio" not in text and ".dio" not in text:
            return text
        page = _page(self.md)
        if page is None:
            return text
        state = site_state()
        if state is None:
            return text
        dest_uri = assets.page_dest_uri(page.url, use_directory_urls=state.use_directory_urls)
        prefix = assets.asset_prefix(dest_uri)
        missing: list[str] = []

        def export(src: str) -> tuple[str, str] | None:
            """``(diagram, published URL of its SVG)``, or ``None`` when there is none."""
            source_uri = assets.drawio_source_uri(src, page_uri=dest_uri)
            if source_uri is None:
                return None
            export_uri = assets.drawio_export_uri(source_uri)
            if not (state.docs_dir / export_uri).is_file():
                missing.append(source_uri)
                return None
            return source_uri, f"{prefix}{export_uri}"

        def rewrite_linked(match: re.Match[str]) -> str:
            href, src = match.group(1), match.group(2)
            linked, image = export(href), export(src)
            if linked is None or image is None or linked[0] != image[0]:
                return match.group(0)
            return (
                match.group(0)
                .replace(f'href="{href}"', f'href="{linked[1]}"', 1)
                .replace(f'src="{src}"', f'src="{image[1]}"', 1)
            )

        def rewrite(match: re.Match[str]) -> str:
            src = match.group(1)
            image = export(src)
            if image is None:
                return match.group(0)
            return match.group(0).replace(f'src="{src}"', f'src="{image[1]}"', 1)

        rewritten = RE_IMG.sub(rewrite, RE_LINKED_IMG.sub(rewrite_linked, text))
        if missing:
            _log.warning(
                "texsmith: page '%s' shows %s, which no SVG was exported for — "
                "run 'texsmith site assets' before the build.",
                page.path,
                ", ".join(sorted(set(missing))),
            )
        return rewritten


class SnippetPostprocessor(Postprocessor):
    """Replace the rendered ``snippet`` fences by their preview image."""

    def run(self, text: str) -> str:
        """Return the page's HTML with every snippet fence rewritten."""
        if "snippet" not in text:
            return text
        page = _page(self.md)
        if page is None:
            return text
        state = site_state()
        if state is None:
            return text
        source_path = state.docs_dir / page.path
        dest_uri = assets.page_dest_uri(page.url, use_directory_urls=state.use_directory_urls)

        def resolve(block: snippet.SnippetBlock) -> tuple[str, str]:
            # Under ``docs_dir``, never under the site directory: Zensical
            # clears that one at the start of every build, and replays a
            # cached page without calling Python, so a preview written there
            # is gone by the time the page that links it is served. A preview
            # written here is published by the next build, which the file
            # appearing under ``docs_dir`` triggers by itself under
            # ``zensical serve``.
            return assets.snippet_urls(
                block,
                root=state.docs_dir,
                dest_uri=dest_uri,
                source_path=source_path,
                emitter=state.index.emitter,
            )

        try:
            return snippet.rewrite_html_snippets(text, resolve, source_path=source_path)
        except Exception as exc:
            # A preview that cannot be built leaves the fence as it is: the
            # page still reads, and the build goes on.
            _log.warning("texsmith: could not render a snippet on page '%s': %s", page.path, exc)
            return text


def _page(md: Markdown) -> Any | None:
    """Zensical's page, or ``None`` when this instance must be left alone.

    ``None`` under MkDocs, which has no rendering context, and ``None`` for
    the inner instances mkdocstrings builds for each docstring, which carry
    the context but not Zensical's own link rewriting.
    """
    if OUTER_MARKER not in md.postprocessors:
        return None
    from zensical.extensions.context import ContextPreprocessor

    context = ContextPreprocessor.from_markdown(md)
    return None if context is None else context.page


def site_state() -> SiteState | None:
    """The site's pre-pass, built once and rebuilt when a page changes.

    ``zensical serve`` renders pages in the process that built this state, so
    it is dropped as soon as a page is added, removed or edited: the numbers
    and the labels of the whole site depend on every page's content. ``None``
    when the ``texsmith`` plugin is disabled.
    """
    global _state
    with _lock:
        current = _state
        if current is not None:
            from zensical.config import get_config

            if get_config() is current.config and current.mtimes == _page_mtimes(current.docs_dir):
                return current
        _state = _build_state()
        return _state


def _build_state() -> SiteState | None:
    """Pre-pass every page of the site and write the stylesheet."""
    from zensical.config import get_config

    config = get_config()
    project_dir = Path(config.get("root_dir") or ".").resolve()
    docs_dir = _directory(project_dir, config.get("docs_dir") or "docs")

    plugin: dict[str, Any] = {}
    nav: list[Any] | None = None
    config_file = config_file_in(project_dir)
    if config_file is None:
        _log.warning(
            "texsmith: no configuration file under '%s'; the 'texsmith' options "
            "are unknown and the defaults apply.",
            project_dir,
        )
    else:
        site_config = load_site_config(config_file)
        plugin = site_config.plugin
        nav = site_config.nav

    if not plugin.get("enabled", True):
        return None
    _show_diagnostics()

    state = SiteState(
        index=SiteIndex(
            counters=site_counters(plugin, logger=_log),
            lang=plugin.get("language") or language_from_mapping(config.get("theme")),
            web_options=web_options(plugin, logger=_log),
            project_dir=project_dir,
            logger=_log,
            emitter=LoggingEmitter(logger_obj=_log),
        ),
        docs_dir=docs_dir,
        use_directory_urls=bool(config.get("use_directory_urls", True)),
        config=config,
        mtimes=_page_mtimes(docs_dir),
    )

    navigation = resolve_navigation(docs_dir, nav or None, exclude_docs=config.get("exclude_docs"))
    pages = [*navigation.pages(), *navigation.unlisted()]
    state.index.prepass(
        SitePage(src_uri=page.src_uri, abs_src_path=page.abs_path) for page in pages
    )

    if plugin.get("css", True):
        if not (docs_dir / assets.CSS_URI).is_file():
            _log.warning(
                "texsmith: '%s' is missing under '%s' — run 'texsmith site assets' "
                "before the build; a file the rendering writes into the site "
                "directory does not survive it.",
                assets.CSS_URI,
                docs_dir,
            )
        if assets.CSS_URI not in (config.get("extra_css") or []):
            _log.warning(
                "texsmith: add '%s' to 'extra_css' — Zensical reads that list "
                "before Python runs, so the extension cannot add it itself.",
                assets.CSS_URI,
            )
    return state


def _page_mtimes(docs_dir: Path) -> dict[str, tuple[int, int]]:
    """Every Markdown source under ``docs_dir``, with when it last changed and its size.

    The size is there because the modification time alone is only as precise
    as the file system's clock: two writes inside one tick — a test, a script,
    a fast editor save — carry the same stamp, and a pre-pass that trusted it
    would keep numbering the site from the page it no longer holds.
    """
    mtimes: dict[str, tuple[int, int]] = {}
    for path in docs_dir.rglob("*.md"):
        try:
            stat = path.stat()
        except OSError:  # pragma: no cover - the file went away mid-scan
            continue
        mtimes[path.relative_to(docs_dir).as_posix()] = (stat.st_mtime_ns, stat.st_size)
    return mtimes


def _directory(project_dir: Path, value: str) -> Path:
    """One of Zensical's directory settings, as an absolute path."""
    path = Path(value)
    return path.resolve() if path.is_absolute() else (project_dir / path).resolve()


def _show_diagnostics() -> None:
    """Make the ``texsmith`` logger print, since Zensical configures nothing.

    Python's last-resort handler would show the warnings but drop everything
    below them, and a snippet preview announces itself at ``INFO`` — the same
    line MkDocs prints.
    """
    logger = logging.getLogger("texsmith")
    if logger.handlers or logging.getLogger().handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
