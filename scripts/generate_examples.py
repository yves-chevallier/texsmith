#!/usr/bin/env python
"""Render TeXSmith examples and export PNG/PDF snapshots."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import contextlib
from dataclasses import dataclass, field
import json
import logging
import math
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


try:  # pragma: no cover - optional dependency alias
    import pymupdf as fitz  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - compatibility alias
    import fitz  # type: ignore[import-not-found]

from PIL import Image  # type: ignore[import]

from texsmith.api.service import ConversionRequest, ConversionService
from texsmith.api.templates import TemplateRenderResult
from texsmith.ui.cli.commands import build_latexmk_command


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_OUTPUT = PROJECT_ROOT / "docs" / "assets" / "examples"
SERVICE = ConversionService()
LOGGER = logging.getLogger(__name__)
MAGENTA = "#FF00FF"
PREVIEW_DPI = 200
MM_PER_INCH = 25.4

BORDER_PREAMBLE = r"""
\usepackage{tikz}
\usetikzlibrary{calc,backgrounds}
\AddToHook{shipout/foreground}{%
  \begin{tikzpicture}[remember picture,overlay]
    \def\margin{1cm}
    \def\e{1cm}
    \coordinate (A) at ($(current page.north west) + (0.1,-0.1)$);
    \coordinate (B) at ($(current page.north east) + (-0.1,-0.1)$);
    \coordinate (C) at ($(current page.south east) + (-0.1,0.1)$);
    \coordinate (D) at ($(current page.south west) + (0.1,0.1)$);
    \coordinate (Bdown) at ($(B)-(0,\e)$);
    \coordinate (Bleft) at ($(B)-(\e,0)$);
    \coordinate (Corner) at ($(B)-(\e,\e)$);
    \draw (A) -- (Bleft) -- (Bdown) -- (C) -- (D) -- cycle;
    \draw (Corner)
     .. controls ($(Corner)+(0.3*\e,0.1*\e)$) and ($(Bdown)+(-0.3*\e,-0.1*\e)$) ..
     (Bdown);
    \draw (Bleft)
     .. controls ($(Bleft)+(0.1*\e,-0.3*\e)$) and ($(Corner)+(-0.1*\e,0.3*\e)$) ..
     (Corner);
  \end{tikzpicture}%
}
"""


@dataclass(frozen=True)
class PreviewGrid:
    """Describe how PDF pages should be combined into PNG previews."""

    columns: int = 1
    rows: int = 1
    gap_mm: float = 0.0

    def to_signature(self) -> dict[str, float | int]:
        return {"columns": self.columns, "rows": self.rows, "gap": self.gap_mm}

    def gap_pixels(self) -> int:
        if self.gap_mm <= 0:
            return 0
        return max(0, round((self.gap_mm / MM_PER_INCH) * PREVIEW_DPI))

    def resolve_dimensions(self, page_count: int) -> tuple[int, int]:
        cols = self.columns
        rows = self.rows

        if cols <= 0 and rows <= 0:
            cols = 1
            rows = 1
        elif cols <= 0:
            rows = max(1, rows)
            cols = math.ceil(page_count / rows) if page_count else 1
        elif rows <= 0:
            cols = max(1, cols)
            rows = math.ceil(page_count / cols) if page_count else 1

        return max(1, cols), max(1, rows)


def _coerce_preview_grid(value: PreviewGrid | Mapping[str, Any] | None) -> PreviewGrid:
    if isinstance(value, PreviewGrid):
        return value
    if isinstance(value, Mapping):
        columns = int(value.get("columns", 1) or 1)
        rows = int(value.get("rows", 1) or 1)
        gap_value = value.get("gap", value.get("gap_mm", 0.0))
        gap = float(gap_value) if gap_value is not None else 0.0
        return PreviewGrid(columns=columns, rows=rows, gap_mm=gap)
    return PreviewGrid()


@dataclass(frozen=True)
class ExampleSpec:
    """Description of an example asset to render."""

    name: str
    source: Path
    build_dir: Path
    template_options: dict[str, Any] = field(default_factory=dict)
    template: str = "article"
    title_from_heading: bool = False
    persist_debug_html: bool = False
    bibliography: list[Path] = field(default_factory=list)
    extra_inputs: list[Path] = field(default_factory=list)
    preview_page: int = 0
    transparent_border: bool | None = None
    preview_grid: PreviewGrid | Mapping[str, Any] | None = None

    def input_paths(self) -> list[Path]:
        """Return the list of inputs tracked for freshness."""
        unique: list[Path] = []
        for candidate in [self.source, *self.bibliography, *self.extra_inputs]:
            if candidate not in unique:
                unique.append(candidate)
        return unique

    def __post_init__(self) -> None:
        object.__setattr__(self, "preview_grid", _coerce_preview_grid(self.preview_grid))
        if self.transparent_border is None:
            wants_border = bool(self.template_options.get("preamble"))
            object.__setattr__(self, "transparent_border", wants_border)
        else:
            object.__setattr__(self, "transparent_border", bool(self.transparent_border))


@dataclass(frozen=True)
class CopyTask:
    """Describe a derived asset that needs snippet escaping or extra copies."""

    source: Path
    destination: Path
    transformer: Callable[[Path, Path], None]
    extra_files: tuple[tuple[Path, Path], ...] = ()


def _latest_mtime(paths: list[Path]) -> float:
    """Return the latest modification time among inputs."""
    mtimes = [path.stat().st_mtime for path in paths if isinstance(path, Path) and path.exists()]
    return max(mtimes) if mtimes else 0.0


def _needs_render(target: Path, inputs: list[Path]) -> bool:
    """Return True when target is missing or older than its dependencies."""
    if not target.exists():
        return True
    newest_input = _latest_mtime(inputs)
    return newest_input > target.stat().st_mtime


def _compile_pdf(result: TemplateRenderResult) -> Path:
    latexmk_path = shutil.which("latexmk")
    if latexmk_path is None:  # pragma: no cover - runtime guard
        raise RuntimeError("latexmk executable not found in PATH.")

    command = build_latexmk_command(
        result.template_engine,
        shell_escape=result.requires_shell_escape,
        force_bibtex=result.has_bibliography,
    )
    command[0] = latexmk_path
    command.append(result.main_tex_path.name)

    subprocess.run(command, check=True, cwd=result.main_tex_path.parent)
    return result.main_tex_path.with_suffix(".pdf")


def _preview_meta_path(png_path: Path) -> Path:
    return png_path.with_suffix(png_path.suffix + ".meta")


def _write_preview_meta(png_path: Path, meta: dict[str, Any]) -> None:
    meta_path = _preview_meta_path(png_path)
    meta_path.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")


def _read_preview_meta(png_path: Path) -> dict[str, Any] | None:
    meta_path = _preview_meta_path(png_path)
    try:
        payload = meta_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    try:
        data: Any = json.loads(payload)
    except json.JSONDecodeError:
        try:
            return {"page_index": int(payload)}
        except ValueError:
            return None
    if isinstance(data, dict):
        return data
    return None


def _render_page_image(page: fitz.Page) -> Image.Image:
    pixmap = page.get_pixmap(dpi=PREVIEW_DPI)
    mode = "RGBA" if pixmap.alpha else "RGB"
    return Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)


def _compose_preview(
    images: list[Image.Image],
    columns: int,
    rows: int,
    gap_px: int,
) -> Image.Image:
    if not images:
        raise ValueError("No pages available to compose preview.")
    width, height = images[0].size
    usable_rows = max(1, math.ceil(len(images) / max(1, columns)))
    total_rows = max(rows, usable_rows)

    canvas_width = columns * width + max(0, columns - 1) * gap_px
    canvas_height = total_rows * height + max(0, total_rows - 1) * gap_px
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")

    for position, image in enumerate(images):
        row = position // columns
        col = position % columns
        x = col * (width + gap_px)
        y = row * (height + gap_px)
        canvas.paste(image, (x, y))
    return canvas


def _pdf_to_png(
    pdf_path: Path,
    target_path: Path,
    *,
    page_index: int = 0,
    grid: PreviewGrid | None = None,
) -> None:
    grid = grid or PreviewGrid()
    with fitz.open(pdf_path) as document:
        page_count = document.page_count
        if page_count == 0:
            raise RuntimeError(f"{pdf_path} does not contain any pages.")
        start_index = min(max(page_index, 0), page_count - 1)
        columns, rows = grid.resolve_dimensions(page_count)
        total_slots = max(1, columns * rows)
        last_index = min(page_count, start_index + total_slots)
        indices = list(range(start_index, last_index))
        images = [_render_page_image(document.load_page(i)) for i in indices]
        if len(images) == 1 and columns == 1 and rows == 1 and grid.gap_mm <= 0:
            images[0].save(target_path)
        else:
            canvas = _compose_preview(images, columns, rows, grid.gap_pixels())
            canvas.save(target_path)
    _write_preview_meta(
        target_path,
        {
            "page_index": start_index,
            "grid": grid.to_signature(),
        },
    )


def _sync_png(
    pdf_path: Path,
    png_path: Path,
    *,
    page_index: int = 0,
    grid: PreviewGrid | None = None,
) -> None:
    """Ensure the PNG preview matches the PDF timestamp."""
    if not pdf_path.exists():
        return
    grid = grid or PreviewGrid()
    recorded_meta = _read_preview_meta(png_path)
    expected_meta = {"page_index": page_index, "grid": grid.to_signature()}
    needs_refresh = recorded_meta != expected_meta
    if (
        needs_refresh
        or not png_path.exists()
        or png_path.stat().st_mtime < pdf_path.stat().st_mtime
    ):
        _pdf_to_png(pdf_path, png_path, page_index=page_index, grid=grid)


def _apply_transparent_border(png_path: Path) -> None:
    """Flood-fill the outer background to transparent."""
    convert_path = shutil.which("convert")
    if convert_path is None:
        LOGGER.warning("ImageMagick 'convert' not found; skipping transparency for %s", png_path)
        return

    filled = png_path.with_suffix(".filled.png")
    try:
        subprocess.run(
            [
                convert_path,
                str(png_path),
                "-fill",
                MAGENTA,
                "-draw",
                "color 1,1 floodfill",
                str(filled),
            ],
            check=True,
        )
        subprocess.run(
            [
                convert_path,
                str(filled),
                "-transparent",
                MAGENTA,
                str(png_path),
            ],
            check=True,
        )
    finally:
        with contextlib.suppress(FileNotFoundError):
            filled.unlink()


def _render_example(spec: ExampleSpec) -> tuple[Path, Path]:
    DOCS_OUTPUT.mkdir(parents=True, exist_ok=True)
    target_pdf = DOCS_OUTPUT / f"{spec.name}.pdf"
    target_png = DOCS_OUTPUT / f"{spec.name}.png"
    dependencies = spec.input_paths()
    grid = spec.preview_grid

    if dependencies and not _needs_render(target_pdf, dependencies):
        _sync_png(target_pdf, target_png, page_index=spec.preview_page, grid=grid)
        LOGGER.info("Skipping %s (up-to-date)", spec.name)
        return target_pdf, target_png

    shutil.rmtree(spec.build_dir, ignore_errors=True)
    spec.build_dir.mkdir(parents=True, exist_ok=True)

    request = ConversionRequest(
        documents=[spec.source],
        template=spec.template,
        render_dir=spec.build_dir,
        title_from_heading=spec.title_from_heading,
        persist_debug_html=spec.persist_debug_html,
        template_options=spec.template_options,
        bibliography_files=list(spec.bibliography),
    )

    prepared = SERVICE.prepare_documents(request)
    response = SERVICE.execute(request, prepared=prepared)
    render_result = response.render_result

    pdf_path = _compile_pdf(render_result)

    shutil.copy2(pdf_path, target_pdf)
    _pdf_to_png(pdf_path, target_png, page_index=spec.preview_page, grid=grid)
    if spec.transparent_border:
        _apply_transparent_border(target_png)
    return target_pdf, target_png


def _write_snippet_copy(source: Path, destination: Path) -> None:
    """Copy a Markdown file while escaping snippet markers and orphan footnotes."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(r"^([ \t]*)(-+8<-+)")
    footnote = re.compile(r"^([ \t]*)\[\^([^\]]+)\]:(.*)$")
    with (
        source.open("r", encoding="utf-8") as infile,
        destination.open("w", encoding="utf-8") as outfile,
    ):
        for line in infile:
            if pattern.match(line):
                outfile.write(pattern.sub(r"\1;\2", line, count=1))
            elif footnote.match(line):
                outfile.write(footnote.sub(r"\1;[^\2]:\3", line, count=1))
            else:
                outfile.write(line)


