"""Implementation of the `texsmith render` command."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from typing import Annotated, Any, Mapping

import click
from click.core import ParameterSource
import typer

from texsmith.adapters.latex.log import stream_latexmk_output
from texsmith.adapters.markdown import resolve_markdown_extensions, split_front_matter
from texsmith.api.service import ConversionRequest, ConversionService
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
    ManifestOptionWithShort,
    MarkdownExtensionsOption,
    NumberedOption,
    OpenLogOption,
    OutputPathOption,
    ParserOption,
    SelectorOption,
    SlotsOption,
    TemplateOption,
    TitleFromHeadingOption,
)
from ..diagnostics import CliEmitter
from ..presenter import (
    consume_event_diagnostics,
    parse_latex_log,
    present_build_summary,
    present_conversion_summary,
    present_latexmk_failure,
)
from ..state import debug_enabled, emit_error, get_cli_state
from ..utils import determine_output_target, organise_slot_overrides, write_output_file


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


_MARKDOWN_SUFFIXES = {
    ".md",
    ".markdown",
    ".mdown",
    ".mkd",
    ".mkdown",
    ".mdtxt",
    ".text",
}


def _load_front_matter(path: Path) -> Mapping[str, Any] | None:
    """Return parsed Markdown front matter when available."""
    suffix = path.suffix.lower()
    if suffix not in _MARKDOWN_SUFFIXES:
        return None
    try:
        metadata, _ = split_front_matter(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return metadata if isinstance(metadata, dict) else {}


def _extract_press_template(metadata: Mapping[str, Any] | None) -> str | None:
    """Extract the template identifier declared in front matter."""
    if not isinstance(metadata, Mapping):
        return None

    direct = metadata.get("press/template")
    if isinstance(direct, str) and (candidate := direct.strip()):
        return candidate

    press_section = metadata.get("press")
    if isinstance(press_section, Mapping):
        candidate = press_section.get("template")
        if isinstance(candidate, str):
            candidate = candidate.strip()
            if candidate:
                return candidate

    dotted = metadata.get("press.template")
    if isinstance(dotted, str) and (candidate := dotted.strip()):
        return candidate

    return None


def _front_matter_has_title(metadata: Mapping[str, Any] | None) -> bool:
    """Return True when a title is declared in the front matter."""
    if not isinstance(metadata, Mapping):
        return False

    title = metadata.get("title")
    if isinstance(title, str) and title.strip():
        return True

    press_section = metadata.get("press")
    if isinstance(press_section, Mapping):
        press_title = press_section.get("title")
        if isinstance(press_title, str) and press_title.strip():
            return True

    dotted = metadata.get("press.title")
    if isinstance(dotted, str) and dotted.strip():
        return True

    return False


def _format_path_for_event(path: Path) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def render(
    inputs: InputPathArgument = None,
    input_path: Annotated[
        Path | None,
        typer.Option(
            "--input-path",
            help="Internal helper used for programmatic invocation.",
            hidden=True,
        ),
    ] = None,
    output: OutputPathOption = None,
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
    build_pdf: Annotated[
        bool,
        typer.Option(
            "--build/--no-build",
            help="Invoke latexmk after rendering to compile the resulting LaTeX project.",
        ),
    ] = False,
    language: LanguageOption = None,
    legacy_latex_accents: Annotated[
        bool,
        typer.Option(
            "--legacy-latex-accents/--unicode-latex-accents",
            help=(
                "Escape accented characters and ligatures with legacy LaTeX macros instead of "
                "emitting Unicode glyphs (defaults to Unicode output)."
            ),
        ),
    ] = False,
    slots: SlotsOption = None,
    markdown_extensions: MarkdownExtensionsOption = None,
    disable_markdown_extensions: DisableMarkdownExtensionsOption = None,
    bibliography: BibliographyOption = None,
    open_log: OpenLogOption = False,
) -> None:
    """Convert MkDocs documents into LaTeX artefacts and optionally build PDFs."""

    state = get_cli_state()
    ctx = click.get_current_context(silent=True)
    verbosity = state.verbosity
    if verbosity <= 0 and ctx is not None and ctx.parent is not None:
        verbosity = int(ctx.parent.params.get("verbose", 0) or 0)
        if verbosity > 0:
            state.verbosity = verbosity

    document_paths = list(inputs or [])
    if input_path is not None:
        if document_paths:
            raise typer.BadParameter("Provide either positional inputs or --input-path, not both.")
        document_paths = [input_path]

    document_paths, bibliography_files = _SERVICE.split_inputs(document_paths, bibliography or [])
    if not document_paths:
        raise typer.BadParameter("Provide a Markdown (.md) or HTML (.html) source document.")

    primary_front_matter: Mapping[str, Any] | None = None
    first_document = document_paths[0] if document_paths else None
    if first_document is not None:
        front_matter = _load_front_matter(first_document)
        if front_matter:
            primary_front_matter = front_matter

    template_param_source = ctx.get_parameter_source("template") if ctx else None
    title_param_source = ctx.get_parameter_source("title_from_heading") if ctx else None
    if (
        template_param_source in {None, ParameterSource.DEFAULT}
        and template is None
        and primary_front_matter is not None
    ):
        metadata_template = _extract_press_template(primary_front_matter)
        if metadata_template:
            template = metadata_template

    template_selected = bool(template)

    output_param_source = ctx.get_parameter_source("output") if ctx else None
    pdf_output_requested = bool(output and output.suffix.lower() == ".pdf")
    if pdf_output_requested and not build_pdf:
        typer.echo("Enabling --build to produce PDF output.")
        build_pdf = True

    if (
        template_selected
        and not title_from_heading
        and title_param_source in {None, ParameterSource.DEFAULT}
        and not _front_matter_has_title(primary_front_matter)
        and not drop_title
    ):
        title_from_heading = True

    if build_pdf and len(document_paths) != 1:
        raise typer.BadParameter(
            "Provide exactly one Markdown or HTML document when using --build."
        )

    if build_pdf and not template_selected:
        emit_error("The --build flag requires a LaTeX template (--template).")
        raise typer.Exit(code=1)

    if drop_title and title_from_heading:
        raise typer.BadParameter("--drop-title and --title-from-heading cannot be combined.")

    if classic_output and not build_pdf:
        raise typer.BadParameter("--classic-output can only be used together with --build.")

    if open_log and not build_pdf:
        raise typer.BadParameter("--open-log can only be used together with --build.")

    try:
        _, slot_assignments = organise_slot_overrides(slots, document_paths)
    except (typer.BadParameter, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    state_slot_rows: list[dict[str, object]] = []
    for doc_path, entries in slot_assignments.items():
        for entry in entries:
            state_slot_rows.append(
                {
                    "document": _format_path_for_event(doc_path),
                    "slot": entry.slot,
                    "selector": entry.selector,
                    "include_document": entry.include_document,
                }
            )
    if state_slot_rows:
        state.record_event("slot_assignments", {"entries": state_slot_rows})

    resolved_markdown_extensions = resolve_markdown_extensions(
        markdown_extensions,
        disable_markdown_extensions,
    )
    extension_line = f"Extensions: {', '.join(resolved_markdown_extensions) or '(none)'}"

    def _flush_diagnostics() -> None:
        lines: list[str] = []
        if verbosity >= 1:
            lines.append(extension_line)
        lines.extend(consume_event_diagnostics(state))
        for line in lines:
            typer.echo(line)

    debug_snapshot = debug_html if debug_html is not None else debug_enabled()

    output_mode, output_target = determine_output_target(template_selected, document_paths, output)
    resolved_output_target = output_target.resolve() if output_target is not None else None

    temp_render_dir: Path | None = None
    cleanup_render_dir = False
    cleanup_render_dir_path: Path | None = None
    final_pdf_target: Path | None = None

    if template_selected:
        if output_mode == "template-pdf":
            temp_render_dir = Path(tempfile.mkdtemp(prefix="texsmith-")).resolve()
            typer.echo(f"Using temporary output directory: {temp_render_dir}")
            cleanup_render_dir = True
            cleanup_render_dir_path = temp_render_dir
            final_pdf_target = resolved_output_target
        elif (
            build_pdf
            and output_mode == "template"
            and output_param_source in {None, ParameterSource.DEFAULT}
        ):
            temp_render_dir = Path(tempfile.mkdtemp(prefix="texsmith-")).resolve()
            typer.echo(f"Using temporary output directory: {temp_render_dir}")
            cleanup_render_dir = True
            cleanup_render_dir_path = temp_render_dir
            primary_name = document_paths[0].stem if document_paths else "texsmith"
            final_pdf_target = Path.cwd() / f"{primary_name}.pdf"

    render_dir_path: Path | None = None
    if template_selected:
        render_dir_path = temp_render_dir or resolved_output_target
    elif output_mode == "directory":
        render_dir_path = resolved_output_target

    if template_selected and render_dir_path is None:
        raise typer.BadParameter("Unable to resolve template output directory.")

    emitter = CliEmitter(state=state, debug_enabled=debug_enabled())

    request_render_dir = render_dir_path

    request = ConversionRequest(
        documents=document_paths,
        bibliography_files=bibliography_files,
        slot_assignments=slot_assignments,
        selector=selector,
        full_document=full_document,
        heading_level=heading_level,
        base_level=base_level,
        drop_title_all=drop_title if build_pdf else False,
        drop_title_first_document=False if build_pdf else drop_title,
        title_from_heading=title_from_heading,
        numbered=numbered,
        markdown_extensions=resolved_markdown_extensions,
        parser=parser,
        disable_fallback_converters=disable_fallback_converters,
        copy_assets=copy_assets,
        manifest=manifest,
        persist_debug_html=bool(debug_snapshot),
        language=language,
        legacy_latex_accents=legacy_latex_accents,
        template=template,
        render_dir=request_render_dir,
        emitter=emitter,
    )
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

    if not template_selected:
        bundle = response.bundle

        if output_mode == "stdout":
            typer.echo(bundle.combined_output())
            _flush_diagnostics()
            return

        if output_mode == "file":
            if resolved_output_target is None:
                raise typer.BadParameter("Output path is required when writing to a file.")
            try:
                write_output_file(resolved_output_target, bundle.combined_output())
            except OSError as exc:
                emit_error(str(exc), exception=exc)
                raise typer.Exit(code=1) from exc
            present_conversion_summary(
                state=state,
                output_mode=output_mode,
                bundle=bundle,
                output_path=resolved_output_target,
                render_result=None,
            )
            _flush_diagnostics()
            return

        if output_mode == "directory":
            present_conversion_summary(
                state=state,
                output_mode=output_mode,
                bundle=bundle,
                output_path=request.render_dir,
                render_result=None,
            )
            _flush_diagnostics()
            return

        raise RuntimeError(f"Unsupported output mode '{output_mode}'.")

    render_result = response.render_result

    render_dir = render_result.main_tex_path.parent.resolve()

    if not build_pdf:
        present_conversion_summary(
            state=state,
            output_mode="template",
            bundle=None,
            output_path=render_dir,
            render_result=render_result,
        )
        _flush_diagnostics()
        return

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

    tex_cache_root = (render_dir / ".texmf-cache").resolve()
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

    if classic_output:
        try:
            process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                cwd=render_dir,
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
                cwd=str(render_dir),
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
    final_pdf_path = pdf_path

    if final_pdf_target is not None:
        final_destination = final_pdf_target
        try:
            final_destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            emit_error(f"Unable to create output directory '{final_destination.parent}': {exc}", exc)
            raise typer.Exit(code=1) from exc
        try:
            shutil.copy2(pdf_path, final_destination)
        except OSError as exc:
            emit_error(f"Failed to write PDF to '{final_destination}': {exc}", exc)
            raise typer.Exit(code=1) from exc
        final_pdf_path = final_destination

    present_build_summary(state=state, render_result=render_result, pdf_path=final_pdf_path)
    _flush_diagnostics()

    if cleanup_render_dir and cleanup_render_dir_path is not None:
        shutil.rmtree(cleanup_render_dir_path, ignore_errors=True)


# Expose runtime dependencies for test monkeypatching
render.shutil = shutil  # type: ignore[attr-defined]
render.subprocess = subprocess  # type: ignore[attr-defined]
