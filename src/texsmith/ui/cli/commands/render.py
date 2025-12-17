"""Implementation of the primary ``texsmith`` CLI command."""

from __future__ import annotations

import atexit
from collections.abc import Iterable, Mapping
import contextlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Annotated, Any

import click
from click.core import ParameterSource
import typer

from texsmith.adapters.latex.engines import (
    EngineResult,
    build_engine_command as build_latex_engine_command,
    build_tex_env,
    compute_features,
    ensure_command_paths,
    missing_dependencies,
    parse_latex_log,
    resolve_engine,
    run_engine_command,
)
from texsmith.adapters.latex.pyxindy import is_available as pyxindy_available
from texsmith.adapters.latex.tectonic import (
    BiberAcquisitionError,
    MakeglossariesAcquisitionError,
    TectonicAcquisitionError,
    select_biber_binary,
    select_makeglossaries,
    select_tectonic_binary,
)
from texsmith.adapters.markdown import (
    DEFAULT_MARKDOWN_EXTENSIONS,
    resolve_markdown_extensions,
    split_front_matter,
)
from texsmith.api.service import ConversionRequest, ConversionService
from texsmith.core.bibliography import BibliographyCollection
from texsmith.core.conversion.debug import ConversionError
from texsmith.core.conversion.inputs import UnsupportedInputError
from texsmith.core.metadata import PressMetadataError, normalise_press_metadata
from texsmith.core.templates import TemplateError
from texsmith.core.templates.runtime import coerce_base_level
from texsmith.fonts.html_scripts import wrap_scripts_in_html

from .._options import (
    DIAGNOSTICS_PANEL,
    OUTPUT_PANEL,
    BaseLevelOption,
    ConvertAssetsOption,
    DebugHtmlOption,
    DebugRulesOption,
    DisableFallbackOption,
    DisableFragmentOption,
    DisableMarkdownExtensionsOption,
    EnableFragmentOption,
    FontsInfoOption,
    FullDocumentOption,
    HashAssetsOption,
    HtmlOnlyOption,
    InputPathArgument,
    LanguageOption,
    MakefileDepsOption,
    ManifestOptionWithShort,
    MarkdownExtensionsOption,
    NoCopyAssetsOption,
    NoPromoteTitleOption,
    NoTitleOption,
    OpenLogOption,
    OutputPathOption,
    ParserOption,
    SelectorOption,
    SlotsOption,
    StripHeadingOption,
    TemplateAttributeOption,
    TemplateInfoOption,
    TemplateOption,
)
from ..bibliography import print_bibliography_overview
from ..commands.templates import list_templates, scaffold_template, show_template_info
from ..diagnostics import CliEmitter
from ..presenter import (
    consume_event_diagnostics,
    present_build_summary,
    present_context_attributes,
    present_conversion_summary,
    present_fonts_info,
    present_html_summary,
    present_latex_failure,
    present_rule_descriptions,
)
from ..state import debug_enabled, emit_error, set_cli_state
from ..utils import determine_output_target, organise_slot_overrides, write_output_file


_SERVICE = ConversionService()


_MARKDOWN_SUFFIXES = {
    ".md",
    ".markdown",
    ".mdown",
    ".mkd",
    ".mkdown",
    ".mdtxt",
    ".text",
    ".yml",
    ".yaml",
}


def _cleanup_temp_input(path: Path) -> None:
    """Remove the temporary input file if it exists.

    This cleanup step prevents filesystem clutter when the user pipes content
    via stdin, ensuring that temporary files don't accumulate over time.
    """
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)


def _read_stdin_document() -> Path | None:
    """Write stdin content to a temporary Markdown file when piped."""
    stream = sys.stdin
    if stream is None or stream.closed:
        return None
    try:
        if stream.isatty():
            return None
    except (AttributeError, ValueError):
        return None

    payload = stream.read()
    if not payload:
        return None

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        prefix="texsmith-stdin-",
        encoding="utf-8",
        delete=False,
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    atexit.register(_cleanup_temp_input, temp_path)
    return temp_path


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

    payload = dict(metadata)
    with contextlib.suppress(PressMetadataError):
        normalise_press_metadata(payload)

    template_value = payload.get("template")
    if isinstance(template_value, str) and (candidate := template_value.strip()):
        return candidate
    return None


