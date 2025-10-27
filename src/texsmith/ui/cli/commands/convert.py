"""Implementation of the `texsmith convert` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import click
import typer

from texsmith.api.service import (
    apply_slot_assignments,
    build_callbacks,
    build_render_settings,
    execute_conversion,
    prepare_documents,
    split_document_inputs,
)
from texsmith.core.conversion.debug import ConversionError
from texsmith.core.conversion.inputs import UnsupportedInputError
from texsmith.adapters.markdown import resolve_markdown_extensions
from texsmith.core.templates import TemplateError
from ..presenter import consume_event_diagnostics, present_conversion_summary
from ..state import debug_enabled, emit_error, emit_warning, get_cli_state
from ..utils import (
    determine_output_target,
    organise_slot_overrides,
    write_output_file,
)
from .._options import (
    BaseLevelOption,
    BibliographyOption,
    CopyAssetsOption,
    DebugHtmlOption,
    DisableFallbackOption,
    DisableMarkdownExtensionsOption,
    DropTitleOption,
    FullDocumentOption,
    HeadingLevelOption,
    InputPathArgument,
    LanguageOption,
    ManifestOption,
    MarkdownExtensionsOption,
    NumberedOption,
    OutputPathOption,
    ParserOption,
    SelectorOption,
    SlotsOption,
    TemplateOption,
)


def _format_path_for_event(path: Path) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def convert(
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
    numbered: NumberedOption = True,
    parser: ParserOption = None,
    disable_fallback_converters: DisableFallbackOption = False,
    copy_assets: CopyAssetsOption = True,
    manifest: ManifestOption = False,
    template: TemplateOption = None,
    debug_html: DebugHtmlOption = None,
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
) -> None:
    """Convert MkDocs documents into LaTeX artefacts without invoking latexmk."""

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

    document_paths, bibliography_files = split_document_inputs(document_paths, bibliography or [])
    if not document_paths:
        raise typer.BadParameter("Provide a Markdown (.md) or HTML (.html) source document.")

    try:
        _, slot_assignments = organise_slot_overrides(slots, document_paths)
    except (typer.BadParameter, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    assignment_rows: list[dict[str, object]] = []
    for doc_path, entries in slot_assignments.items():
        for entry in entries:
            assignment_rows.append(
                {
                    "document": _format_path_for_event(doc_path),
                    "slot": entry.slot,
                    "selector": entry.selector,
                    "include_document": entry.include_document,
                }
            )
    if assignment_rows:
        state.record_event("slot_assignments", {"entries": assignment_rows})

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

    template_identifier = template
    template_selected = bool(template_identifier)

    output_mode, output_target = determine_output_target(template_selected, document_paths, output)
    output_path = output_target.resolve() if output_target is not None else None

    callbacks = build_callbacks(
        emit_warning=lambda message, exception=None: emit_warning(message, exception=exception),
        emit_error=lambda message, exception=None: emit_error(message, exception=exception),
        debug_enabled=debug_enabled(),
        record_event=state.record_event,
    )

    settings = build_render_settings(
        parser=parser,
        disable_fallback_converters=disable_fallback_converters,
        copy_assets=copy_assets,
        manifest=manifest,
        persist_debug_html=bool(debug_snapshot),
        language=language,
        legacy_latex_accents=legacy_latex_accents,
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
        prepared = prepare_documents(
            document_paths,
            selector=selector,
            full_document=full_document,
            heading_level=heading_level,
            base_level=base_level,
            drop_title_all=False,
            drop_title_first_document=drop_title,
            numbered=numbered,
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

    apply_slot_assignments(prepared.document_map, slot_assignments)

    if not template_selected:
        render_target = output_path if output_mode == "directory" else None
        outcome = execute_conversion(
            prepared.documents,
            settings=settings,
            callbacks=callbacks,
            bibliography_files=bibliography_files,
            template=None,
            render_dir=render_target,
        )
        bundle = outcome.bundle
        if bundle is None:  # pragma: no cover - defensive
            raise RuntimeError("Conversion bundle missing from service outcome.")

        if output_mode == "stdout":
            typer.echo(bundle.combined_output())
            _flush_diagnostics()
            return

        if output_mode == "file":
            if output_path is None:
                raise typer.BadParameter("Output path is required when writing to a file.")
            try:
                write_output_file(output_path, bundle.combined_output())
            except OSError as exc:
                emit_error(str(exc), exception=exc)
                raise typer.Exit(code=1) from exc
            present_conversion_summary(
                state=state,
                output_mode=output_mode,
                bundle=bundle,
                output_path=output_path,
                render_result=None,
            )
            _flush_diagnostics()
            return

        if output_mode == "directory":
            present_conversion_summary(
                state=state,
                output_mode=output_mode,
                bundle=bundle,
                output_path=output_path,
                render_result=None,
            )
            _flush_diagnostics()
            return

        raise RuntimeError(f"Unsupported output mode '{output_mode}'.")

    render_dir = (output_path or Path("build")).resolve()
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

    present_conversion_summary(
        state=state,
        output_mode="template",
        bundle=None,
        output_path=render_dir,
        render_result=render_result,
    )
    _flush_diagnostics()
