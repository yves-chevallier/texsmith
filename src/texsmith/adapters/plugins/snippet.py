"""Plugin rendering fenced snippet blocks into standalone PDF assets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from PIL import Image, ImageDraw

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
from texsmith.core.templates import TemplateRuntime, load_template_runtime


SNIPPET_DIR = "snippets"
_SNIPPET_PREFIX = "snippet-"
_TRUE_VALUES = {"1", "true", "on", "yes"}
_FALSE_VALUES = {"0", "false", "off", "no"}


@dataclass(slots=True)
class SnippetBlock:
    """Parsed representation of a snippet fence."""

    content: str
    caption: str | None
    label: str | None
    figure_width: str | None
    template_overrides: dict[str, Any]
    digest: str
    border_enabled: bool
    dogear_enabled: bool
    transparent_corner: bool

    @property
    def asset_basename(self) -> str:
        return f"{_SNIPPET_PREFIX}{self.digest}"


@dataclass(slots=True)
class _SnippetAssets:
    pdf: Path
    png: Path


_SNIPPET_RUNTIME: TemplateRuntime | None = None


def _resolve_runtime() -> TemplateRuntime:
    global _SNIPPET_RUNTIME
    if _SNIPPET_RUNTIME is None:
        _SNIPPET_RUNTIME = load_template_runtime("snippet")
    return _SNIPPET_RUNTIME


def _resolve_emitter(context: RenderContext) -> DiagnosticEmitter | None:
    emitter = context.runtime.get("emitter")
    if isinstance(emitter, DiagnosticEmitter):
        return emitter
    return None


def asset_filename(digest: str, suffix: str) -> str:
    """Return the deterministic filename for a snippet artefact."""
    return f"{_SNIPPET_PREFIX}{digest}{suffix}"


def _hash_payload(content: str, overrides: dict[str, str]) -> str:
    payload = {"content": content, "overrides": overrides}
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
) -> tuple[dict[str, Any], str | None, str | None, str | None]:
    overrides: dict[str, Any] = {}
    caption = coerce_attribute(element.get("data-caption")) or None
    label = coerce_attribute(element.get("data-label")) or None
    figure_width = (
        coerce_attribute(element.get("data-width"))
        or coerce_attribute(element.get("data-figure-width"))
        or None
    )

    for attr, value in element.attrs.items():
        if not isinstance(attr, str):
            continue
        key = attr.lower()
        if not key.startswith("data-snippet-"):
            continue
        normalised = key[len("data-snippet-") :].strip().replace("-", "_")
        if not normalised:
            continue
        overrides[normalised] = coerce_attribute(value) or ""

    if "no-border" in classes and "border" not in overrides:
        overrides["border"] = False

    for key, default in (("border", True), ("dogear_enabled", True)):
        if key in overrides:
            overrides[key] = _coerce_bool_option(overrides[key], default)

    return overrides, caption, label, figure_width


def _extract_snippet_block(element: Tag) -> SnippetBlock | None:
    classes = gather_classes(element.get("class"))
    if "snippet" not in classes:
        return None

    code_element = element.find("code")
    if code_element is None:
        raise InvalidNodeError("Snippet block is missing an inner <code> element.")
    content = code_element.get_text(strip=False)
    if not content.strip():
        return None

    overrides, caption, label, figure_width = _extract_template_overrides(element, classes)
    digest = _hash_payload(content, overrides)
    border_enabled = _coerce_bool_option(overrides.get("border"), True)
    dogear_enabled = _coerce_bool_option(overrides.get("dogear_enabled"), True)

    return SnippetBlock(
        content=content,
        caption=caption,
        label=label,
        figure_width=figure_width,
        template_overrides=overrides,
        digest=digest,
        border_enabled=border_enabled,
        dogear_enabled=dogear_enabled,
        transparent_corner=border_enabled and dogear_enabled,
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
        heading_level=0,
        title_strategy=TitleStrategy.DROP,
        numbered=False,
    )
    document = Document(
        source_path=synthetic,
        kind=InputKind.MARKDOWN,
        _html=rendered.html,
        _front_matter=rendered.front_matter,
        options=options,
        slots=DocumentSlots(),
    )
    document._initialise_slots_from_front_matter()
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
        raise LatexRenderingError(f"Failed to compile snippet: {detail}")

    return render_result.main_tex_path.with_suffix(".pdf")


def _load_pymupdf():
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

    pdf_missing = not pdf_path.exists()
    png_missing = not png_path.exists()
    apply_corner = block.transparent_corner if transparent_corner is None else transparent_corner

    if not pdf_missing and not png_missing:
        return _SnippetAssets(pdf=pdf_path, png=png_path)
    if not pdf_missing and png_missing:
        _pdf_to_png(pdf_path, png_path, transparent_corner=apply_corner)
        return _SnippetAssets(pdf=pdf_path, png=png_path)

    runtime = _resolve_runtime()
    if source_path is not None:
        host_path = Path(source_path)
    else:
        host_path = destination / "snippet.md"
    host_dir = host_path.parent
    host_name = host_path.stem or "snippet"

    document = _build_document(block, host_dir=host_dir, host_name=host_name)
    settings = RenderSettings(
        copy_assets=True,
        convert_assets=False,
        hash_assets=False,
        manifest=False,
    )
    session = TemplateSession(runtime=runtime, settings=settings, emitter=emitter)
    session.add_document(document)
    if block.template_overrides:
        session.update_options(block.template_overrides)

    work_dir = destination / f".build-{block.digest}"
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        render_result = session.render(work_dir)
        compiled_pdf = _compile_pdf(render_result)
        shutil.copy2(compiled_pdf, pdf_path)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    _pdf_to_png(pdf_path, png_path, transparent_corner=apply_corner)
    return _SnippetAssets(pdf=pdf_path, png=png_path)


def _render_snippet_assets(block: SnippetBlock, context: RenderContext) -> _SnippetAssets:
    emitter = _resolve_emitter(context)
    document_path = context.runtime.get("document_path")
    host_path = Path(document_path) if document_path else None
    return ensure_snippet_assets(
        block,
        output_dir=context.assets.output_root / SNIPPET_DIR,
        source_path=host_path or (context.assets.output_root / "snippet.md"),
        emitter=emitter,
        transparent_corner=block.transparent_corner,
    )


def _render_figure(context: RenderContext, assets: _SnippetAssets, block: SnippetBlock) -> NavigableString:
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
    block = _extract_snippet_block(element)
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
        image = soup.new_tag("img", src=png_url, alt=block.caption or "Snippet")
        anchor.append(image)
        element.replace_with(anchor)
        mutated = True

    return str(soup) if mutated else html


def register(renderer: Any) -> None:
    """Register the snippet handler on a renderer instance."""
    renderer.register(render_snippet_block)


__all__ = [
    "SNIPPET_DIR",
    "ensure_snippet_assets",
    "SnippetBlock",
    "asset_filename",
    "register",
    "render_snippet_block",
    "rewrite_html_snippets",
]
