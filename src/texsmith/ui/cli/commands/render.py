"""Implementation of the primary ``texsmith`` CLI command."""

from __future__ import annotations

import atexit
from collections.abc import Iterable, Mapping
import contextlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Annotated, Any
import warnings

import click
from click.core import ParameterSource
import typer

from texsmith.adapters.latex import build as pdf_build
from texsmith.adapters.latex.engines import (
    EngineResult,
    parse_latex_log,
    resolve_engine,
    run_engine_command,
)
from texsmith.core.bibliography import BibliographyCollection
from texsmith.core.conversion import ConversionRequest
from texsmith.core.conversion.inputs import UnsupportedInputError
from texsmith.core.conversion.policy import (
    DEPRECATED_LEVELS,
    declared_template,
    demote_deprecated,
)
from texsmith.core.conversion.resolution import NUMBERING_MODES, NUMBERING_OVERRIDE_KEY
from texsmith.core.conversion.service import ConversionService
from texsmith.core.conversion.typst import build_typst_pdf, render_typst_document
from texsmith.core.exceptions import ConversionError
from texsmith.core.front_matter import split_front_matter
from texsmith.core.metadata import PressMetadataError, normalise_press_metadata
from texsmith.core.sources import is_front_matter, is_markdown
from texsmith.core.templates import TemplateError
from texsmith.diagnostics import Diagnostic
from texsmith.version import get_version

from .._options import (
    DIAGNOSTICS_PANEL,
    OUTPUT_PANEL,
    BaseLevelOption,
    ConvertAssetsOption,
    DebugIrOption,
    DeprecatedOption,
    DiagnosticsJsonOption,
    DisableFragmentOption,
    EnableFragmentOption,
    FontsInfoOption,
    FormatOption,
    HashAssetsOption,
    HttpUserAgentOption,
    IncludePathOption,
    InputPathArgument,
    LanguageOption,
    MakefileDepsOption,
    ManifestOptionWithShort,
    NoCopyAssetsOption,
    NoPromoteTitleOption,
    NoTitleOption,
    NumberingOption,
    OpenLogOption,
    OutputPathOption,
    QuietOption,
    SlotsOption,
    StrictOption,
    StripHeadingOption,
    TemplateAttributeOption,
    TemplateInfoOption,
    TemplateOption,
)
from ..bibliography import print_bibliography_overview
from ..commands.templates import list_templates, scaffold_template, show_template_info
from ..diagnostics import CliEmitter
from ..plan import RenderOptionError, resolve_render_plan
from ..presenter import (
    consume_event_diagnostics,
    present_build_summary,
    present_context_attributes,
    present_conversion_summary,
    present_diagnostics_summary,
    present_fonts_info,
    present_latex_failure,
    write_diagnostics_json,
)
from ..state import debug_enabled, emit_error, set_cli_state
from ..utils import determine_output_target, organise_slot_overrides, write_output_file


_SERVICE = ConversionService()
_REQUEST_DEFAULTS = ConversionRequest()