def _needs_copy(target: Path, dependencies: list[Path]) -> bool:
    if not target.exists():
        return True
    newest = _latest_mtime(dependencies)
    return newest > target.stat().st_mtime


def _build_specs() -> list[ExampleSpec]:
    examples_dir = PROJECT_ROOT / "examples"
    code_dir = examples_dir / "code"
    math_dir = examples_dir / "math"
    admonition_dir = examples_dir / "admonition"
    abbr_dir = examples_dir / "abbr"
    mermaid_dir = examples_dir / "mermaid"
    progress_dir = examples_dir / "progressbar"
    diagrams_dir = examples_dir / "diagrams"
    booby_dir = examples_dir / "booby"
    letter_dir = examples_dir / "letter"
    paper_dir = examples_dir / "paper"
    dialects_dir = examples_dir / "dialects"
    colorful_dir = examples_dir / "colorful"
    index_dir = examples_dir / "index"

    specs: list[ExampleSpec] = [
        ExampleSpec(
            name="code-block",
            source=code_dir / "code-block.md",
            build_dir=code_dir / "build",
            template_options={
                "paper": "a5",
                "orientation": "landscape",
                "margin": "1cm",
                "page_numbers": False,
                "preamble": BORDER_PREAMBLE,
            },
            transparent_border=True,
        ),
        ExampleSpec(
            name="code-inline",
            source=code_dir / "code-inline.md",
            build_dir=code_dir / "build",
            template_options={
                "paper": "a5",
                "orientation": "portrait",
                "margin": "narrow",
                "page_numbers": False,
                "geometry": {"paperheight": "5cm"},
                "preamble": BORDER_PREAMBLE,
            },
            transparent_border=True,
        ),
        ExampleSpec(
            name="equation",
            source=math_dir / "math.md",
            build_dir=math_dir / "build",
            persist_debug_html=True,
            template_options={
                "paper": "a5",
                "orientation": "landscape",
                "margin": "1cm",
                "page_numbers": False,
                "preamble": BORDER_PREAMBLE,
            },
            transparent_border=True,
        ),
        ExampleSpec(
            name="abbreviations",
            source=abbr_dir / "example.md",
            build_dir=abbr_dir / "build",
            template_options={
                "paper": "a5",
                "orientation": "landscape",
                "margin": "1cm",
                "page_numbers": False,
                "preamble": BORDER_PREAMBLE,
            },
            transparent_border=True,
        ),
        ExampleSpec(
            name="mermaid",
            source=mermaid_dir / "example.md",
            build_dir=mermaid_dir / "build",
            persist_debug_html=True,
            template_options={
                "paper": "a5",
                "margin": "narrow",
                "page_numbers": False,
                "geometry": {"paperheight": "17cm"},
                "preamble": BORDER_PREAMBLE,
            },
            transparent_border=True,
        ),
        ExampleSpec(
            name="progressbar",
            source=progress_dir / "example.md",
            build_dir=progress_dir / "build",
            template_options={
                "paper": "a5",
                "margin": "narrow",
                "page_numbers": False,
                "geometry": {"paperheight": "15cm"},
                "preamble": BORDER_PREAMBLE,
            },
            transparent_border=True,
        ),
        ExampleSpec(
            name="booby",
            source=booby_dir / "booby.md",
            build_dir=booby_dir / "build",
            template_options={
                "paper": "a5",
                "preamble": BORDER_PREAMBLE,
            },
            transparent_border=True,
        ),
        ExampleSpec(
            name="diagrams",
            source=diagrams_dir / "diagrams.md",
            build_dir=diagrams_dir / "build",
            template_options={
                "paper": "a5",
                "orientation": "landscape",
                "margin": "1cm",
                "page_numbers": False,
                "preamble": BORDER_PREAMBLE,
            },
            extra_inputs=[diagrams_dir / "pgcd.drawio"],
            preview_page=1,
            transparent_border=True,
        ),
        ExampleSpec(
            name="paper",
            source=paper_dir / "cheese.md",
            build_dir=paper_dir / "build" / "preview",
            template="article",
            title_from_heading=True,
            bibliography=[paper_dir / "cheese.bib"],
            template_options={
                "preamble": BORDER_PREAMBLE,
            },
            preview_grid={"columns": 2, "rows": 2, "gap": 3},
            transparent_border=True,
        ),
        ExampleSpec(
            name="dialects",
            source=dialects_dir / "dialects.md",
            build_dir=dialects_dir / "build" / "preview",
            template="article",
            title_from_heading=True,
            template_options={
                "preamble": BORDER_PREAMBLE,
            },
            preview_grid={"columns": 2, "rows": 1, "gap": 3},
            transparent_border=True,
        ),
        ExampleSpec(
            name="colorful",
            source=colorful_dir / "colorful.md",
            build_dir=colorful_dir / "build",
            template=str(colorful_dir / "template"),
            extra_inputs=[
                colorful_dir / "template" / "manifest.toml",
                colorful_dir / "template" / "template" / "template.tex",
            ],
        ),
        ExampleSpec(
            name="index",
            source=index_dir / "example.md",
            build_dir=index_dir / "build",
            template="article",
            title_from_heading=False,
            template_options={
                "margin": "narrow",
                "geometry": {"paperheight": "6cm"},
                "preamble": BORDER_PREAMBLE,
            },
            preview_grid={"columns": 1, "rows": -1, "gap": 3},
            transparent_border=True,
        ),
    ]

    for style in ("fancy", "classic", "minimal"):
        specs.append(
            ExampleSpec(
                name=f"{style}-admonition",
                source=admonition_dir / "admonition.md",
                build_dir=admonition_dir / "build" / style,
                template_options={
                    "paper": "a6",
                    "orientation": "landscape",
                    "margin": "0.5cm",
                    "page_numbers": False,
                    "callout_style": style,
                    "preamble": BORDER_PREAMBLE,
                },
                transparent_border=True,
            )
        )

    for layout in ("din", "nf", "sn"):
        specs.append(
            ExampleSpec(
                name=f"letter-{layout}",
                source=letter_dir / "letter.md",
                build_dir=letter_dir / "build" / layout,
                template="letter",
                title_from_heading=True,
                template_options={
                    "preamble": BORDER_PREAMBLE,
                    "press": {"format": layout},
                },
                transparent_border=True,
            )
        )

    return specs


