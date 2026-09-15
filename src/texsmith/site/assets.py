"""What a rendered page needs beside it: the stylesheet, the previews, the diagrams.

Both generators serve the same three things: one stylesheet for the whole
site, linked from every page through ``extra_css``; one PDF/PNG pair per
``.snippet`` fence under ``assets/snippets/``, linked from the page that holds
the fence, so the URL depends on how deep that page sits in the site; and one
SVG per ``.drawio`` image under ``assets/drawio/``, which is what a browser
can show of a diagram TeXSmith otherwise exports to PDF for the document.

Where those files are *produced* is the difference between the generators.
MkDocs takes the stylesheet as a generated file and renders a preview into
``site_dir`` while it writes the page. Zensical cannot be driven that way: it
clears the site directory at the start of every build, and it caches rendered
pages, so a warm build replays a page's HTML without calling Python at all —
a file written while a page renders is gone, and never written again. Under
Zensical the generated files are therefore *sources*: :func:`generate`, the
work of ``texsmith site assets``, writes them under ``docs_dir`` before the
build, and the build copies them like any other static file.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PurePosixPath
import posixpath
import shutil
from urllib.parse import urlparse

from tmark.ir import model
from tmark.ir.walk import walk

from texsmith.adapters.plugins import snippet
from texsmith.adapters.transformers import drawio_export
from texsmith.core.user_dir import get_user_dir
from texsmith.diagnostics import DiagnosticEmitter, FileTable
from texsmith.passes.assets import DRAWIO_SUFFIXES
from texsmith.passes.include import resolve_include
from texsmith.passes.snippet import is_snippet, snippet_block
from texsmith.readers.loader import TexsmithLoader
from texsmith.readers.tmark import read
from texsmith.site.config import SiteConfig
from texsmith.site.nav import resolve_navigation


__all__ = [
    "CSS_URI",
    "DRAWIO_DIR",
    "AssetFailure",
    "Drawing",
    "GeneratedAssets",
    "Preview",
    "asset_prefix",
    "drawio_dir",
    "drawio_export_name",
    "drawio_export_uri",
    "drawio_source_uri",
    "generate",
    "page_dest_uri",
    "page_url",
    "snippet_dir",
    "snippet_urls",
    "stylesheet",
    "write_stylesheet",
]

#: Where the stylesheet lands in the site, and what ``extra_css`` must name.
CSS_URI = "assets/texsmith/texsmith.css"

#: Where an exported ``.drawio`` diagram lands under ``docs_dir``, under the
#: relative path of the diagram itself, so two diagrams of the same name in
#: two directories keep their own export.
DRAWIO_DIR = "assets/drawio"

#: The digest cache the draw.io exports share between runs and projects.
DRAWIO_CACHE = "site-drawio"


def stylesheet() -> str:
    """The ``texsmith.css`` shipped with the package."""
    return resources.files(__package__).joinpath("static/texsmith.css").read_text(encoding="utf-8")


def write_stylesheet(root: Path) -> Path:
    """Write the stylesheet at :data:`CSS_URI` under ``root``.

    ``root`` is the documentation directory: the stylesheet is a source of
    the site, which the generator copies where every page's ``extra_css``
    link expects it. MkDocs takes it as a generated file instead, and leaves
    the copy alone when ``texsmith site assets`` has already put one there.
    """
    target = Path(root) / CSS_URI
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stylesheet(), encoding="utf-8")
    return target


def page_dest_uri(url: str, *, use_directory_urls: bool) -> str:
    """The file a page is written to, from the URL the generator gave it.

    With directory URLs a page is served from its own directory
    (``guide/mkdocs/``) and written to the ``index.html`` in it; without
    them the URL already names the file (``guide/mkdocs.html``).
    """
    if not use_directory_urls:
        return url
    return posixpath.join(url, "index.html")


def page_url(dest_uri: str, *, use_directory_urls: bool) -> str:
    """The URL of a page, from the file the generator wrote it to.

    The inverse of :func:`page_dest_uri`, for the one caller that has only
    the built site to read: ``texsmith site search`` walks the HTML files and
    has to name each one the way the search index does.
    """
    if not use_directory_urls or posixpath.basename(dest_uri) != "index.html":
        return dest_uri
    parent = posixpath.dirname(dest_uri)
    return f"{parent}/" if parent else ""


def asset_prefix(dest_uri: str) -> str:
    """``../`` once per directory between a page's own file and the site root."""
    parent = PurePosixPath(dest_uri).parent
    if str(parent) in {"", "."}:
        return ""
    return "../" * len([part for part in parent.parts if part and part != "."])