def _deliver_reference_inventory(main_tex_path: Path, destination: Path) -> None:
    """Copy the reference inventory next to the delivered PDF."""
    from texsmith.core.crossrefs import INVENTORY_SUFFIX, relocate_inventory

    inventory = main_tex_path.with_name(f"{main_tex_path.stem}{INVENTORY_SUFFIX}")
    if not inventory.exists():
        return
    try:
        relocate_inventory(inventory, destination)
    except OSError as exc:  # pragma: no cover - the PDF itself was delivered
        warnings.warn(f"Could not deliver the cross-reference inventory: {exc}", stacklevel=2)


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
    if not (is_markdown(path) or is_front_matter(path)):
        return None
    try:
        metadata, _ = split_front_matter(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return metadata if isinstance(metadata, dict) else {}


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


class _RenderEmitter(CliEmitter):
    """The render command's emitter: applies the ``--deprecated`` level to every record.

    Parse records (``Document.load``), pass, ``resolve`` and ``write`` records
    all reach the sink through :meth:`diagnostic`, so lowering or dropping
    tmark's ``deprecated`` records here covers the whole run before the
    ``--strict`` check reads ``sink.strict_failed()``.
    """

    def __init__(self, *, deprecated: str = "warning", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.deprecated = deprecated

    def diagnostic(self, diagnostic: Diagnostic, cause: BaseException | None = None) -> None:
        record = demote_deprecated(diagnostic, self.deprecated)
        if record is not None:
            super().diagnostic(record, cause)


def render(
    show_version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the TeXSmith version and exit.",
            is_eager=True,
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
    quiet: QuietOption = False,
    strict: StrictOption = False,
    deprecated: DeprecatedOption = None,
    diagnostics_json: DiagnosticsJsonOption = None,
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
    base_level: BaseLevelOption = str(_REQUEST_DEFAULTS.base_level),
    strip_heading: StripHeadingOption = _REQUEST_DEFAULTS.strip_heading_all,
    no_promote_title: NoPromoteTitleOption = not _REQUEST_DEFAULTS.promote_title,
    no_title: NoTitleOption = _REQUEST_DEFAULTS.suppress_title,
    include_paths: IncludePathOption = None,
    no_copy_assets: NoCopyAssetsOption = not _REQUEST_DEFAULTS.copy_assets,
    convert_assets: ConvertAssetsOption = _REQUEST_DEFAULTS.convert_assets,
    hash_assets: HashAssetsOption = _REQUEST_DEFAULTS.hash_assets,
    http_user_agent: HttpUserAgentOption = _REQUEST_DEFAULTS.http_user_agent,
    diagrams_backend: Annotated[
        str | None,
        typer.Option(
            "--diagrams-backend",
            metavar="BACKEND",
            help="Force the backend for diagram conversion (draw.io, mermaid): playwright, local, or docker (auto-default).",
            case_sensitive=False,
        ),
    ] = _REQUEST_DEFAULTS.diagrams_backend,
    manifest: ManifestOptionWithShort = _REQUEST_DEFAULTS.manifest,
    make_deps: MakefileDepsOption = False,
    template: TemplateOption = None,
    embed_fragments: Annotated[
        bool,
        typer.Option(
            "--embed",
            help="Embed converted documents into the main document instead linking them with \\input.",
        ),
    ] = _REQUEST_DEFAULTS.embed_fragments,
    enable_fragments: EnableFragmentOption = None,
    disable_fragments: DisableFragmentOption = None,
    template_attributes: TemplateAttributeOption = None,
    debug_ir: DebugIrOption = None,
    classic_output: Annotated[
        bool,
        typer.Option(
            "--classic-output",
            help=("Display raw latexmk output without parsing."),
        ),
    ] = False,
    output_format: FormatOption = "latex",
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
    language: LanguageOption = _REQUEST_DEFAULTS.language,
    numbering: NumberingOption = "backend",
    legacy_latex_accents: Annotated[
        bool,
        typer.Option(
            "--legacy-latex-accents",
            help=(
                "Escape accented characters and ligatures with legacy LaTeX macros instead of "
                "emitting Unicode glyphs (defaults to Unicode output)."
            ),
        ),
    ] = _REQUEST_DEFAULTS.legacy_latex_accents,
    slots: SlotsOption = None,
    open_log: OpenLogOption = False,
    snippet_dump_dir: Annotated[
        Path | None,
        typer.Option(
            "--dump-snippets",
            metavar="DIR",
            help="Copy snippet render sources (tex, aux files) into DIR for inspection.",
            rich_help_panel=DIAGNOSTICS_PANEL,
        ),
    ] = None,
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

    if typer_ctx is not None and typer_ctx.resilient_parsing:
        return

    if show_version:
        typer.echo(get_version())
        raise typer.Exit()

    state = set_cli_state(ctx=typer_ctx, verbosity=verbose, debug=debug, quiet=quiet)
    output_format = (output_format or "latex").strip().lower()
    if output_format not in {"latex", "typst"}:
        raise typer.BadParameter("--format must be 'latex' or 'typst'.")
    # The Typst backend emits a ``.typ`` via the shared IR. With a template it
    # wraps the body in the template's [typst.template] scaffolding; without one
    # it emits a standalone document. It does not use the LaTeX fragment/engine
    # machinery, so the template *info/scaffold* flags are unsupported here.
    if output_format == "typst" and (template_info_flag or template_scaffold is not None):
        raise typer.BadParameter(
            "--format typst does not support --template-info/--template-scaffold."
        )
    numbering = (numbering or "backend").strip().lower()
    if numbering not in NUMBERING_MODES:
        raise typer.BadParameter("--numbering must be 'backend' or 'tmark'.")
    if deprecated is not None:
        deprecated = deprecated.strip().lower()
        if deprecated not in DEPRECATED_LEVELS:
            raise typer.BadParameter("--deprecated must be 'warning', 'info' or 'off'.")
    if snippet_dump_dir is not None:
        os.environ["TEXSMITH_SNIPPET_DUMP_DIR"] = str(snippet_dump_dir)

    if list_templates_flag:
        list_templates()
        raise typer.Exit()

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
    shared_front_matter_paths = split_result.front_matter_paths

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

    # The template has to be known before the two flags that report on one and
    # exit; everything else the flags imply is settled by ``resolve_render_plan``.
    template_param_source = ctx.get_parameter_source("template") if ctx else None
    no_promote_param_source = ctx.get_parameter_source("no_promote_title") if ctx else None
    if template is None and template_param_source in {None, ParameterSource.DEFAULT}:
        template = declared_template(primary_front_matter)

    if template_requested:
        identifier = template or "article"
        if template_info_flag:
            show_template_info(identifier)
        if template_scaffold:
            scaffold_template(identifier, template_scaffold)
        raise typer.Exit()

    attribute_overrides = _parse_template_attributes(template_attributes)
    has_attributes = bool(attribute_overrides)
    if attribute_overrides:
        try:
            normalise_press_metadata(attribute_overrides)
        except PressMetadataError as exc:
            raise typer.BadParameter(str(exc)) from exc
    if engine:
        attribute_overrides.setdefault("_texsmith_latex_engine", engine)
    if numbering != "backend":
        # Read by both IR backends (``core.conversion.resolution.numbering_mode``).
        attribute_overrides[NUMBERING_OVERRIDE_KEY] = numbering

    try:
        plan = resolve_render_plan(
            front_matter=fm_payload,
            template=template,
            build_pdf=build_pdf,
            output=output,
            output_format=output_format,
            print_context=print_context,
            has_attributes=has_attributes,
            no_title=no_title,
            strip_heading=strip_heading,
            no_promote_title=no_promote_title,
            no_promote_defaulted=no_promote_param_source in {None, ParameterSource.DEFAULT},
            base_level=base_level,
            base_level_defaulted=(ctx.get_parameter_source("base_level") if ctx else None)
            in {None, ParameterSource.DEFAULT},
            classic_output=classic_output,
            open_log=open_log,
            make_deps=make_deps,
            strict=strict,
            deprecated=deprecated,
            template_options=attribute_overrides,
            ci_runner=os.environ.get("ACT") == "true",
        )
    except RenderOptionError as exc:
        raise typer.BadParameter(str(exc)) from exc

    template = plan.template
    template_selected = plan.template_selected
    build_pdf = plan.build_pdf
    classic_output = plan.classic_output
    promote_title = plan.promote_title
    numbered = plan.numbered
    strict = plan.strict
    deprecated = plan.deprecated
    resolved_base_level = plan.base_level
    for notice in plan.notices:
        typer.echo(notice)

    if attribute_overrides:
        state.record_event("template_attributes", {"values": attribute_overrides})

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

    emitter = _RenderEmitter(state=state, debug_enabled=debug_enabled(), deprecated=deprecated)
    presented_diagnostics = 0

    def _flush_diagnostics() -> None:
        """Close a phase: event lines, the diagnostics summary, the JSON dump, ``--strict``.

        Called at every exit of the command and, when building, once more
        before the engine runs so the ``.tex`` is there to inspect when
        ``--strict`` stops the run.
        """
        nonlocal presented_diagnostics
        lines: list[str] = list(consume_event_diagnostics(state))
        for line in lines:
            typer.echo(line)
        if len(emitter.sink) > presented_diagnostics:
            presented_diagnostics = len(emitter.sink)
            present_diagnostics_summary(state, emitter.sink)
        if diagnostics_json is not None:
            try:
                write_diagnostics_json(diagnostics_json, emitter.sink)
            except OSError as exc:
                emit_error(f"Failed to write diagnostics to '{diagnostics_json}': {exc}", exc)
                raise typer.Exit(code=1) from exc
        if strict and emitter.sink.strict_failed():
            emit_error("Diagnostics were recorded and --strict is on.")
            raise typer.Exit(code=1)

    debug_snapshot = debug_ir if debug_ir is not None else debug_enabled()

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
        elif build_pdf and output_mode == "template" and output is None:
            # Keyed on the absence of ``-o`` itself, not on Typer's parameter
            # source: that source is ``None`` whenever the command runs without
            # a click context, which used to route an explicit ``-o dir`` to a
            # temporary directory and drop the PDF in the current directory.
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

    request_render_dir = render_dir_path

    request = ConversionRequest(
        copy_assets=copy_assets,
        convert_assets=convert_assets,
        hash_assets=hash_assets,
        manifest=manifest,
        persist_debug_ir=bool(debug_snapshot),
        language=language,
        http_user_agent=http_user_agent,
        legacy_latex_accents=legacy_latex_accents,
        diagrams_backend=diagrams_backend.lower() if isinstance(diagrams_backend, str) else None,
        documents=document_paths,
        bibliography_files=bibliography_files,
        front_matter=shared_front_matter,
        front_matter_paths=shared_front_matter_paths,
        slot_assignments=slot_assignments,
        include_paths=list(include_paths or ()),
        base_level=resolved_base_level,
        strip_heading_all=strip_heading if build_pdf else False,
        strip_heading_first_document=False if build_pdf else strip_heading,
        promote_title=promote_title,
        suppress_title=no_title,
        numbered=numbered,
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
            "copy_assets": copy_assets,
            "convert_assets": convert_assets,
            "hash_assets": hash_assets,
            "manifest": manifest,
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

    if output_format == "typst":
        typst_output_dir: Path | None = None
        if output_mode in {"directory", "template"}:
            typst_output_dir = resolved_output_target
        elif output_mode == "file" and resolved_output_target is not None:
            typst_output_dir = resolved_output_target.parent

        def _emit_typst(doc: Any) -> str:
            try:
                return render_typst_document(
                    doc,
                    request,
                    output_dir=typst_output_dir,
                    emitter=emitter,
                )
            except (ConversionError, TemplateError) as exc:
                # ``raise_conversion_error`` already put the record in the sink
                # and marked the exception as logged, so the message reaches the
                # console only if this exit flushes like every other one.
                _flush_diagnostics()
                emit_error(str(exc), exception=exc)
                raise typer.Exit(code=1) from exc

        typst_docs = [(doc.source_path, _emit_typst(doc)) for doc in prepared.documents]
        if output_mode == "stdout":
            typer.echo("\n\n".join(payload for _, payload in typst_docs))
            _flush_diagnostics()
            return

        written_paths: list[Path] = []
        if output_mode == "file":
            if resolved_output_target is None:
                raise typer.BadParameter("Output path is required when writing Typst to a file.")
            try:
                write_output_file(resolved_output_target, typst_docs[0][1])
            except OSError as exc:
                emit_error(str(exc), exception=exc)
                raise typer.Exit(code=1) from exc
            written_paths.append(resolved_output_target)
        elif output_mode in {"directory", "template"}:
            if resolved_output_target is None:
                raise typer.BadParameter("Output directory is required when writing Typst files.")
            resolved_output_target.mkdir(parents=True, exist_ok=True)
            for source_path, payload in typst_docs:
                target = resolved_output_target / f"{source_path.stem}.typ"
                try:
                    write_output_file(target, payload)
                except OSError as exc:
                    emit_error(str(exc), exception=exc)
                    raise typer.Exit(code=1) from exc
                written_paths.append(target)
        else:
            raise RuntimeError(f"Unsupported output mode '{output_mode}' for Typst output.")

        for path in written_paths:
            typer.echo(f"Wrote {path}")
        if build_pdf:
            for path in written_paths:
                ok, message = build_typst_pdf(path)
                typer.echo(message)
                if not ok and debug_enabled():
                    raise typer.Exit(code=1)
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
        if print_context:
            present_context_attributes(state=state, render_result=render_result)
        if fonts_info:
            present_fonts_info(state, render_result)
        _flush_diagnostics()
        return

    # Engine orchestration (binary selection, command/env build, run) lives in
    # adapters.latex.build.build_pdf; the CLI keeps only presentation, the PDF copy,
    # and dependency-file emission. ``build_pdf`` takes the runner as a parameter,
    # which is the seam a test substitutes.
    # The bodies are written: ``--strict`` decides here, before the engine runs.
    _flush_diagnostics()

    engine_choice = resolve_engine(engine, render_result.template_engine)
    state.console.print(f"[bold cyan]Running {engine_choice.label}…[/]")

    try:
        engine_result: EngineResult = pdf_build.build_pdf(
            render_result,
            engine=engine,
            classic_output=classic_output,
            isolate_cache=isolate_cache,
            console=state.console,
            verbosity=state.verbosity,
            use_system_tectonic=system_tectonic,
            run_engine=run_engine_command,
        )
    except ConversionError as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc
    except OSError as exc:
        if debug_enabled():
            raise
        emit_error(f"Failed to execute {engine_choice.label}: {exc}", exception=exc)
        raise typer.Exit(code=1) from exc

    if engine_result.returncode != 0:
        messages = engine_result.messages or parse_latex_log(engine_result.log_path)
        present_latex_failure(
            state=state,
            log_path=engine_result.log_path,
            messages=messages,
            open_log=open_log,
        )
        emit_error(f"{engine_choice.label} exited with status {engine_result.returncode}")
        raise typer.Exit(code=engine_result.returncode)

    pdf_path = engine_result.pdf_path
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

        # The reference inventory is written next to the intermediate ``.tex``,
        # which is a temporary directory in this mode: without this it would be
        # deleted along with it, and its pages — harvested from the ``.aux`` —
        # would never reach anyone.
        _deliver_reference_inventory(render_result.main_tex_path, final_destination.parent)

    if make_deps:
        dependency_paths: set[Path] = set()
        dependency_paths.update(document_paths)
        dependency_paths.update(bibliography_files)
        dependency_paths.update(shared_front_matter_paths)
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
    _flush_diagnostics()

    if cleanup_render_dir and cleanup_render_dir_path is not None:
        shutil.rmtree(cleanup_render_dir_path, ignore_errors=True)
