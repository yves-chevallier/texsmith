"""Implementation of the `texsmith build` command."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess

import click
import typer

from ...api.service import (
    SlotAssignment,
    apply_slot_assignments,
    build_callbacks,
    build_render_settings,
    execute_conversion,
    prepare_documents,
    split_document_inputs,
)
from ...conversion import ConversionError
from ...conversion.inputs import UnsupportedInputError
from ...latex.log import stream_latexmk_output
from ...markdown import resolve_markdown_extensions
from ...templates import TemplateError
from ..state import debug_enabled, emit_error, emit_warning, get_cli_state
from ..utils import (
    parse_slot_option,
    resolve_option,
)


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


def build(
    inputs: list[Path] | None = typer.Argument(  # type: ignore[assignment]
        [],
        metavar="INPUT...",
        help=(
            "Conversion inputs. Provide a Markdown/HTML source document and optionally "
            "one or more BibTeX files."
        ),
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    output_dir: Path = typer.Option(
        Path("build"),
        "--output-dir",
        "-o",
        help="Directory used to collect generated assets (if any).",
    ),
    selector: str = typer.Option(
        "article.md-content__inner",
        "--selector",
        help="CSS selector to extract the MkDocs article content.",
    ),
    full_document: bool = typer.Option(
        False,
        "--full-document",
        help="Disable article extraction and render the entire HTML file.",
    ),
    base_level: int = typer.Option(
        0,
        "--base-level",
        help="Shift detected heading levels by this offset.",
    ),
    heading_level: int = typer.Option(
        0,
        "--heading-level",
        "-h",
        min=0,
        help=(
            "Indent all headings by the selected depth (e.g. 1 turns sections into subsections)."
        ),
    ),
    drop_title: bool = typer.Option(
        False,
        "--drop-title/--keep-title",
        help="Drop the first document title heading.",
    ),
    numbered: bool = typer.Option(
        True,
        "--numbered/--unnumbered",
        help="Toggle numbered headings.",
    ),
    parser: str | None = typer.Option(
        None,
        "--parser",
        help='BeautifulSoup parser backend to use (defaults to "html.parser").',
    ),
    disable_fallback_converters: bool = typer.Option(
        False,
        "--no-fallback-converters",
        help=("Disable registration of placeholder converters when Docker is unavailable."),
    ),
    copy_assets: bool = typer.Option(
        True,
        "--copy-assets/--no-copy-assets",
        "-a/-A",
        help=("Control whether asset files are generated and copied to the output directory."),
    ),
    manifest: bool = typer.Option(
        False,
        "--manifest/--no-manifest",
        "-m/-M",
        help="Toggle generation of an asset manifest file (reserved).",
    ),
    template: str | None = typer.Option(
        None,
        "--template",
        "-t",
        help=(
            "Select a LaTeX template to use during conversion. "
            "Accepts a local path or a registered template name."
        ),
    ),
    debug_html: bool | None = typer.Option(
        None,
        "--debug-html/--no-debug-html",
        help=(
            "Persist the intermediate HTML snapshot used during conversion. "
            "Defaults to enabled when --debug is passed at the CLI root."
        ),
    ),
    classic_output: bool = typer.Option(
        False,
        "--classic-output/--rich-output",
        help=(
            "Display raw latexmk output without parsing (use --rich-output for structured logs)."
        ),
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        help="Language code passed to babel (defaults to metadata or english).",
    ),
    slots: list[str] = typer.Option(
        [],
        "--slot",
        "-s",
        help=(
            "Inject a document section into a template slot using 'slot:Section'. "
            "Repeat to map multiple sections."
        ),
    ),
    markdown_extensions: list[str] = typer.Option(
        [],
        "--markdown-extensions",
        "-x",
        help=(
            "Additional Markdown extensions to enable "
            "(comma or space separated values are accepted)."
        ),
    ),
    disable_markdown_extensions: list[str] = typer.Option(
        [],
        "--disable-markdown-extensions",
        "--disable-extension",
        "-d",
        help=(
            "Markdown extensions to disable. "
            "Provide a comma separated list or repeat the option multiple times."
        ),
    ),
    bibliography: list[Path] = typer.Option(
        [],
        "--bibliography",
        "-b",
        help="BibTeX files merged and exposed to the renderer.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
) -> None:
    """Orchestrate document conversion and compilation for the MkDocs workflow."""

    raw_inputs = resolve_option(inputs if inputs is not None else [])
    if raw_inputs is None:
        resolved_inputs: list[Path] = []
    elif isinstance(raw_inputs, Path):
        resolved_inputs = [raw_inputs]
    else:
        resolved_inputs = list(raw_inputs)

    resolved_bibliography_option = list(resolve_option(bibliography))
    documents, bibliography_files = split_document_inputs(
        resolved_inputs,
        resolved_bibliography_option,
    )
    if not documents:
        ctx = click.get_current_context()
        typer.echo(ctx.command.get_help(ctx))
        raise typer.Exit()
    if len(documents) != 1:
        raise typer.BadParameter("Provide exactly one Markdown or HTML document.")
    document_path = documents[0]

    resolved_markdown_extensions = resolve_markdown_extensions(
        resolve_option(markdown_extensions),
        resolve_option(disable_markdown_extensions),
    )
    try:
        requested_slots = parse_slot_option(resolve_option(slots))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    debug_snapshot = resolve_option(debug_html)
    if debug_snapshot is None:
        debug_snapshot = debug_enabled()

    template_identifier = resolve_option(template)
    if not template_identifier:
        emit_error("The build command requires a LaTeX template (--template).")
        raise typer.Exit(code=1)

    callbacks = build_callbacks(
        emit_warning=lambda message, exception=None: emit_warning(message, exception=exception),
        emit_error=lambda message, exception=None: emit_error(message, exception=exception),
        debug_enabled=debug_enabled(),
    )

    resolved_selector = resolve_option(selector)
    resolved_full_document = resolve_option(full_document)
    resolved_base_level = resolve_option(base_level)
    resolved_heading_level = resolve_option(heading_level)
    resolved_drop_title = resolve_option(drop_title)
    resolved_numbered = resolve_option(numbered)
    resolved_parser = resolve_option(parser)
    resolved_disable_fallback = resolve_option(disable_fallback_converters)
    resolved_copy_assets = resolve_option(copy_assets)
    resolved_manifest = resolve_option(manifest)
    resolved_language = resolve_option(language)

    try:
        prepared = prepare_documents(
            [document_path],
            selector=resolved_selector,
            full_document=resolved_full_document,
            heading_level=resolved_heading_level,
            base_level=resolved_base_level,
            drop_title_all=resolved_drop_title,
            drop_title_first_document=False,
            numbered=resolved_numbered,
            markdown_extensions=resolved_markdown_extensions,
            callbacks=callbacks,
        )
    except UnsupportedInputError as exc:
        if callbacks.emit_error is not None:
            callbacks.emit_error(str(exc), exc)
        else:
            emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc
    except ConversionError as exc:
        raise typer.Exit(code=1) from exc

    assignments: dict[Path, list[SlotAssignment]] = {
        document_path: [
            SlotAssignment(slot=slot_name, selector=selector_value, include_document=False)
            for slot_name, selector_value in requested_slots.items()
        ]
    }
    apply_slot_assignments(prepared.document_map, assignments)

    settings = build_render_settings(
        parser=resolved_parser,
        disable_fallback_converters=resolved_disable_fallback,
        copy_assets=resolved_copy_assets,
        manifest=resolved_manifest,
        persist_debug_html=bool(debug_snapshot),
        language=resolved_language,
        legacy_latex_accents=False,
    )

    render_dir = resolve_option(output_dir).resolve()
    try:
        outcome = execute_conversion(
            prepared.documents,
            settings=settings,
            callbacks=callbacks,
            bibliography_files=bibliography_files,
            template=template_identifier,
            render_dir=render_dir,
        )
    except (TemplateError, ConversionError) as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc

    render_result = outcome.render_result
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

    if classic_output:
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
            emit_error(f"latexmk exited with status {process.returncode}")
            raise typer.Exit(code=process.returncode)
    else:
        console = get_cli_state().console
        console.print("[bold cyan]Running latexmk…[/]")
        try:
            result = stream_latexmk_output(
                command,
                cwd=str(render_result.main_tex_path.parent),
                env=env,
                console=console,
            )
        except OSError as exc:
            if debug_enabled():
                raise
            emit_error(f"Failed to execute latexmk: {exc}", exception=exc)
            raise typer.Exit(code=1) from exc

        if result.returncode != 0:
            emit_error(f"latexmk exited with status {result.returncode}")
            raise typer.Exit(code=result.returncode)

    pdf_path = render_result.main_tex_path.with_suffix(".pdf")
    typer.secho(f"PDF document written to {pdf_path}", fg=typer.colors.GREEN)


# Expose runtime dependencies for test monkeypatching
build.shutil = shutil  # type: ignore[attr-defined]
build.subprocess = subprocess  # type: ignore[attr-defined]