def drawio_source_uri(src: str, *, page_uri: str) -> str | None:
    """The ``.drawio`` file an image names, relative to ``docs_dir``.

    ``src`` is written the way a Markdown image writes it: relative to the
    page, or absolute from the site root. ``None`` when the image is not a
    draw.io diagram, when it is remote, or when it reaches out of the
    documentation directory, where nothing can be exported for it.
    """
    clean = src.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean or urlparse(clean).scheme:
        return None
    if PurePosixPath(clean).suffix.lower() not in DRAWIO_SUFFIXES:
        return None
    if clean.startswith("/"):
        target = clean.lstrip("/")
    else:
        target = posixpath.normpath(posixpath.join(posixpath.dirname(page_uri), clean))
    if target.startswith("../") or target == "..":
        return None
    return target


def drawio_export_name(source_uri: str) -> str:
    """Where the SVG of one ``.drawio`` source lands, relative to :data:`DRAWIO_DIR`."""
    return PurePosixPath(source_uri).with_suffix(".svg").as_posix()


def drawio_export_uri(source_uri: str) -> str:
    """Where the SVG of one ``.drawio`` source lands, relative to ``docs_dir``."""
    return f"{DRAWIO_DIR}/{drawio_export_name(source_uri)}"


def drawio_dir(root: Path) -> Path:
    """The directory of the draw.io exports under ``root``, created when missing."""
    target = Path(root) / DRAWIO_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def snippet_dir(root: Path) -> Path:
    """The directory of the snippet previews under ``root``, created when missing."""
    target = Path(root) / "assets" / snippet.SNIPPET_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def snippet_urls(
    block: snippet.SnippetBlock,
    *,
    root: Path,
    dest_uri: str,
    source_path: Path | str | None = None,
    emitter: DiagnosticEmitter | None = None,
) -> tuple[str, str]:
    """Render one snippet under ``root`` and return its PDF and PNG URLs.

    ``root`` is the site directory for MkDocs, which writes the preview where
    it writes the page, and the documentation directory for Zensical, which
    would throw away anything written into the site directory.

    The URLs are relative to the page at ``dest_uri``, the way the page's own
    Markdown images are, so they survive whatever prefix the site is served
    under.
    """
    snippet.ensure_snippet_assets(
        block,
        output_dir=snippet_dir(root),
        source_path=source_path,
        emitter=emitter,
    )
    prefix = f"{asset_prefix(dest_uri)}assets/{snippet.SNIPPET_DIR}/"
    return (
        prefix + snippet.asset_filename(block.digest, ".pdf"),
        prefix + snippet.asset_filename(block.digest, ".png"),
    )


@dataclass(frozen=True, slots=True)
class Preview:
    """One ``.snippet`` fence of a page and the preview it asks for."""

    #: The page's path relative to ``docs_dir``.
    page: str
    #: ``snippet-<digest>``, the stem of the PDF/PNG pair.
    basename: str
    #: ``False`` when both files were already there, so nothing was rendered.
    built: bool


@dataclass(frozen=True, slots=True)
class Drawing:
    """One ``.drawio`` image of a page and the SVG exported for the web."""

    #: The page's path relative to ``docs_dir``.
    page: str
    #: The diagram's path relative to ``docs_dir``.
    source: str
    #: The export's path relative to ``docs_dir`` (``assets/drawio/…svg``).
    uri: str
    #: ``False`` when the export was already there, byte for byte.
    built: bool


@dataclass(frozen=True, slots=True)
class AssetFailure:
    """An asset that could not be produced; the page keeps what it had."""

    page: str
    message: str


@dataclass(frozen=True, slots=True)
class GeneratedAssets:
    """What :func:`generate` left under ``docs_dir``."""

    stylesheet: Path
    previews: tuple[Preview, ...]
    drawings: tuple[Drawing, ...]
    #: The files removed because no page names them any more, previews by
    #: name and exports by their path relative to ``docs_dir``.
    pruned: tuple[str, ...]
    failures: tuple[AssetFailure, ...]