def _run_copy_tasks(tasks: list[CopyTask]) -> None:
    for task in tasks:
        if _needs_copy(task.destination, [task.source]):
            task.transformer(task.source, task.destination)
        for extra_source, extra_dest in task.extra_files:
            extra_dest.parent.mkdir(parents=True, exist_ok=True)
            if _needs_copy(extra_dest, [extra_source]):
                shutil.copy2(extra_source, extra_dest)


COPY_TASKS = [
    CopyTask(
        source=PROJECT_ROOT / "examples" / "paper" / "cheese.md",
        destination=DOCS_OUTPUT / "cheese.md",
        transformer=_write_snippet_copy,
        extra_files=(
            (
                PROJECT_ROOT / "examples" / "paper" / "mozzarella.svg",
                DOCS_OUTPUT / "mozzarella.svg",
            ),
        ),
    ),
    CopyTask(
        source=PROJECT_ROOT / "examples" / "dialects" / "dialects.md",
        destination=DOCS_OUTPUT / "dialects.md",
        transformer=_write_snippet_copy,
    ),
]


def main() -> None:
    DOCS_OUTPUT.mkdir(parents=True, exist_ok=True)
    specs = _build_specs()
    for spec in specs:
        pdf_path, png_path = _render_example(spec)
        LOGGER.info("Rendered %s: %s, %s", spec.name, pdf_path.name, png_path.name)
    _run_copy_tasks(COPY_TASKS)


if __name__ == "__main__":
    main()
