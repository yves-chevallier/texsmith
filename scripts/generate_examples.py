#!/usr/bin/env python
"""Render TeXSmith examples and export PNG/PDF snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
import subprocess
from typing import Any


try:  # pragma: no cover - optional dependency alias
    import pymupdf as fitz  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - compatibility alias
    import fitz  # type: ignore[import-not-found]

from texsmith.api.service import ConversionRequest, ConversionService
from texsmith.api.templates import TemplateRenderResult
from texsmith.ui.cli.commands import build_latexmk_command


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_OUTPUT = PROJECT_ROOT / "docs" / "assets" / "examples"
SERVICE = ConversionService()
LOGGER = logging.getLogger(__name__)

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
class ExampleSpec:
    """Description of an example asset to render."""

    name: str
    source: Path
    build_dir: Path
    template_options: dict[str, Any]
    template: str = "article"
    title_from_heading: bool = False
    persist_debug_html: bool = False


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


def _pdf_to_png(pdf_path: Path, target_path: Path) -> None:
    with fitz.open(pdf_path) as document:
        page = document.load_page(0)
        pixmap = page.get_pixmap(dpi=200)
        pixmap.save(target_path)


def _render_example(spec: ExampleSpec) -> tuple[Path, Path]:
    shutil.rmtree(spec.build_dir, ignore_errors=True)
    spec.build_dir.mkdir(parents=True, exist_ok=True)

    request = ConversionRequest(
        documents=[spec.source],
        template=spec.template,
        render_dir=spec.build_dir,
        title_from_heading=spec.title_from_heading,
        persist_debug_html=spec.persist_debug_html,
        template_options=spec.template_options,
    )

    prepared = SERVICE.prepare_documents(request)
    response = SERVICE.execute(request, prepared=prepared)
    render_result = response.render_result

    pdf_path = _compile_pdf(render_result)

    DOCS_OUTPUT.mkdir(parents=True, exist_ok=True)
    target_pdf = DOCS_OUTPUT / f"{spec.name}.pdf"
    target_png = DOCS_OUTPUT / f"{spec.name}.png"

    shutil.copy2(pdf_path, target_pdf)
    _pdf_to_png(pdf_path, target_png)
    return target_pdf, target_png


def _build_specs() -> list[ExampleSpec]:
    examples_dir = PROJECT_ROOT / "examples"
    code_dir = examples_dir / "code"
    math_dir = examples_dir / "math"
    admonition_dir = examples_dir / "admonition"
    abbr_dir = examples_dir / "abbr"
    mermaid_dir = examples_dir / "mermaid"

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
            )
        )

    return specs


def main() -> None:
    DOCS_OUTPUT.mkdir(parents=True, exist_ok=True)
    specs = _build_specs()
    for spec in specs:
        pdf_path, png_path = _render_example(spec)
        LOGGER.info("Rendered %s: %s, %s", spec.name, pdf_path.name, png_path.name)


if __name__ == "__main__":
    main()
