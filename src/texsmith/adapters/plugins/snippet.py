"""Plugin rendering fenced snippet blocks into standalone PDF assets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from PIL import Image, ImageDraw, ImageFilter

from texsmith.adapters.handlers._helpers import (
    coerce_attribute,
    gather_classes,
    mark_processed,
)
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown
from texsmith.api.document import Document, DocumentRenderOptions, DocumentSlots, TitleStrategy
from texsmith.api.pipeline import RenderSettings
from texsmith.api.templates import TemplateSession
from texsmith.core.context import RenderContext
from texsmith.core.conversion.inputs import InputKind
from texsmith.core.diagnostics import DiagnosticEmitter
from texsmith.core.exceptions import AssetMissingError, InvalidNodeError, LatexRenderingError
from texsmith.core.rules import RenderPhase, renders
from texsmith.core.templates import TemplateError, TemplateRuntime, load_template_runtime


SNIPPET_DIR = "snippets"
_SNIPPET_PREFIX = "snippet-"
_TRUE_VALUES = {"1", "true", "on", "yes"}
_FALSE_VALUES = {"0", "false", "off", "no"}
_SNIPPET_CACHE_NAMESPACE = "snippets"
_SNIPPET_CACHE_FILENAME = "metadata.json"
_SNIPPET_CACHE_VERSION = 2
_log = logging.getLogger(__name__)


@dataclass(slots=True)
class SnippetBlock:
    """Parsed representation of a snippet fence."""

    content: str
    frame_enabled: bool
    layout: tuple[int, int] | None
    template_id: str | None
    cwd: Path | None
    caption: str | None
    label: str | None
    figure_width: str | None
    template_overrides: dict[str, Any]
    digest: str
    border_enabled: bool
    dogear_enabled: bool
    transparent_corner: bool
    bibliography_raw: list[str]
    bibliography_files: list[Path]
    title_strategy: TitleStrategy
    suppress_title_metadata: bool

    @property
    def asset_basename(self) -> str:
        return f"{_SNIPPET_PREFIX}{self.digest}"


@dataclass(slots=True)
class _SnippetAssets:
    pdf: Path
    png: Path


_SNIPPET_RUNTIME: TemplateRuntime | None = None
_SNIPPET_CACHE: _SnippetCache | None = None


@dataclass(slots=True)
class _SnippetCache:
    """Disk-backed cache storing rendered snippet artefacts."""

    root: Path
    metadata_path: Path
    metadata: dict[str, Any]
    dirty: bool = False

    def lookup(self, digest: str, template_version: str | None) -> _SnippetAssets | None:
        """Return cached assets when they exist and match the signature."""
        entries = self._entries()
        payload = entries.get(digest)
        if not isinstance(payload, dict):
            self.discard(digest)
            return None

        signature = payload.get("signature")
        if signature and signature != digest:
            self.discard(digest)
            return None

        recorded_version = payload.get("template_version")
        if template_version and recorded_version and recorded_version != template_version:
            self.discard(digest)
            return None

        pdf_name = payload.get("pdf") or asset_filename(digest, ".pdf")
        png_name = payload.get("png") or asset_filename(digest, ".png")
        pdf_path = (self.root / pdf_name).resolve()
        png_path = (self.root / png_name).resolve()
        if not pdf_path.exists() or not png_path.exists():
            self.discard(digest)
            return None

        return _SnippetAssets(pdf=pdf_path, png=png_path)

    def store(
        self,
        digest: str,
        pdf_path: Path,
        png_path: Path,
        *,
        template_version: str | None,
        block: SnippetBlock | None = None,
        source_path: Path | None = None,
    ) -> None:
        """Persist compiled assets in the cache directory."""
        entries = self._entries()
        cached_pdf = (self.root / asset_filename(digest, ".pdf")).resolve()
        cached_png = (self.root / asset_filename(digest, ".png")).resolve()
        cached_pdf.parent.mkdir(parents=True, exist_ok=True)
        cached_md = (self.root / asset_filename(digest, ".md")).resolve()

        cached_md_path: Path | None = None
        if block is not None:
            try:
                cached_md.write_text(block.content, encoding="utf-8")
                cached_md_path = cached_md
            except OSError:
                cached_md_path = None

        attributes: dict[str, Any] | None = None
        if block is not None:
            attributes = {
                "caption": block.caption,
                "label": block.label,
            "figure_width": block.figure_width,
            "border": block.border_enabled,
            "dogear_enabled": block.dogear_enabled,
            "transparent_corner": block.transparent_corner,
            "frame_enabled": block.frame_enabled,
            "layout": block.layout,
            "overrides": block.template_overrides,
            "cwd": str(block.cwd) if block.cwd else None,
        }

        linked_files: dict[str, str] = {
            "pdf": cached_pdf.name,
            "png": cached_png.name,
        }
        if cached_md_path is not None:
            linked_files["md"] = cached_md_path.name

        source_hint = str(source_path) if source_path is not None else None

        try:
            source_pdf = Path(pdf_path).resolve()
            source_png = Path(png_path).resolve()
            if source_pdf != cached_pdf:
                shutil.copy2(source_pdf, cached_pdf)
            if source_png != cached_png:
                shutil.copy2(source_png, cached_png)
        except OSError:
            return

        entries[digest] = {
            "signature": digest,
            "pdf": cached_pdf.name,
            "png": cached_png.name,
            "template_version": template_version,
            "files": linked_files,
            "attributes": attributes,
            "source": source_hint,
        }
        self.dirty = True

    def discard(self, digest: str) -> None:
        """Remove a cache entry when it becomes invalid."""
        entries = self._entries()
        if digest in entries:
            entries.pop(digest, None)
            self.dirty = True

    def flush(self) -> None:
        """Persist metadata to disk when modified."""
        if not self.dirty:
            return

        payload = {
            "version": _SNIPPET_CACHE_VERSION,
            "entries": self._entries(),
        }
        tmp_path = self.metadata_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp_path.replace(self.metadata_path)
            self.dirty = False
        except OSError:
            return

    def _entries(self) -> dict[str, Any]:
        entries = self.metadata.setdefault("entries", {})
        if not isinstance(entries, dict):
            entries = {}
            self.metadata["entries"] = entries
        return entries


def _resolve_runtime() -> TemplateRuntime:
    global _SNIPPET_RUNTIME
    if _SNIPPET_RUNTIME is None:
        _SNIPPET_RUNTIME = load_template_runtime("snippet")
    return _SNIPPET_RUNTIME


def _resolve_cache_root() -> Path | None:
    base = os.environ.get("TEXSMITH_CACHE_DIR")
    if base:
        candidate = Path(base).expanduser() / _SNIPPET_CACHE_NAMESPACE
    else:
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            candidate = Path(xdg_cache).expanduser() / "texsmith" / _SNIPPET_CACHE_NAMESPACE
        else:
            try:
                candidate = Path.home() / ".cache" / "texsmith" / _SNIPPET_CACHE_NAMESPACE
            except RuntimeError:
                return None

    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return candidate


def _load_cache_metadata(path: Path) -> dict[str, Any]:
    default = {"version": _SNIPPET_CACHE_VERSION, "entries": {}}
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    except OSError:
        return default

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return default

    if payload.get("version") != _SNIPPET_CACHE_VERSION:
        return default

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        payload["entries"] = {}
    return payload


def _resolve_cache() -> _SnippetCache | None:
    global _SNIPPET_CACHE
    if _SNIPPET_CACHE is not None:
        return _SNIPPET_CACHE

    root = _resolve_cache_root()
    if root is None:
        return None

    metadata_path = root / _SNIPPET_CACHE_FILENAME
    metadata = _load_cache_metadata(metadata_path)
    _SNIPPET_CACHE = _SnippetCache(root=root, metadata_path=metadata_path, metadata=metadata)
    return _SNIPPET_CACHE


def _resolve_caches(source_path: Path | str | None) -> list[_SnippetCache]:
    """Return the user-level cache only."""
    cache = _resolve_cache()
    return [cache] if cache is not None else []


def _resolve_bibliography_files(
    files: list[str],
    cwd: str | Path | None,
    host_path: Path | None,
) -> list[Path]:
    """Resolve bibliography file paths relative to the snippet host document."""
    if not files:
        return []

    base_dir: Path | None = None
    cwd_path = Path(cwd).expanduser() if cwd else None
    if cwd_path is not None:
        if cwd_path.is_absolute():
            base_dir = cwd_path
        elif host_path is not None:
            try:
                base_dir = (host_path.parent / cwd_path).resolve()
            except OSError:
                base_dir = host_path.parent
        else:
            try:
                base_dir = cwd_path.resolve()
            except OSError:
                base_dir = None
    elif host_path is not None:
        base_dir = host_path.parent

    resolved: list[Path] = []
    for entry in files:
        candidate = Path(entry)
        if not candidate.is_absolute():
            if base_dir is None:
                try:
                    base_dir = Path.cwd()
                except OSError:
                    base_dir = None
            if base_dir is not None:
                candidate = base_dir / candidate
        try:
            candidate = candidate.resolve()
        except OSError:
            pass
        resolved.append(candidate)
    return resolved


def _resolve_host_path(document_path: Path | str | None, source_dir: Path | None) -> Path | None:
    """Normalise the host document path to an absolute path when possible."""
    if document_path is None:
        return None

    try:
        candidate = Path(document_path)
    except TypeError:
        return None

    if candidate.is_absolute():
        return candidate

    if source_dir is not None:
        try:
            return (Path(source_dir) / candidate).resolve()
        except OSError:
            return Path(source_dir) / candidate

    try:
        return candidate.resolve()
    except OSError:
        return candidate


def _resolve_base_dir(block: SnippetBlock, host_path: Path | None) -> Path:
    """Resolve the effective base directory for snippet assets."""
    if block.cwd:
        base = block.cwd
        if not base.is_absolute() and host_path is not None:
            try:
                return (host_path.parent / base).resolve()
            except OSError:
                return host_path.parent
        try:
            return base.resolve()
        except OSError:
            pass

    if host_path is not None:
        return host_path.parent

    try:
        return Path.cwd()
    except OSError:
        return Path(".")


def _resolve_template_runtime(block: SnippetBlock, document: Document, base_dir: Path) -> TemplateRuntime:
    """Select the template runtime from front matter when provided."""
    front_matter = document.front_matter
    template_id: str | None = block.template_id
    if isinstance(front_matter, Mapping):
        raw = front_matter.get("template")
        if raw:
            template_id = str(raw).strip()
        if not template_id:
            press = front_matter.get("press")
            if isinstance(press, Mapping):
                raw_press = press.get("template")
                if raw_press:
                    template_id = str(raw_press).strip()

    if not template_id:
        return _resolve_runtime()

    # Try resolving relative to the snippet cwd / host directory first.
    candidates: list[str] = []
    tpl_path = Path(template_id)
    if not tpl_path.is_absolute():
        candidates.append(str((base_dir / tpl_path).resolve()))
    candidates.append(template_id)

    last_exc: Exception | None = None
    for candidate in candidates:
        try:
            return load_template_runtime(candidate)
        except TemplateError as exc:
            last_exc = exc
            continue

    if last_exc is not None:
        raise last_exc

    return _resolve_runtime()


def _snippet_template_version() -> str | None:
    runtime = _resolve_runtime()
    info = getattr(runtime.instance, "info", None)
    if info is None:
        return None
    version = getattr(info, "version", None)
    return str(version) if version is not None else None


def _resolve_emitter(context: RenderContext) -> DiagnosticEmitter | None:
    emitter = context.runtime.get("emitter")
    if isinstance(emitter, DiagnosticEmitter):
        return emitter
    return None


def asset_filename(digest: str, suffix: str) -> str:
    """Return the deterministic filename for a snippet artefact."""
    return f"{_SNIPPET_PREFIX}{digest}{suffix}"


def _hash_payload(
    content: str,
    overrides: dict[str, str],
    cwd: str | None = None,
    frame: bool = True,
    template_id: str | None = None,
    layout: tuple[int, int] | None = None,
) -> str:
    payload = {
        "content": content,
        "overrides": overrides,
        "cwd": cwd,
        "frame": frame,
        "template": template_id,
        "layout": layout,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _coerce_bool_option(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_VALUES:
            return True
        if token in _FALSE_VALUES:
            return False
    return default


def _extract_template_overrides(
    element: Tag, classes: list[str]
) -> tuple[
    dict[str, Any],
    str | None,
    str | None,
    str | None,
    str | None,
    bool,
    str | None,
    list[str],
]:
    code_element = element.find("code")
    pre_element = element.find("pre")

    def _attr(name: str) -> Any:
        for candidate in (element, pre_element, code_element):
            if candidate is None:
                continue
            value = candidate.get(name)
            if value is not None:
                return value
        return None

    overrides: dict[str, Any] = {}
    caption = coerce_attribute(_attr("data-caption")) or None
    label = coerce_attribute(_attr("data-label")) or None
    figure_width = (
        coerce_attribute(_attr("data-width"))
        or coerce_attribute(_attr("data-figure-width"))
        or coerce_attribute(_attr("width"))
        or None
    )
    if figure_width is None:
        style_attr = coerce_attribute(_attr("style")) or ""
        if "width" in style_attr:
            for chunk in style_attr.split(";"):
                if "width" not in chunk:
                    continue
                key, _, value = chunk.partition(":")
                if key.strip().lower() == "width":
                    figure_width = value.strip()
                    break
    cwd = coerce_attribute(_attr("data-cwd")) or None
    template_id = coerce_attribute(_attr("data-template")) or None
    frame_enabled = _coerce_bool_option(_attr("data-frame"), True)
    layout_literal = coerce_attribute(_attr("data-layout")) or None
    files_literal = coerce_attribute(_attr("data-files")) or None

    candidate_attrs: list[tuple[str, Any]] = list(element.attrs.items())
    if pre_element is not None:
        candidate_attrs.extend(pre_element.attrs.items())
    if code_element is not None:
        candidate_attrs.extend(code_element.attrs.items())

    for attr, value in candidate_attrs:
        if not isinstance(attr, str):
            continue
        key = attr.lower()
        if key.startswith("data-snippet-"):
            normalised = key[len("data-snippet-") :].strip().replace("-", "_")
            if not normalised:
                continue
            overrides[normalised] = coerce_attribute(value) or ""
        elif key.startswith("data-attr-"):
            normalised = key[len("data-attr-") :].strip().replace("-", "_")
            if not normalised:
                continue
            value_norm = coerce_attribute(value) or ""
            press_section = overrides.setdefault("press", {})
            if isinstance(press_section, dict):
                press_section[normalised] = value_norm
            else:
                overrides["press"] = {normalised: value_norm}
            if normalised in {"callout_style", "callouts_style"}:
                overrides["callout_style"] = value_norm

    if "no-border" in classes and "border" not in overrides:
        overrides["border"] = False

    for key, default in (("border", True), ("dogear_enabled", True)):
        if key in overrides:
            overrides[key] = _coerce_bool_option(overrides[key], default)

    layout = _parse_layout(layout_literal)

    files: list[str] = []
    if isinstance(files_literal, str) and files_literal.strip():
        candidates = [chunk.strip() for chunk in files_literal.split(",")]
        files = [item for item in candidates if item]

    return overrides, caption, label, figure_width, cwd, frame_enabled, template_id, layout, files


def _extract_snippet_block(element: Tag, host_path: Path | None = None) -> SnippetBlock | None:
    classes = gather_classes(element.get("class"))
    if "snippet" not in classes:
        return None

    pre_element = element.find("pre")
    code_element = element.find("code")
    if code_element is None:
        raise InvalidNodeError("Snippet block is missing an inner <code> element.")
    content = code_element.get_text(strip=False)
    if not content.strip():
        return None

    def _attr(name: str) -> Any:
        for candidate in (element, pre_element, code_element):
            if candidate is None:
                continue
            value = candidate.get(name)
            if value is not None:
                return value
        return None

    (
        overrides,
        caption,
        label,
        figure_width,
        cwd,
        frame_enabled,
        template_id,
        layout,
        files,
    ) = _extract_template_overrides(element, classes)
    suppress_title_value = _coerce_bool_option(_attr("data-no-title"), True)
    drop_title_value = _coerce_bool_option(
        _attr("data-strip-title") or _attr("data-drop-title"),
        False,
    )
    title_strategy = TitleStrategy.DROP if drop_title_value else TitleStrategy.KEEP

    digest_overrides = dict(overrides)
    digest_overrides["_no_title"] = suppress_title_value
    digest_overrides["_drop_title"] = drop_title_value
    if files:
        digest_overrides["_files"] = [cwd or "", *files]

    digest = _hash_payload(
        content,
        digest_overrides,
        cwd=cwd,
        frame=frame_enabled,
        template_id=template_id,
        layout=layout,
    )
    border_enabled = _coerce_bool_option(overrides.get("border"), True)
    dogear_enabled = _coerce_bool_option(overrides.get("dogear_enabled"), True)

    resolved_files = _resolve_bibliography_files(files, cwd, host_path)

    return SnippetBlock(
        content=content,
        frame_enabled=frame_enabled,
        layout=layout,
        template_id=template_id,
        cwd=Path(cwd).expanduser() if cwd else None,
        caption=caption,
        label=label,
        figure_width=figure_width,
        template_overrides=overrides,
        digest=digest,
        border_enabled=border_enabled,
        dogear_enabled=dogear_enabled,
        transparent_corner=border_enabled and dogear_enabled,
        bibliography_raw=files,
        bibliography_files=resolved_files,
        title_strategy=title_strategy,
        suppress_title_metadata=suppress_title_value,
    )


def _build_document(
    block: SnippetBlock,
    *,
    host_dir: Path,
    host_name: str,
) -> Document:
    rendered = render_markdown(
        block.content,
        extensions=list(DEFAULT_MARKDOWN_EXTENSIONS),
        base_path=host_dir,
    )
    synthetic = host_dir / f"{host_name}-{block.asset_basename}.md"
    options = DocumentRenderOptions(
        base_level=0,
        title_strategy=block.title_strategy,
        numbered=False,
        suppress_title_metadata=block.suppress_title_metadata,
    )
    document = Document(
        source_path=synthetic,
        kind=InputKind.MARKDOWN,
        _html=rendered.html,
        _front_matter=rendered.front_matter,
        options=options,
        slots=DocumentSlots(),
    )
    document._initialise_slots_from_front_matter()  # noqa: SLF001
    return document


def _compile_pdf(render_result: Any) -> Path:
    latexmk = shutil.which("latexmk")
    if latexmk is None:
        raise AssetMissingError("latexmk executable not found; required for snippet rendering.")

    from texsmith.ui.cli.commands.render import build_latexmk_command

    command = build_latexmk_command(
        render_result.template_engine,
        render_result.requires_shell_escape,
        force_bibtex=render_result.has_bibliography,
    )
    command[0] = latexmk
    command.append(render_result.main_tex_path.name)

    process = subprocess.run(
        command,
        cwd=render_result.main_tex_path.parent,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        stderr = process.stderr.strip()
        stdout = process.stdout.strip()
        detail = stderr or stdout or "latexmk exited with a non-zero status."
        log_path = render_result.main_tex_path.with_suffix(".log")
        raise LatexRenderingError(
            f"Failed to compile snippet: {detail} (log: {log_path})"
        )

    return render_result.main_tex_path.with_suffix(".pdf")


def _load_pymupdf() -> object:
    try:
        import pymupdf as fitz  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        try:
            import fitz  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise AssetMissingError(
                "PyMuPDF is required to generate snippet previews. Install the 'pymupdf' package."
            ) from exc

    if not hasattr(fitz, "open"):  # type: ignore[attr-defined]
        raise AssetMissingError(
            "A conflicting 'fitz' package is installed. Remove it and install 'pymupdf' instead."
        )

    return fitz  # type: ignore[return-value]


def _pdf_to_png(pdf_path: Path, png_path: Path, *, transparent_corner: bool = False) -> None:
    fitz = _load_pymupdf()

    with fitz.open(pdf_path) as document:
        if document.page_count == 0:
            raise LatexRenderingError(f"Snippet PDF '{pdf_path}' did not produce any pages.")
        page = document.load_page(0)
        pixmap = page.get_pixmap(dpi=220)

    mode = "RGBA" if pixmap.alpha else "RGB"
    image = Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
    if transparent_corner:
        image = _apply_dogear_transparency(image)
    image.save(png_path)


def _pdf_to_png_grid(
    pdf_path: Path,
    png_path: Path,
    *,
    layout: tuple[int, int] | None = None,
    transparent_corner: bool = False,
    spacing: int | None = None,
    decorate_page: Callable[[Image.Image], Image.Image] | None = None,
) -> None:
    fitz = _load_pymupdf()

    with fitz.open(pdf_path) as document:
        page_count = document.page_count
        if page_count == 0:
            raise LatexRenderingError(f"Snippet PDF '{pdf_path}' did not produce any pages.")

        cols, rows = (1, 1)
        if layout:
            c, r = layout
            if c > 0:
                cols = c
            if r > 0:
                rows = r
        pages_needed = cols * rows
        if pages_needed <= 0:
            cols = 1
            rows = 1
            pages_needed = 1
        use_pages = min(page_count, pages_needed)

        images: list[Image.Image] = []
        for index in range(use_pages):
            page = document.load_page(index)
            pixmap = page.get_pixmap(dpi=220)
            mode = "RGBA" if pixmap.alpha else "RGB"
            images.append(Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples))

    if not images:
        raise LatexRenderingError(f"Snippet PDF '{pdf_path}' did not produce any pages.")

    page_w, page_h = images[0].size
    inferred_spacing = 0
    if spacing is None and cols * rows > 1:
        inferred_spacing = max(int(round(min(page_w, page_h) * 0.04)), 18)
    elif spacing:
        inferred_spacing = max(spacing, 0)

    total_w = cols * page_w + inferred_spacing * (cols - 1)
    total_h = rows * page_h + inferred_spacing * (rows - 1)
    canvas = Image.new("RGBA", (total_w, total_h), (255, 255, 255, 0))

    for idx, img in enumerate(images):
        if transparent_corner:
            img = _apply_dogear_transparency(img)
        if decorate_page is not None:
            img = decorate_page(img)

        r = idx // cols
        c = idx % cols
        x = c * (page_w + inferred_spacing)
        y = r * (page_h + inferred_spacing)
        mask = img if "A" in img.getbands() else None
        canvas.paste(img, (x, y), mask=mask)

    canvas.save(png_path)


def _apply_dogear_transparency(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    if width <= 0 or height <= 0:
        return rgba

    seed_x = max(width - 2, 0)
    seed_y = 1 if height > 1 else 0
    marker = (255, 0, 255, 255)
    try:
        ImageDraw.floodfill(rgba, (seed_x, seed_y), marker, thresh=4)
    except ValueError:
        return rgba

    pixels = rgba.load()
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == marker:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def _parse_layout(value: str | None) -> tuple[int, int] | None:
    """Parse layout string like '2x2', '3', or '1x3' into (cols, rows)."""
    if not value:
        return None
    raw = value.strip().lower()
    if not raw:
        return None
    if "x" in raw:
        parts = raw.split("x", 1)
        try:
            cols = int(parts[0])
            rows = int(parts[1])
        except ValueError:
            return None
        return (cols, rows)
    try:
        cols = int(raw)
    except ValueError:
        return None
    return (cols, 1)


def _overlay_dogear_frame(
    image: Image.Image,
    *,
    margin: int | None = None,
    dogear: int | None = None,
    border_width: int | None = None,
    border_color: tuple[int, int, int, int] = (0, 0, 0, 255),
    dogear_enabled: bool = True,
) -> Image.Image:
    """Draw a frame with a folded corner directly onto the PNG."""
    base = image.convert("RGBA")
    width, height = base.size
    if width <= 0 or height <= 0:
        return base

    size_hint = min(width, height)
    m = 0 if margin is None else max(margin, 0)
    fold = dogear if dogear is not None else max(int(size_hint * 0.07), 18)
    stroke = border_width if border_width is not None else max(int(size_hint * 0.0025), 1)

    x0, y0 = m, m
    x1, y1 = width - 1 - m, height - 1 - m

    scale = 6
    overlay = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bw = max(1, stroke * scale)

    def sx(val: float) -> int:
        return int(round(val * scale))

    def sy(val: float) -> int:
        return int(round(val * scale))

    draw.line([(sx(x0), sy(y0)), (sx(x1 - fold), sy(y0))], fill=border_color, width=bw)
    draw.line([(sx(x1), sy(y0 + fold)), (sx(x1), sy(y1))], fill=border_color, width=bw)
    draw.line([(sx(x1), sy(y1)), (sx(x0), sy(y1))], fill=border_color, width=bw)
    draw.line([(sx(x0), sy(y1)), (sx(x0), sy(y0))], fill=border_color, width=bw)

    mask = Image.new("L", overlay.size, color=255)
    mask_draw = ImageDraw.Draw(mask)

    if dogear_enabled:
        corner = (x1 - fold, y0 + fold)
        bdown = (x1, y0 + fold)
        bleft = (x1 - fold, y0)

        def bezier_points(p0, p1, p2, p3, steps: int = 192):
            pts = []
            for i in range(steps + 1):
                t = i / steps
                mt = 1 - t
                x = (
                    mt * mt * mt * p0[0]
                    + 3 * mt * mt * t * p1[0]
                    + 3 * mt * t * t * p2[0]
                    + t * t * t * p3[0]
                )
                y = (
                    mt * mt * mt * p0[1]
                    + 3 * mt * mt * t * p1[1]
                    + 3 * mt * t * t * p2[1]
                    + t * t * t * p3[1]
                )
                pts.append((sx(x), sy(y)))
            return pts

        spline1 = bezier_points(
            corner,
            (corner[0] + 0.3 * fold, corner[1] - 0.1 * fold),
            (bdown[0] - 0.3 * fold, bdown[1] + 0.1 * fold),
            bdown,
        )
        spline2 = bezier_points(
            bleft,
            (bleft[0] + 0.1 * fold, bleft[1] - 0.3 * fold),
            (corner[0] - 0.1 * fold, corner[1] + 0.3 * fold),
            corner,
        )

        draw.line(spline1, fill=border_color, width=bw, joint="curve")
        draw.line(spline2, fill=border_color, width=bw, joint="curve")

        mask_draw.polygon(
            [
                (sx(x1 - fold), sy(y0)),
                (sx(x1 + 1), sy(y0)),
                (sx(x1 + 1), sy(y0 + fold + 1)),
            ],
            fill=0,
        )

    composited = Image.alpha_composite(base, overlay.resize(base.size, Image.LANCZOS))
    if dogear_enabled:
        mask_small = mask.resize(base.size, Image.LANCZOS)
        composited.putalpha(mask_small)
    return composited


def ensure_snippet_assets(
    block: SnippetBlock,
    *,
    output_dir: Path,
    source_path: Path | str | None = None,
    emitter: DiagnosticEmitter | None = None,
    transparent_corner: bool | None = None,
) -> _SnippetAssets:
    """Render snippet assets into the provided directory when missing."""
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    pdf_path = destination / asset_filename(block.digest, ".pdf")
    png_path = destination / asset_filename(block.digest, ".png")

    host_path = Path(source_path) if source_path is not None else destination / "snippet.md"
    host_dir = _resolve_base_dir(block, host_path)
    host_name = host_path.stem or "snippet"

    document = _build_document(block, host_dir=host_dir, host_name=host_name)
    runtime = _resolve_template_runtime(block, document, host_dir)
    apply_corner_default = (
        block.transparent_corner if transparent_corner is None else transparent_corner
    )
    if block.frame_enabled:
        apply_corner = False
    elif runtime.name == "snippet":
        apply_corner = apply_corner_default if block.dogear_enabled and block.border_enabled else False
    else:
        apply_corner = False

    caches = _resolve_caches(source_path)
    template_version = None
    if caches:
        info = getattr(runtime.instance, "info", None)
        if info is not None:
            version = getattr(info, "version", None)
            template_version = str(version) if version is not None else None

    pdf_missing = not pdf_path.exists()
    png_missing = not png_path.exists() or block.frame_enabled
    assets = _SnippetAssets(pdf=pdf_path, png=png_path)

    def _flush_caches() -> None:
        for cache in caches:
            cache.flush()

    def _store_in_caches() -> None:
        if not caches:
            return
        for cache in caches:
            cache.store(
                block.digest,
                pdf_path,
                png_path,
                template_version=template_version,
                block=block,
                source_path=Path(source_path) if source_path is not None else None,
            )
        _flush_caches()

    if not pdf_missing and not png_missing:
        _store_in_caches()
        return assets

    if caches and (pdf_missing or png_missing):
        for cache in caches:
            cached_assets = cache.lookup(block.digest, template_version=template_version)
            if cached_assets is None:
                continue
            try:
                if pdf_missing:
                    shutil.copy2(cached_assets.pdf, pdf_path)
                    pdf_missing = False
                if png_missing:
                    shutil.copy2(cached_assets.png, png_path)
                    png_missing = False
            except OSError:
                cache.discard(block.digest)
                continue
            if not pdf_missing and not png_missing:
                _store_in_caches()
                return assets
        _flush_caches()

    if not pdf_missing and png_missing:
        _pdf_to_png(pdf_path, png_path, transparent_corner=apply_corner)
        png_missing = False
        _store_in_caches()
        return assets

    _announce_build(block, source_path, emitter)

    settings = RenderSettings(
        copy_assets=True,
        convert_assets=False,
        hash_assets=False,
        manifest=False,
    )
    session = TemplateSession(runtime=runtime, settings=settings, emitter=emitter)
    session.add_document(document)
    if block.bibliography_files:
        session.add_bibliography(*block.bibliography_files)
    if block.template_overrides:
        session.update_options(block.template_overrides)

    work_dir = destination / f".build-{block.digest}"
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    debug_dir: Path | None = None
    try:
        render_result = session.render(work_dir)
        compiled_pdf = _compile_pdf(render_result)
        shutil.copy2(compiled_pdf, pdf_path)
    except Exception as exc:
        # Preserve the work directory for post-mortem inspection when compilation fails.
        try:
            cache_root = _resolve_cache_root() or Path(tempfile.gettempdir()) / "texsmith"
            debug_dir = (cache_root / "snippet-fail" / block.digest).resolve()
            if debug_dir.exists():
                shutil.rmtree(debug_dir, ignore_errors=True)
            shutil.copytree(work_dir, debug_dir, dirs_exist_ok=True)
        except Exception:
            debug_dir = None
        if debug_dir is not None:
            raise exc.__class__(f"{exc} (debug: {debug_dir})") from exc
        raise
    else:
        shutil.rmtree(work_dir, ignore_errors=True)

    total_cells = 1
    if block.layout:
        cols, rows = block.layout
        total_cells = max(cols, 1) * max(rows, 1)
    per_page_frame: Callable[[Image.Image], Image.Image] | None = None
    if block.frame_enabled and block.border_enabled and total_cells > 1:
        def _frame_page(img: Image.Image) -> Image.Image:
            return _overlay_dogear_frame(img, dogear_enabled=block.dogear_enabled)

        per_page_frame = _frame_page

    _pdf_to_png_grid(
        pdf_path,
        png_path,
        layout=block.layout,
        transparent_corner=apply_corner,
        spacing=None if total_cells > 1 else 0,
        decorate_page=per_page_frame,
    )
    needs_global_frame = block.frame_enabled and block.border_enabled and per_page_frame is None
    if needs_global_frame:
        try:
            image = Image.open(png_path)
        except OSError:
            pass
        else:
            framed = _overlay_dogear_frame(
                image,
                dogear_enabled=block.dogear_enabled,
            )
            try:
                framed.save(png_path)
            except OSError:
                pass

    _store_in_caches()
    return assets


def _render_snippet_assets(block: SnippetBlock, context: RenderContext) -> _SnippetAssets:
    emitter = _resolve_emitter(context)
    document_path = context.runtime.get("document_path")
    source_dir = context.runtime.get("source_dir")
    host_path = _resolve_host_path(document_path, source_dir)
    if block.bibliography_raw:
        try:
            block.bibliography_files = _resolve_bibliography_files(
                block.bibliography_raw,
                block.cwd,
                host_path,
            )
        except Exception:
            _log.debug("failed to resolve bibliography paths for snippet", exc_info=True)
    return ensure_snippet_assets(
        block,
        output_dir=context.assets.output_root / SNIPPET_DIR,
        source_path=host_path or (context.assets.output_root / "snippet.md"),
        emitter=emitter,
        transparent_corner=block.transparent_corner,
    )


def _render_figure(
    context: RenderContext, assets: _SnippetAssets, block: SnippetBlock
) -> NavigableString:
    template_name = context.runtime.get("figure_template", "figure")
    formatter = getattr(context.formatter, template_name)
    latex_path = context.assets.latex_path(assets.pdf)
    latex = formatter(
        path=latex_path,
        caption=block.caption,
        shortcaption=block.caption,
        label=block.label,
        width=block.figure_width,
        adjustbox=True,
    )
    return mark_processed(NavigableString(latex))


@renders("div", phase=RenderPhase.PRE, priority=32, name="snippet_blocks", nestable=False)
def render_snippet_block(element: Tag, context: RenderContext) -> None:
    """Convert `.snippet` code fences into rendered figures."""
    document_path = context.runtime.get("document_path")
    source_dir = context.runtime.get("source_dir")
    host_path = _resolve_host_path(document_path, source_dir)
    block = _extract_snippet_block(element, host_path=host_path)
    if block is None:
        return

    assets = _render_snippet_assets(block, context)
    asset_key = f"snippet::{block.digest}"
    context.assets.register(asset_key, assets.pdf)

    node = _render_figure(context, assets, block)
    context.suppress_children(element)
    element.replace_with(node)


def rewrite_html_snippets(
    html: str,
    resolver: Callable[[SnippetBlock], tuple[str, str]],
) -> str:
    """Replace snippet fences in an HTML fragment with linked previews."""
    if "snippet" not in html:
        return html

    soup = BeautifulSoup(html, "html.parser")
    mutated = False
    for element in soup.find_all("div"):
        block = _extract_snippet_block(element)
        if block is None:
            continue
        pdf_url, png_url = resolver(block)
        anchor = soup.new_tag(
            "a",
            href=pdf_url,
            target="_blank",
            rel="noopener noreferrer",
        )
        image_attrs = {"src": png_url, "alt": block.caption or "Snippet", "class": ["ts-snippet"]}
        if block.figure_width:
            image_attrs["width"] = block.figure_width
        image = soup.new_tag("img", **image_attrs)
        anchor.append(image)
        element.replace_with(anchor)
        mutated = True

    return str(soup) if mutated else html


def register(renderer: Any) -> None:
    """Register the snippet handler on a renderer instance."""
    renderer.register(render_snippet_block)


def _announce_build(
    block: SnippetBlock, host_path: Path | str | None, emitter: DiagnosticEmitter | None
) -> None:
    """Emit an informational message when a snippet is actually compiled."""
    source_hint = f" from {host_path}" if host_path else ""
    _log.info("texsmith: building snippet %s%s", block.asset_basename, source_hint)
    if emitter is not None:
        try:
            emitter.event(
                "snippet_build",
                {"digest": block.digest, "source": str(host_path) if host_path else ""},
            )
        except Exception:
            _log.debug("failed to emit snippet_build event", exc_info=True)


__all__ = [
    "SNIPPET_DIR",
    "SnippetBlock",
    "asset_filename",
    "ensure_snippet_assets",
    "register",
    "render_snippet_block",
    "rewrite_html_snippets",
]