def generate(
    config: SiteConfig,
    *,
    emitter: DiagnosticEmitter | None = None,
    on_preview: Callable[[Preview], None] | None = None,
) -> GeneratedAssets:
    """Write the stylesheet, every ``.snippet`` preview and every diagram.

    Every page the navigation reaches, then every page it does not, is parsed
    once and walked twice: each ``.snippet`` fence's preview is rendered into
    ``docs_dir/assets/snippets/`` unless the digest is already there, and each
    ``.drawio`` image is exported to an SVG under ``docs_dir/assets/drawio/``.
    What no page asks for any more is deleted from either directory: both hold
    nothing but generated files, so anything the pages do not name is a
    leftover.

    An asset that cannot be read or built is an :class:`AssetFailure` naming
    its page, and the walk goes on: one broken snippet or diagram does not
    cost the site its other assets.
    """
    docs_dir = config.docs_dir
    navigation = resolve_navigation(docs_dir, config.nav or None, exclude_docs=config.exclude_docs)
    output_dir = snippet_dir(docs_dir)
    exports_dir = drawio_dir(docs_dir)
    loader = TexsmithLoader(FileTable())

    previews: list[Preview] = []
    drawings: list[Drawing] = []
    failures: list[AssetFailure] = []
    wanted: set[str] = set()
    exported: set[str] = set()
    for page in (*navigation.pages(), *navigation.unlisted()):
        document = _parse(page.abs_path, page=page.src_uri, failures=failures)
        if document is None:
            continue
        for fence in _fences(document):
            block = _block(
                fence,
                page=page.src_uri,
                host_path=page.abs_path,
                search=config.snippet_base_paths,
                loader=loader,
                failures=failures,
            )
            if block is None:
                continue
            # Named before it is rendered: a preview that is already there
            # survives a build that fails, and the page keeps linking to it.
            wanted.add(block.asset_basename)
            preview = _render(
                block,
                page=page.src_uri,
                host_path=page.abs_path,
                output_dir=output_dir,
                emitter=emitter,
                failures=failures,
            )
            if preview is None:
                continue
            previews.append(preview)
            if on_preview is not None:
                on_preview(preview)

        for source_uri in _diagrams(document, page_uri=page.src_uri):
            exported.add(drawio_export_name(source_uri))
            drawing = _export(
                source_uri,
                page=page.src_uri,
                docs_dir=docs_dir,
                emitter=emitter,
                failures=failures,
            )
            if drawing is not None:
                drawings.append(drawing)

    return GeneratedAssets(
        stylesheet=write_stylesheet(docs_dir),
        previews=tuple(previews),
        drawings=tuple(drawings),
        pruned=(
            *_prune(output_dir, wanted, name=lambda path: path.stem),
            *(
                f"{DRAWIO_DIR}/{name}"
                for name in _prune(
                    exports_dir,
                    exported,
                    name=lambda path: path.relative_to(exports_dir).as_posix(),
                )
            ),
        ),
        failures=tuple(failures),
    )


