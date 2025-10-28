"""Implementation of the `texsmith build` command."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Annotated

import click
import typer

from texsmith.adapters.latex.log import stream_latexmk_output
from texsmith.adapters.markdown import resolve_markdown_extensions
from texsmith.api.service import ConversionRequest, ConversionService, SlotAssignment
from texsmith.core.conversion.debug import ConversionError
from texsmith.core.conversion.inputs import UnsupportedInputError
from texsmith.core.templates import TemplateError

from .._options import (
    BaseLevelOption,
    BibliographyOption,
    CopyAssetsOptionWithShort,
    DebugHtmlOption,
    DisableFallbackOption,
    DisableMarkdownExtensionsOption,
    DropTitleOption,
    FullDocumentOption,
    HeadingLevelOption,
    InputPathArgument,
    LanguageOption,
    TitleFromHeadingOption,
    ManifestOptionWithShort,
    MarkdownExtensionsOption,
    NumberedOption,
    OpenLogOption,
    OutputDirOption,
    ParserOption,
    SelectorOption,
    SlotsOption,
    TemplateOption,
)
from ..diagnostics import CliEmitter
from ..presenter import (
    consume_event_diagnostics,
    parse_latex_log,
    present_build_summary,
    present_latexmk_failure,
)
from ..state import debug_enabled, emit_error, emit_warning, get_cli_state
from ..utils import parse_slot_option


_SERVICE = ConversionService()


def build_latexmk_command(
    engine: str | None,
    shell_escape: bool,
    force_bibtex: bool = False,
) -> list[str]:
    """Construct the latexmk command arguments respecting CLI options."""
    engine_command = (engine or "pdflatex").strip()
    if not engine_command:
        engine_command = "pdflatex"

    tokens = shlex.split(engine_command)
    if not tokens:
        tokens = ["pdflatex"]

    if shell_escape and not any(token in {"-shell-escape", "--shell-escape"} for token in tokens):
        tokens.append("--shell-escape")

    tokens.extend(["%O", "%S"])

    command = [
        "latexmk",
        "-pdf",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-pdflatex={' '.join(tokens)}",
    ]
    if force_bibtex:
        command.insert(2, "-bibtex")
    return command


def _format_path_for_event(path: Path) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def build(
    inputs: InputPathArgument = None,
    output_dir: OutputDirOption = Path("build"),
    selector: SelectorOption = "article.md-content__inner",
    full_document: FullDocumentOption = False,
    base_level: BaseLevelOption = 0,
    heading_level: HeadingLevelOption = 0,
    drop_title: DropTitleOption = False,
    title_from_heading: TitleFromHeadingOption = False,
    numbered: NumberedOption = True,
    parser: ParserOption = None,
    disable_fallback_converters: DisableFallbackOption = False,
    copy_assets: CopyAssetsOptionWithShort = True,
    manifest: ManifestOptionWithShort = False,
    template: TemplateOption = None,
    debug_html: DebugHtmlOption = None,
    classic_output: Annotated[
        bool,
        typer.Option(
            "--classic-output/--rich-output",
            help=(
                "Display raw latexmk output without parsing (use --rich-output for structured logs)."
            ),
        ),
    ] = False,
    language: LanguageOption = None,
    slots: SlotsOption = None,
    markdown_extensions: MarkdownExtensionsOption = None,
    disable_markdown_extensions: DisableMarkdownExtensionsOption = None,
    bibliography: BibliographyOption = None,
    open_log: OpenLogOption = False,
) -> None:
    """Orchestrate document conversion and compilation for the MkDocs workflow."""

    state = get_cli_state()
    resolved_inputs = list(inputs or [])

    documents, bibliography_files = _SERVICE.split_inputs(
        resolved_inputs,
        bibliography or [],
    )
    if not documents:
        ctx = click.get_current_context()
        typer.echo(ctx.command.get_help(ctx))
        raise typer.Exit()
    if len(documents) != 1:
        raise typer.BadParameter("Provide exactly one Markdown or HTML document.")
    document_path = documents[0]

    resolved_markdown_extensions = resolve_markdown_extensions(
        markdown_extensions,
        disable_markdown_extensions,
    )
    extension_line = f"Extensions: {', '.join(resolved_markdown_extensions) or '(none)'}"
    try:
        requested_slots = parse_slot_option(slots)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    debug_snapshot = debug_html if debug_html is not None else debug_enabled()

    template_identifier = template
    if not template_identifier:
        emit_error("The build command requires a LaTeX template (--template).")
        raise typer.Exit(code=1)

    if drop_title and title_from_heading:
        raise typer.BadParameter(
            "--drop-title and --title-from-heading cannot be combined."
        )

    emitter = CliEmitter(state=state, debug_enabled=debug_enabled())

    assignments: dict[Path, list[SlotAssignment]] = {
        document_path: [
            SlotAssignment(slot=slot_name, selector=selector_value, include_document=False)
            for slot_name, selector_value in requested_slots.items()
        ]
    }
    if requested_slots:
        state.record_event(
            "slot_assignments",
            {
                "entries": [
                    {
                        "document": _format_path_for_event(document_path),
                        "slot": slot_name,
                        "selector": selector_value,
                        "include_document": False,
                    }
                    for slot_name, selector_value in requested_slots.items()
                ]
            },
        )

    request = ConversionRequest(
        documents=[document_path],
        bibliography_files=bibliography_files,
        slot_assignments=assignments,
        selector=selector,
        full_document=full_document,
        heading_level=heading_level,
        base_level=base_level,
        drop_title_all=drop_title,
        drop_title_first_document=False,
        numbered=numbered,
        title_from_heading=title_from_heading,
        markdown_extensions=resolved_markdown_extensions,
        parser=parser,
        disable_fallback_converters=disable_fallback_converters,
        copy_assets=copy_assets,
        manifest=manifest,
        persist_debug_html=bool(debug_snapshot),
        language=language,
        legacy_latex_accents=False,
        template=template_identifier,
        render_dir=output_dir.resolve(),
        emitter=emitter,
    )

    def _flush_diagnostics() -> None:
        lines: list[str] = []
        if state.verbosity >= 1:
            lines.append(extension_line)
        lines.extend(consume_event_diagnostics(state))
        for line in lines:
            typer.echo(line)

    state.record_event(
        "conversion_settings",
        {
            "parser": parser or "auto",
            "copy_assets": copy_assets,
            "manifest": manifest,
            "fallback_converters_enabled": not disable_fallback_converters,
        },
    )

    try:
        prepared = _SERVICE.prepare_documents(request)
    except UnsupportedInputError as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc
    except ConversionError as exc:
        raise typer.Exit(code=1) from exc

    try:
        response = _SERVICE.execute(request, prepared=prepared)
    except (TemplateError, ConversionError) as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc

    render_result = response.render_result
    if render_result is None:  # pragma: no cover - defensive
        raise RuntimeError("Template render result missing from service outcome.")

    latexmk_path = shutil.which("latexmk")
    if latexmk_path is None:
        emit_error("latexmk executable not found. Install TeX Live (or latexmk) to build PDFs.")
        raise typer.Exit(code=1)

    command = build_latexmk_command(
        render_result.template_engine,
        render_result.requires_shell_escape,
        force_bibtex=render_result.has_bibliography,
    )
    command[0] = latexmk_path
    command.append(render_result.main_tex_path.name)

    tex_cache_root = (render_result.main_tex_path.parent / ".texmf-cache").resolve()
    tex_cache_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()

    texmf_home = tex_cache_root / "texmf-home"
    texmf_var = tex_cache_root / "texmf-var"
    luatex_cache = tex_cache_root / "luatex-cache"

    texmf_cache = tex_cache_root / "texmf-cache"
    texmf_config = tex_cache_root / "texmf-config"
    xdg_cache = tex_cache_root / "xdg-cache"

    for cache_path in (
        texmf_home,
        texmf_var,
        texmf_config,
        luatex_cache,
        texmf_cache,
        xdg_cache,
    ):
        cache_path.mkdir(parents=True, exist_ok=True)

    env["TEXMFHOME"] = str(texmf_home)
    env["TEXMFVAR"] = str(texmf_var)
    env["TEXMFCONFIG"] = str(texmf_config)
    env["LUATEXCACHE"] = str(luatex_cache)
    env["LUAOTFLOAD_CACHE"] = str(luatex_cache)
    env["TEXMFCACHE"] = str(texmf_cache)
    env.setdefault("XDG_CACHE_HOME", str(xdg_cache))

    if classic_output is True:
        try:
            process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                cwd=render_result.main_tex_path.parent,
                env=env,
            )
        except OSError as exc:
            if debug_enabled():
                raise
            emit_error(f"Failed to execute latexmk: {exc}", exception=exc)
            raise typer.Exit(code=1) from exc

        if process.stdout:
            typer.echo(process.stdout.rstrip())
        if process.stderr:
            typer.echo(process.stderr.rstrip(), err=True)

        if process.returncode != 0:
            log_path = render_result.main_tex_path.with_suffix(".log")
            messages = parse_latex_log(log_path)
            present_latexmk_failure(
                state=state,
                log_path=log_path,
                messages=messages,
                open_log=open_log,
            )
            emit_error(f"latexmk exited with status {process.returncode}")
            raise typer.Exit(code=process.returncode)
    else:
        console = state.console
        console.print("[bold cyan]Running latexmk…[/]")
        try:
            result = stream_latexmk_output(
                command,
                cwd=str(render_result.main_tex_path.parent),
                env=env,
                console=console,
                verbosity=state.verbosity,
            )
        except OSError as exc:
            if debug_enabled():
                raise
            emit_error(f"Failed to execute latexmk: {exc}", exception=exc)
            raise typer.Exit(code=1) from exc

        if result.returncode != 0:
            log_path = render_result.main_tex_path.with_suffix(".log")
            messages = result.messages or parse_latex_log(log_path)
            present_latexmk_failure(
                state=state,
                log_path=log_path,
                messages=messages,
                open_log=open_log,
            )
            emit_error(f"latexmk exited with status {result.returncode}")
            raise typer.Exit(code=result.returncode)

    pdf_path = render_result.main_tex_path.with_suffix(".pdf")
    present_build_summary(state=state, render_result=render_result, pdf_path=pdf_path)
    _flush_diagnostics()


# Expose runtime dependencies for test monkeypatching
build.shutil = shutil  # type: ignore[attr-defined]
build.subprocess = subprocess  # type: ignore[attr-defined]