def _format_path_for_event(path: Path) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def _relativize_path(path: Path, base: Path) -> Path:
    """Return a path relative to ``base`` when possible."""
    try:
        return path.resolve().relative_to(base)
    except ValueError:
        try:
            return Path(os.path.relpath(path, base))
        except ValueError:
            return path.resolve()


def _escape_make_path(path: Path) -> str:
    """Escape whitespace and backslashes for Makefile dependency entries."""
    raw = path.as_posix()
    raw = raw.replace("\\", "\\\\")
    return raw.replace(" ", "\\ ")


def _write_makefile_deps(target: Path, dependencies: Iterable[Path]) -> Path:
    """Write a Makefile-compatible .d file for the given target."""
    base = Path.cwd()
    resolved_target = target.resolve()
    dep_path = resolved_target.with_suffix(resolved_target.suffix + ".d")
    dep_path.parent.mkdir(parents=True, exist_ok=True)

    seen: set[Path] = set()
    normalised: list[Path] = []
    for dep in dependencies:
        if not dep:
            continue
        try:
            resolved = Path(dep).resolve()
        except OSError:
            continue
        if resolved == resolved_target or resolved in seen:
            continue
        if not resolved.exists():
            continue
        seen.add(resolved)
        normalised.append(resolved)

    normalised = sorted(normalised, key=lambda path: path.as_posix())
    rel_target = _escape_make_path(_relativize_path(resolved_target, base))
    rel_deps = [_escape_make_path(_relativize_path(dep, base)) for dep in normalised]
    content = f"{rel_target}: {' '.join(rel_deps)}\n" if rel_deps else f"{rel_target}:\n"
    dep_path.write_text(content, encoding="utf-8")
    return dep_path


def _coerce_attribute_value(raw: str) -> Any:
    """Infer the type of a template attribute value from its string representation.

    This bridges the gap between string-only CLI arguments and the typed configuration
    expected by templates, allowing users to pass booleans and numbers naturally.
    """
    candidate = raw.strip()
    lowered = candidate.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if candidate.startswith(("0x", "0X")):
            return int(candidate, 16)
        return int(candidate)
    except ValueError:
        pass
    try:
        return float(candidate)
    except ValueError:
        pass
    return candidate


def _assign_nested_value(target: dict[str, Any], path: list[str], value: Any) -> None:
    """Set a value in a nested dictionary structure using a list of keys.

    This enables dot-notation configuration (e.g. `theme.color=red`) for complex
    template settings, allowing deep overrides from the flat CLI interface.
    """
    cursor = target
    for key in path[:-1]:
        if key not in cursor:
            cursor[key] = {}
        elif not isinstance(cursor[key], dict):
            raise typer.BadParameter(
                f"Invalid attribute override for '{'.'.join(path)}', "
                f"'{key}' is already assigned to a non-mapping value."
            )
        cursor = cursor[key]  # type: ignore[assignment]
    cursor[path[-1]] = value


def _parse_template_attributes(values: Iterable[str] | None) -> dict[str, Any]:
    """Parse a list of key=value strings into a dictionary of attributes.

    This transforms the flat list of CLI arguments into a structured configuration
    dictionary that can be merged with the template's default settings.
    """
    overrides: dict[str, Any] = {}
    if not values:
        return overrides
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            continue
        if "=" not in raw:
            raise typer.BadParameter(f"Invalid attribute override '{raw}', expected key=value.")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter(f"Invalid attribute override '{raw}', empty key.")
        parts = [chunk for chunk in key.split(".") if chunk]
        if not parts:
            raise typer.BadParameter(f"Invalid attribute override '{raw}', empty key.")
        coerced = _coerce_attribute_value(value)
        if len(parts) == 1:
            overrides[parts[0]] = coerced
        else:
            _assign_nested_value(overrides, parts, coerced)
    return overrides


def _lookup_bool(mapping: Mapping[str, Any] | None, path: tuple[str, ...]) -> bool | None:
    """Walk a mapping to resolve a boolean-like value."""
    if not isinstance(mapping, Mapping):
        return None
    cursor: Any = mapping
    for key in path:
        if not isinstance(cursor, Mapping) or key not in cursor:
            return None
        cursor = cursor[key]
    if isinstance(cursor, bool):
        return cursor
    if isinstance(cursor, (int, float)):
        return bool(cursor)
    if isinstance(cursor, str):
        candidate = cursor.strip().lower()
        if candidate in {"true", "yes", "on", "1"}:
            return True
        if candidate in {"false", "no", "off", "0"}:
            return False
    return None