def _parse(path: Path, *, page: str, failures: list[AssetFailure]) -> model.Document | None:
    """The IR of one page, or ``None`` with a failure recorded when it cannot be read.

    The assets are read from the IR ``tmark.parse`` builds, the same nodes the
    ``snippet`` and ``assets`` passes rewrite, rather than from the page's
    rendered HTML: no Markdown pipeline has to be assembled to find a fence or
    an image, and the attributes come parsed.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        failures.append(AssetFailure(page, f"could not be read: {exc}"))
        return None
    document, _diagnostics = read(text, name=str(path))
    return document


def _fences(document: model.Document) -> Iterator[model.CodeBlock]:
    """Every ``.snippet`` fence of a page, in document order."""
    for node in walk(document):
        if is_snippet(node):
            yield node


def _diagrams(document: model.Document, *, page_uri: str) -> Iterator[str]:
    """Every ``.drawio`` file the page's images name, relative to ``docs_dir``.

    Each diagram is yielded once per page, however many images point at it.
    """
    seen: set[str] = set()
    for node in walk(document):
        if not isinstance(node, model.Image):
            continue
        source_uri = drawio_source_uri(node.src, page_uri=page_uri)
        if source_uri is None or source_uri in seen:
            continue
        seen.add(source_uri)
        yield source_uri


def _block(
    fence: model.CodeBlock,
    *,
    page: str,
    host_path: Path,
    search: Sequence[Path],
    loader: TexsmithLoader,
    failures: list[AssetFailure],
) -> snippet.SnippetBlock | None:
    """Read one fence into the block that names its preview, or say why it cannot be."""
    try:
        text = _fence_text(fence, host_path=host_path, search=search, loader=loader)
        block = snippet_block(fence, host_path=host_path, text=text)
    except Exception as exc:  # a fence that will not parse is reported, not raised
        failures.append(AssetFailure(page, str(exc)))
        return None
    if block is None:
        failures.append(AssetFailure(page, "the fence has neither inline content nor sources"))
    return block


def _render(
    block: snippet.SnippetBlock,
    *,
    page: str,
    host_path: Path,
    output_dir: Path,
    emitter: DiagnosticEmitter | None,
    failures: list[AssetFailure],
) -> Preview | None:
    """Render one block's preview into ``output_dir``, or record why it could not be."""
    built = not all(
        (output_dir / snippet.asset_filename(block.digest, suffix)).exists()
        for suffix in (".pdf", ".png")
    )
    try:
        snippet.ensure_snippet_assets(
            block, output_dir=output_dir, source_path=host_path, emitter=emitter
        )
    except Exception as exc:  # a snippet that will not build is reported, not raised
        failures.append(AssetFailure(page, str(exc)))
        return None
    return Preview(page=page, basename=block.asset_basename, built=built)


def _fence_text(
    fence: model.CodeBlock,
    *,
    host_path: Path,
    search: Sequence[Path],
    loader: TexsmithLoader,
) -> str | None:
    """The body of a fence, with its ``include=`` read when it has one.

    ``pymdownx.snippets`` splices that file into the fence before the site's
    Markdown pipeline ever sees it, so the preview the page will ask for is
    the one of the spliced text; the ``include`` pass does the same thing
    ahead of the ``snippet`` pass. ``None`` leaves the fence body alone.
    """
    include = next((value for key, value in fence.options.kv if key == "include"), None)
    if include is None:
        return None
    found = resolve_include(include, from_path=str(host_path), loader=loader, search=search)
    if found is None:
        raise FileNotFoundError(f"included file '{include}' not found")
    return found[1]


def _export(
    source_uri: str,
    *,
    page: str,
    docs_dir: Path,
    emitter: DiagnosticEmitter | None,
    failures: list[AssetFailure],
) -> Drawing | None:
    """Export one diagram to SVG under ``docs_dir``, or record why it could not be.

    The converter keeps its own digest cache, so a diagram that has not
    changed is not exported again; what lands under ``docs_dir`` is a copy of
    that cached export, written only when it differs from the one already
    there, so an untouched diagram leaves the site's sources untouched too.
    """
    source_path = docs_dir / source_uri
    target = docs_dir / drawio_export_uri(source_uri)
    if not source_path.is_file():
        failures.append(AssetFailure(page, f"'{source_uri}': the diagram does not exist"))
        return None
    try:
        produced = drawio_export(
            source_path,
            output_dir=get_user_dir().cache_dir(DRAWIO_CACHE),
            format="svg",
            emitter=emitter,
        )
    except Exception as exc:  # a diagram that will not export is reported, not raised
        failures.append(AssetFailure(page, f"'{source_uri}': {exc}"))
        return None
    svg = Path(produced).read_bytes()
    built = not target.is_file() or target.read_bytes() != svg
    if built:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(produced, target)
    return Drawing(page=page, source=source_uri, uri=drawio_export_uri(source_uri), built=built)


def _prune(root: Path, wanted: set[str], *, name: Callable[[Path], str]) -> tuple[str, ...]:
    """Delete every file under ``root``, at any depth, that no page asks for.

    ``name`` is how a file on disk is spelled in ``wanted`` — a preview by its
    stem, since one fence owns a PDF and a PNG; an export by its path under
    the export directory, since two diagrams of the same name live in two
    directories. Emptied directories go with their files.
    """
    removed: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or name(path) in wanted:
            continue
        path.unlink()
        removed.append(path.relative_to(root).as_posix())
    for directory in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    return tuple(removed)
