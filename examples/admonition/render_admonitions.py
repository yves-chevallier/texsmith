#!/usr/bin/env python
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import fitz  # PyMuPDF

from texsmith.api.service import ConversionRequest, ConversionService
from texsmith.ui.cli.commands import build_latexmk_command

STYLES = ("fancy", "classic", "minimal")
BASE_DIR = Path(__file__).resolve().parent
BUILD_ROOT = BASE_DIR / "build"
DOCS_DIR = BASE_DIR.parent.parent / "docs" / "markdown"
SERVICE = ConversionService()


def _prepare_dirs() -> None:
    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def _render_style(style: str) -> Path:
    output_dir = BUILD_ROOT / style
    output_dir.mkdir(parents=True, exist_ok=True)

    request = ConversionRequest(
        documents=[BASE_DIR / "admonition.md"],
        template="article",
        render_dir=output_dir,
        template_options={
            "paper": "a6",
            "orientation": "landscape",
            "margin": "0.5cm",
            "page_numbers": False,
            "callout_style": style,
        },
    )

    prepared = SERVICE.prepare_documents(request)
    response = SERVICE.execute(request, prepared=prepared)
    render_result = response.render_result

    latexmk_path = shutil.which("latexmk")
    if latexmk_path is None:
        raise RuntimeError("latexmk executable not found in PATH.")

    command = build_latexmk_command(
        render_result.template_engine,
        shell_escape=render_result.requires_shell_escape,
        force_bibtex=render_result.has_bibliography,
    )
    command[0] = latexmk_path
    command.append(render_result.main_tex_path.name)

    subprocess.run(command, check=True, cwd=render_result.main_tex_path.parent)
    return render_result.main_tex_path.with_suffix(".pdf")


def _pdf_to_png(pdf_path: Path, target_path: Path) -> None:
    with fitz.open(pdf_path) as document:
        page = document.load_page(0)
        pixmap = page.get_pixmap(dpi=200)
        pixmap.save(target_path)


def main() -> None:
    _prepare_dirs()
    for style in STYLES:
        pdf = _render_style(style)
        png_path = DOCS_DIR / f"{style}-admonition.png"
        _pdf_to_png(pdf, png_path)
    print(f"Admonition previews exported to {DOCS_DIR}.")


if __name__ == "__main__":
    main()
