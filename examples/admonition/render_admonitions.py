#!/usr/bin/env python
from __future__ import annotations

import shutil
from pathlib import Path

import fitz  # PyMuPDF

from texsmith.adapters.latex.engines import (
    EngineResult,
    build_engine_command,
    build_tex_env,
    compute_features,
    ensure_command_paths,
    missing_dependencies,
    resolve_engine,
    run_engine_command,
)
from texsmith.adapters.latex.tectonic import (
    BiberAcquisitionError,
    MakeglossariesAcquisitionError,
    TectonicAcquisitionError,
    select_makeglossaries,
    select_biber_binary,
    select_tectonic_binary,
)
from texsmith.api.service import ConversionRequest, ConversionService

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

    engine_choice = resolve_engine("tectonic", render_result.template_engine)
    template_context = getattr(render_result, "template_context", None) or getattr(
        render_result, "context", None
    )
    features = compute_features(
        requires_shell_escape=render_result.requires_shell_escape,
        bibliography=render_result.has_bibliography,
        document_state=render_result.document_state,
        template_context=template_context,
    )
    biber_binary: Path | None = None
    makeglossaries_binary: Path | None = None
    bundled_bin: Path | None = None
    try:
        selection = select_tectonic_binary(False, console=None)
        if features.bibliography:
            biber_binary = select_biber_binary(console=None)
            bundled_bin = biber_binary.parent
        if features.has_glossary:
            glossaries = select_makeglossaries(console=None)
            makeglossaries_binary = glossaries.path
            if glossaries.source == "bundled":
                bundled_bin = bundled_bin or glossaries.path.parent
    except (TectonicAcquisitionError, BiberAcquisitionError, MakeglossariesAcquisitionError) as exc:
        raise RuntimeError(str(exc)) from exc

    available_bins: dict[str, Path] = {}
    if biber_binary:
        available_bins["biber"] = biber_binary
    if makeglossaries_binary:
        available_bins["makeglossaries"] = makeglossaries_binary

    missing = missing_dependencies(
        engine_choice,
        features,
        use_system_tectonic=False,
        available_binaries=available_bins or None,
    )
    if missing:
        raise RuntimeError(
            f"Missing LaTeX tools for admonition preview: {', '.join(sorted(missing))}"
        )

    command_plan = ensure_command_paths(
        build_engine_command(
            engine_choice,
            features,
            main_tex_path=render_result.main_tex_path,
            tectonic_binary=selection.path,
        )
    )
    env = build_tex_env(
        render_result.main_tex_path.parent,
        isolate_cache=False,
        extra_path=bundled_bin,
        biber_path=biber_binary,
    )
    result: EngineResult = run_engine_command(
        command_plan,
        backend=engine_choice.backend,
        workdir=render_result.main_tex_path.parent,
        env=env,
        console=None,
        classic_output=True,
        features=features,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{engine_choice.label} exited with status {result.returncode} for {render_result.main_tex_path}"
        )

    return command_plan.pdf_path


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