def render(
    list_extensions: Annotated[
        bool,
        typer.Option(
            "--list-extensions",
            help="List Markdown extensions enabled by default and exit.",
            rich_help_panel=DIAGNOSTICS_PANEL,
        ),
    ] = False,
    list_templates_flag: Annotated[
        bool,
        typer.Option(
            "--list-templates",
            help="List available templates (builtin, entry-point, and local) and exit.",
            rich_help_panel=DIAGNOSTICS_PANEL,
        ),
    ] = False,
    list_bibliography: Annotated[
        bool,
        typer.Option(
            "--list-bibliography",
            help="Print bibliography details from provided .bib files and exit.",
            rich_help_panel=DIAGNOSTICS_PANEL,
        ),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help=("Increase CLI verbosity. Combine multiple times for additional diagnostics."),
            rich_help_panel=DIAGNOSTICS_PANEL,
        ),
    ] = 0,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Show full tracebacks when an unexpected error occurs.",
            rich_help_panel=DIAGNOSTICS_PANEL,
        ),
    ] = False,
    debug_rules: DebugRulesOption = False,
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
    base_level: BaseLevelOption = "0",
    strip_heading: StripHeadingOption = False,
    no_promote_title: NoPromoteTitleOption = False,
    no_title: NoTitleOption = False,
    parser: ParserOption = None,
    disable_fallback_converters: DisableFallbackOption = False,
    no_copy_assets: NoCopyAssetsOption = False,
    convert_assets: ConvertAssetsOption = False,
    hash_assets: HashAssetsOption = False,
    diagrams_backend: Annotated[
        str | None,
        typer.Option(
            "--diagrams-backend",
            metavar="BACKEND",
            help="Force the backend for diagram conversion (draw.io, mermaid): playwright, local, or docker (auto-default).",
            case_sensitive=False,
        ),
    ] = None,
    manifest: ManifestOptionWithShort = False,
    make_deps: MakefileDepsOption = False,
    template: TemplateOption = None,
    embed_fragments: Annotated[
        bool,
        typer.Option(
            "--embed",
            help="Embed converted documents into the main document instead linking them with \\input.",
        ),
    ] = False,
    enable_fragments: EnableFragmentOption = None,
    disable_fragments: DisableFragmentOption = None,
    template_attributes: TemplateAttributeOption = None,
    debug_html: DebugHtmlOption = None,
    classic_output: Annotated[
        bool,
        typer.Option(
            "--classic-output",
            help=("Display raw latexmk output without parsing."),
        ),
    ] = False,
    html_only: HtmlOnlyOption = False,
    build_pdf: Annotated[
        bool,
        typer.Option(
            "-b",
            "--build",
            help="Invoke latexmk after rendering to compile the resulting LaTeX project.",
        ),
    ] = False,
    engine: Annotated[
        str,
        typer.Option(
            "-e",
            "--engine",
            help="LaTeX engine backend to use when building (tectonic, lualatex, xelatex).",
            rich_help_panel=OUTPUT_PANEL,
        ),
    ] = "tectonic",
    system_tectonic: Annotated[
        bool,
        typer.Option(
            "-S",
            "--system",
            help="Use the system Tectonic binary instead of the bundled download.",
            rich_help_panel=OUTPUT_PANEL,
        ),
    ] = False,
    language: LanguageOption = None,
    legacy_latex_accents: Annotated[
        bool,
        typer.Option(
            "--legacy-latex-accents",
            help=(
                "Escape accented characters and ligatures with legacy LaTeX macros instead of "
                "emitting Unicode glyphs (defaults to Unicode output)."
            ),
        ),
    ] = False,
    slots: SlotsOption = None,
    markdown_extensions: MarkdownExtensionsOption = None,
    disable_markdown_extensions: DisableMarkdownExtensionsOption = None,
    open_log: OpenLogOption = False,
    isolate_cache: Annotated[
        bool,
        typer.Option(
            "--isolate",
            help=(
                "Use a per-render TeX cache inside the output directory instead of the shared "
                "~/.cache/texsmith cache."
            ),
            rich_help_panel=OUTPUT_PANEL,
        ),
    ] = False,
    template_info_flag: TemplateInfoOption = False,
    template_scaffold: Annotated[
        Path | None,
        typer.Option(
            "--template-scaffold",
            metavar="DEST",
            help="Copy the selected template into DEST and exit.",
        ),
    ] = None,
    fonts_info: FontsInfoOption = False,
    print_context: Annotated[
        bool,
        typer.Option(
            "--print-context",
            help="Print resolved template context emitters/consumers and exit.",
            rich_help_panel=DIAGNOSTICS_PANEL,
        ),
    ] = False,
) -> None:
    """Convert MkDocs documents into LaTeX artefacts and optionally build PDFs."""

    ctx = click.get_current_context(silent=True)
    typer_ctx = ctx if isinstance(ctx, typer.Context) else None
    state = set_cli_state(ctx=typer_ctx, verbosity=verbose, debug=debug)
    if html_only:
        build_pdf = False
        template = None
        template_info_flag = False
        template_scaffold = None
    if print_context:
        build_pdf = False

    if typer_ctx is not None and typer_ctx.resilient_parsing:
        return

    if list_extensions:
        for extension in DEFAULT_MARKDOWN_EXTENSIONS:
            typer.echo(extension)
        raise typer.Exit()

    if list_templates_flag:
        list_templates()
        raise typer.Exit()

    verbosity_level = state.verbosity
    if verbosity_level <= 0 and typer_ctx is not None and typer_ctx.parent is not None:
        verbosity_level = int(typer_ctx.parent.params.get("verbose", 0) or 0)
        if verbosity_level > 0:
            state.verbosity = verbosity_level

    document_paths = list(inputs or [])
    if input_path is not None:
        if document_paths:
            raise typer.BadParameter("Provide either positional inputs or --input-path, not both.")
        document_paths = [input_path]

    if not document_paths:
        stdin_document = _read_stdin_document()
        if stdin_document is not None:
            document_paths = [stdin_document]

    try:
        split_result = _SERVICE.split_inputs(document_paths)
    except ConversionError as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc

    document_paths = split_result.documents
    bibliography_files = split_result.bibliography_files
    shared_front_matter = split_result.front_matter
    shared_front_matter_path = split_result.front_matter_path

    template_requested = template_info_flag or template_scaffold

    if list_bibliography:
        collection = BibliographyCollection()
        if bibliography_files:
            collection.load_files(bibliography_files)
        print_bibliography_overview(collection)
        raise typer.Exit()

    if not document_paths:
        if template_requested:
            identifier = template or "article"
            if template_info_flag:
                show_template_info(identifier)
            if template_scaffold:
                scaffold_template(identifier, template_scaffold)
            raise typer.Exit()
        raise typer.BadParameter(
            "Provide a Markdown (.md) or HTML (.html) source document or pipe content via stdin."
        )

    numbered = True
    copy_assets = not no_copy_assets
    primary_front_matter: Mapping[str, Any] | None = shared_front_matter
    first_document = document_paths[0] if document_paths else None
    if primary_front_matter is None and first_document is not None:
        front_matter = _load_front_matter(first_document)
        if front_matter:
            primary_front_matter = front_matter

    fm_payload: dict[str, Any] = {}
    if isinstance(primary_front_matter, Mapping):
        fm_payload = dict(primary_front_matter)
        try:
            normalise_press_metadata(fm_payload)
        except PressMetadataError as exc:
            raise typer.BadParameter(str(exc)) from exc

    fm_numbered = _lookup_bool(fm_payload, ("numbered",))
    if fm_numbered is not None:
        numbered = fm_numbered

    template_param_source = ctx.get_parameter_source("template") if ctx else None
    no_promote_param_source = ctx.get_parameter_source("no_promote_title") if ctx else None
    if (
        template_param_source in {None, ParameterSource.DEFAULT}
        and template is None
        and primary_front_matter is not None
    ):
        metadata_template = _extract_press_template(primary_front_matter)
        if metadata_template:
            template = metadata_template

    if template is None and (build_pdf or template_requested):
        template = "article"

    template_selected = bool(template)

    if template_requested:
        identifier = template or "article"
        if template_info_flag:
            show_template_info(identifier)
        if template_scaffold:
            scaffold_template(identifier, template_scaffold)
        raise typer.Exit()

    promote_title = not no_promote_title

    attribute_overrides = _parse_template_attributes(template_attributes)
    if attribute_overrides:
        try:
            normalise_press_metadata(attribute_overrides)
        except PressMetadataError as exc:
            raise typer.BadParameter(str(exc)) from exc
    if attribute_overrides and not template_selected:
        raise typer.BadParameter("--attribute can only be used together with --template.")
    if engine:
        attribute_overrides.setdefault("_texsmith_latex_engine", engine)
    attr_numbered = _lookup_bool(attribute_overrides, ("numbered",))
    if attr_numbered is not None:
        numbered = attr_numbered
    if attribute_overrides:
        state.record_event("template_attributes", {"values": attribute_overrides})

    output_param_source = ctx.get_parameter_source("output") if ctx else None
    pdf_output_requested = bool(output and output.suffix.lower() == ".pdf")
    if pdf_output_requested and not build_pdf:
        typer.echo("Enabling --build to produce PDF output.")
        build_pdf = True

    if no_title:
        promote_title = False

    if strip_heading:
        promote_title = False

    if build_pdf and not template_selected:
        template = "article"
        template_selected = True
        # In CI runners like act, prefer classic output to avoid streaming latexmk.
        if os.environ.get("ACT") == "true":
            classic_output = True

    if classic_output and not build_pdf:
        raise typer.BadParameter("--classic-output can only be used together with --build.")

    if open_log and not build_pdf:
        raise typer.BadParameter("--open-log can only be used together with --build.")
    if make_deps and not build_pdf:
        raise typer.BadParameter("--makefile-deps can only be used together with --build.")

    if print_context and not template_selected:
        raise typer.BadParameter(
            "--print-context requires a template (front matter or --template)."
        )

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

    base_level_param_source = ctx.get_parameter_source("base_level") if ctx else None
    base_level_value = base_level
    if not template_selected and base_level_param_source in {
        None,
        ParameterSource.DEFAULT,
    }:
        base_level_value = "section"
    try:
        resolved_base_level = coerce_base_level(base_level_value, allow_none=False)
    except TemplateError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if not template_selected and no_promote_param_source in {
        None,
        ParameterSource.DEFAULT,
    }:
        promote_title = False

    resolved_markdown_extensions = resolve_markdown_extensions(
        markdown_extensions,
        disable_markdown_extensions,
    )
    extension_line = f"Extensions: {', '.join(resolved_markdown_extensions) or '(none)'}"

    def _flush_diagnostics() -> None:
        lines: list[str] = []
        if state.verbosity >= 1:
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

    if not embed_fragments and template_selected and len(document_paths) == 1:
        embed_fragments = True

    emitter = CliEmitter(state=state, debug_enabled=debug_enabled())

    request_render_dir = render_dir_path

    request = ConversionRequest(
        documents=document_paths,
        bibliography_files=bibliography_files,
        front_matter=shared_front_matter,
        front_matter_path=shared_front_matter_path,
        slot_assignments=slot_assignments,
        selector=selector,
        full_document=full_document,
        base_level=resolved_base_level,
        strip_heading_all=strip_heading if build_pdf else False,
        strip_heading_first_document=False if build_pdf else strip_heading,
        promote_title=promote_title,
        suppress_title=no_title,
        numbered=numbered,
        markdown_extensions=resolved_markdown_extensions,
        parser=parser,
        disable_fallback_converters=disable_fallback_converters,
        copy_assets=copy_assets,
        convert_assets=convert_assets,
        hash_assets=hash_assets,
        manifest=manifest,
        persist_debug_html=bool(debug_snapshot),
        language=language,
        legacy_latex_accents=legacy_latex_accents,
        diagrams_backend=diagrams_backend.lower() if isinstance(diagrams_backend, str) else None,
        template=template,
        render_dir=request_render_dir,
        template_options=attribute_overrides,
        embed_fragments=embed_fragments,
        enable_fragments=enable_fragments or [],
        disable_fragments=disable_fragments or [],
        emitter=emitter,
    )
    state.record_event(
        "conversion_settings",
        {
            "parser": parser or "auto",
            "copy_assets": copy_assets,
            "convert_assets": convert_assets,
            "hash_assets": hash_assets,
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
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc

    if html_only:
        html_fragments = []
        for doc in prepared.documents:
            processed_html = doc.html
            try:
                processed_html, _usage, _summary = wrap_scripts_in_html(processed_html)
            except Exception:
                processed_html = doc.html
            html_fragments.append((doc.source_path, processed_html))
        if output_mode == "stdout":
            typer.echo("\n\n".join(fragment for _, fragment in html_fragments))
            _flush_diagnostics()
            return

        summary_paths: list[Path] = []
        if output_mode == "file":
            if resolved_output_target is None:
                raise typer.BadParameter("Output path is required when writing HTML to a file.")
            try:
                write_output_file(resolved_output_target, html_fragments[0][1])
            except OSError as exc:
                emit_error(str(exc), exception=exc)
                raise typer.Exit(code=1) from exc
            summary_paths.append(resolved_output_target)
        elif output_mode in {"directory", "template"}:
            if resolved_output_target is None:
                raise typer.BadParameter("Output directory is required when writing HTML files.")
            resolved_output_target.mkdir(parents=True, exist_ok=True)
            for source_path, payload in html_fragments:
                target = resolved_output_target / f"{source_path.stem}.html"
                try:
                    write_output_file(target, payload)
                except OSError as exc:
                    emit_error(str(exc), exception=exc)
                    raise typer.Exit(code=1) from exc
                summary_paths.append(target)
        elif output_mode == "template-pdf":
            raise typer.BadParameter("--html cannot be combined with a PDF output target.")
        else:
            raise RuntimeError(f"Unsupported output mode '{output_mode}' for HTML output.")

        present_html_summary(
            state=state,
            output_mode=output_mode,
            output_paths=summary_paths,
        )
        _flush_diagnostics()
        return

    engine_env_key = "TEXSMITH_SELECTED_ENGINE"
    previous_engine_value = os.environ.get(engine_env_key)
    if engine:
        os.environ[engine_env_key] = engine
    else:
        os.environ.pop(engine_env_key, None)
    try:
        response = _SERVICE.execute(request, prepared=prepared)
    except (TemplateError, ConversionError) as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc
    finally:
        if previous_engine_value is None:
            os.environ.pop(engine_env_key, None)
        else:
            os.environ[engine_env_key] = previous_engine_value

    def _emit_rule_diagnostics() -> None:
        if not debug_rules:
            return
        rules: list[dict[str, object]] = []
        if response.is_template:
            rules = getattr(response.render_result, "rule_descriptions", []) or []
        else:
            for fragment in response.bundle.fragments:
                conversion = fragment.conversion
                if conversion and conversion.rule_descriptions:
                    rules = conversion.rule_descriptions
                    break
        if rules:
            present_rule_descriptions(state, rules)

    if not template_selected:
        bundle = response.bundle

        if output_mode == "stdout":
            typer.echo(bundle.combined_output())
            _emit_rule_diagnostics()
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
            _emit_rule_diagnostics()
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
            _emit_rule_diagnostics()
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
        if print_context:
            present_context_attributes(state=state, render_result=render_result)
        if fonts_info:
            present_fonts_info(state, render_result)
        _emit_rule_diagnostics()
        _flush_diagnostics()
        return

    engine_choice = resolve_engine(engine, render_result.template_engine)
    template_context = getattr(render_result, "template_context", None) or getattr(
        render_result, "context", None
    )
    use_system_tectonic = system_tectonic if engine_choice.backend == "tectonic" else False
    features = compute_features(
        requires_shell_escape=render_result.requires_shell_escape,
        bibliography=render_result.has_bibliography,
        document_state=render_result.document_state,
        template_context=template_context,
    )

    tectonic_binary: Path | None = None
    biber_binary: Path | None = None
    makeglossaries_binary: Path | None = None
    bundled_bin: Path | None = None
    if engine_choice.backend == "tectonic":
        try:
            selection = select_tectonic_binary(use_system_tectonic, console=state.console)
            if features.bibliography and not use_system_tectonic:
                biber_binary = select_biber_binary(console=state.console)
                bundled_bin = biber_binary.parent
            if features.has_glossary and not pyxindy_available():
                glossaries = select_makeglossaries(console=state.console)
                makeglossaries_binary = glossaries.path
                if glossaries.source == "bundled":
                    bundled_bin = bundled_bin or glossaries.path.parent
        except (
            TectonicAcquisitionError,
            BiberAcquisitionError,
            MakeglossariesAcquisitionError,
        ) as exc:
            emit_error(str(exc), exception=exc)
            raise typer.Exit(code=1) from exc
        tectonic_binary = selection.path

    available_bins: dict[str, Path] = {}
    if biber_binary:
        available_bins["biber"] = biber_binary
    if makeglossaries_binary:
        available_bins["makeglossaries"] = makeglossaries_binary

    missing_tools = missing_dependencies(
        engine_choice,
        features,
        use_system_tectonic=use_system_tectonic,
        available_binaries=available_bins or None,
    )
    if missing_tools:
        formatted = ", ".join(sorted(missing_tools))
        emit_error(f"Missing required tools for {engine_choice.label}: {formatted}")
        raise typer.Exit(code=1)

    command_plan = ensure_command_paths(
        build_latex_engine_command(
            engine_choice,
            features,
            main_tex_path=render_result.main_tex_path,
            tectonic_binary=tectonic_binary,
        )
    )
    env = build_tex_env(
        render_dir,
        isolate_cache=isolate_cache,
        extra_path=bundled_bin,
        biber_path=biber_binary,
    )

    state.console.print(f"[bold cyan]Running {engine_choice.label}…[/]")

    run_engine = getattr(render, "run_engine_command", run_engine_command)

    try:
        engine_result: EngineResult = run_engine(
            command_plan,
            backend=engine_choice.backend,
            workdir=render_dir,
            env=env,
            console=state.console,
            verbosity=state.verbosity,
            classic_output=classic_output,
            features=features,
        )
    except OSError as exc:
        if debug_enabled():
            raise
        emit_error(f"Failed to execute {engine_choice.label}: {exc}", exception=exc)
        raise typer.Exit(code=1) from exc

    if engine_result.returncode != 0:
        messages = engine_result.messages or parse_latex_log(command_plan.log_path)
        present_latex_failure(
            state=state,
            log_path=command_plan.log_path,
            messages=messages,
            open_log=open_log,
        )
        emit_error(f"{engine_choice.label} exited with status {engine_result.returncode}")
        raise typer.Exit(code=engine_result.returncode)

    pdf_path = command_plan.pdf_path
    final_pdf_path = pdf_path
    dep_file_path: Path | None = None

    if final_pdf_target is not None:
        final_destination = final_pdf_target
        try:
            final_destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            emit_error(
                f"Unable to create output directory '{final_destination.parent}': {exc}",
                exc,
            )
            raise typer.Exit(code=1) from exc
        try:
            shutil.copy2(pdf_path, final_destination)
        except OSError as exc:
            emit_error(f"Failed to write PDF to '{final_destination}': {exc}", exc)
            raise typer.Exit(code=1) from exc
        final_pdf_path = final_destination

    if make_deps:
        dependency_paths: set[Path] = set()
        dependency_paths.update(document_paths)
        dependency_paths.update(bibliography_files)
        if shared_front_matter_path:
            dependency_paths.add(shared_front_matter_path)
        dependency_paths.add(render_result.main_tex_path)
        dependency_paths.update(render_result.fragment_paths)
        if render_result.bibliography_path:
            dependency_paths.add(render_result.bibliography_path)
        latexmkrc_candidate = render_dir / ".latexmkrc"
        if latexmkrc_candidate.exists():
            dependency_paths.add(latexmkrc_candidate)
        dependency_paths.update(getattr(render_result, "asset_paths", []))
        dependency_paths.update(getattr(render_result, "asset_sources", []))
        for key in getattr(render_result, "asset_map", {}) or {}:
            candidate_path = Path(key)
            if candidate_path.exists():
                dependency_paths.add(candidate_path)
        try:
            dep_file_path = _write_makefile_deps(final_pdf_path, dependency_paths)
        except OSError as exc:
            emit_error(f"Failed to write dependency file: {exc}", exc)
            raise typer.Exit(code=1) from exc

    present_build_summary(state=state, render_result=render_result, pdf_path=final_pdf_path)
    if fonts_info:
        present_fonts_info(state, render_result)
    if dep_file_path is not None:
        state.console.print(f"[cyan]Dependencies written to[/] {dep_file_path}")
    _emit_rule_diagnostics()
    _flush_diagnostics()

    if cleanup_render_dir and cleanup_render_dir_path is not None:
        shutil.rmtree(cleanup_render_dir_path, ignore_errors=True)


# Expose runtime dependencies for test monkeypatching
render.shutil = shutil  # type: ignore[attr-defined]
render.subprocess = subprocess  # type: ignore[attr-defined]
render.run_engine_command = run_engine_command  # type: ignore[attr-defined]
