"""Implementation of the `texsmith convert` command."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import typer

from ...context import DocumentState
from ...conversion import (
    ConversionCallbacks,
    ConversionError,
    InputKind,
    TemplateRuntime,
    UnsupportedInputError,
    convert_document,
    load_template_runtime,
)
from ...markdown import resolve_markdown_extensions
from ...templates import TemplateError, copy_template_assets
from ..state import debug_enabled, emit_error, emit_warning
from ..utils import (
    SlotAssignment,
    build_unique_stem_map,
    classify_input_source,
    determine_output_target,
    organise_slot_overrides,
    prepare_document_context,
    resolve_option,
    split_document_inputs,
    write_output_file,
)


def convert(
    inputs: list[Path] = typer.Argument(  # type: ignore[assignment]
        ...,
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
    input_path: Path | None = typer.Option(
        None,
        "--input-path",
        help="Internal helper used for programmatic invocation.",
        hidden=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        "--output-dir",
        help=("Output file or directory. Defaults to stdout unless a template is used."),
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
        help="Toggle copying of remote assets to the output directory.",
    ),
    manifest: bool = typer.Option(
        False,
        "--manifest/--no-manifest",
        help="Generate a manifest.json file alongside the LaTeX output.",
    ),
    template: str | None = typer.Option(
        None,
        "--template",
        "-t",
        help="Wrap the generated LaTeX using the selected template.",
    ),
    debug_html: bool | None = typer.Option(
        None,
        "--debug-html/--no-debug-html",
        help="Persist intermediate HTML snapshots.",
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
            "Inject a document or section into a template slot. "
            "Use 'slot:label' for single documents or 'slot:file[:section]' "
            "when multiple inputs are provided."
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
    """Convert MkDocs documents into LaTeX artefacts without invoking latexmk."""
    resolved_bibliography_option = list(resolve_option(bibliography))
    resolved_inputs = list(resolve_option(inputs))

    if input_path is not None:
        if resolved_inputs:
            raise typer.BadParameter("Provide either positional inputs or --input-path, not both.")
        resolved_inputs = [input_path]

    documents, bibliography_files = split_document_inputs(
        resolved_inputs,
        resolved_bibliography_option,
    )
    if not documents:
        raise typer.BadParameter("Provide a Markdown (.md) or HTML (.html) source document.")

    try:
        cli_slot_overrides, cli_slot_assignments = organise_slot_overrides(
            resolve_option(slots),
            documents,
        )
    except typer.BadParameter:
        raise
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    resolved_markdown_extensions = resolve_markdown_extensions(
        resolve_option(markdown_extensions),
        resolve_option(disable_markdown_extensions),
    )

    debug_snapshot = resolve_option(debug_html)
    if debug_snapshot is None:
        debug_snapshot = debug_enabled()

    template_name = resolve_option(template)
    output_option = resolve_option(output)
    template_selected = bool(template_name)

    template_runtime: TemplateRuntime | None = None
    if template_selected:
        try:
            template_runtime = load_template_runtime(template_name)
        except TemplateError as exc:  # pragma: no cover - template errors handled upstream
            emit_error(str(exc), exception=exc)
            raise typer.Exit(code=1) from exc

    output_mode, output_target = determine_output_target(
        template_selected,
        documents,
        output_option,
    )
    output_path = output_target.resolve() if output_target is not None else None

    resolved_selector = resolve_option(selector)
    resolved_full_document = resolve_option(full_document)
    resolved_base_level = resolve_option(base_level)
    resolved_heading_level = resolve_option(heading_level)
    resolved_drop_title = bool(resolve_option(drop_title))
    resolved_numbered = resolve_option(numbered)
    resolved_parser = resolve_option(parser)
    resolved_disable_fallback = resolve_option(disable_fallback_converters)
    resolved_copy_assets = resolve_option(copy_assets)
    resolved_manifest = resolve_option(manifest)
    resolved_language = resolve_option(language)

    callbacks = ConversionCallbacks(
        emit_warning=lambda message, exception=None: emit_warning(message, exception=exception),
        emit_error=lambda message, exception=None: emit_error(message, exception=exception),
        debug_enabled=debug_enabled(),
    )

    try:
        document_formats: dict[Path, InputKind] = {
            path: classify_input_source(path) for path in documents
        }
    except UnsupportedInputError as exc:
        if callbacks.emit_error is not None:
            callbacks.emit_error(str(exc), exc)
        else:
            emit_error(str(exc), exception=exc)
        raise ConversionError(str(exc)) from exc

    documents_count = len(documents)

    try:
        if documents_count == 1 and not template_selected:
            _convert_single_without_template(
                document_path=documents[0],
                output_mode=output_mode,
                output_path=output_path,
                selector=resolved_selector,
                full_document=resolved_full_document,
                base_level=resolved_base_level,
                heading_level=resolved_heading_level,
                drop_title=resolved_drop_title,
                numbered=resolved_numbered,
                parser=resolved_parser,
                disable_fallback_converters=resolved_disable_fallback,
                copy_assets=resolved_copy_assets,
                manifest=resolved_manifest,
                language=resolved_language,
                debug_snapshot=bool(debug_snapshot),
                slot_overrides=cli_slot_overrides.get(documents[0]),
                markdown_extensions=resolved_markdown_extensions,
                bibliography_files=bibliography_files,
                callbacks=callbacks,
                input_format=document_formats[documents[0]],
            )
            return

        if documents_count == 1 and template_selected:
            _convert_single_with_template(
                document_path=documents[0],
                output_dir=(output_path or Path("build")).resolve(),
                selector=resolved_selector,
                full_document=resolved_full_document,
                base_level=resolved_base_level,
                heading_level=resolved_heading_level,
                drop_title=resolved_drop_title,
                numbered=resolved_numbered,
                parser=resolved_parser,
                disable_fallback_converters=resolved_disable_fallback,
                copy_assets=resolved_copy_assets,
                manifest=resolved_manifest,
                language=resolved_language,
                debug_snapshot=bool(debug_snapshot),
                slot_overrides=cli_slot_overrides.get(documents[0]),
                markdown_extensions=resolved_markdown_extensions,
                bibliography_files=bibliography_files,
                template_name=template_name,
                template_runtime=template_runtime,
                callbacks=callbacks,
                input_format=document_formats[documents[0]],
            )
            return

        if not template_selected:
            _convert_multiple_without_template(
                documents=documents,
                output_mode=output_mode,
                output_path=output_path,
                selector=resolved_selector,
                full_document=resolved_full_document,
                base_level=resolved_base_level,
                heading_level=resolved_heading_level,
                drop_title=resolved_drop_title,
                numbered=resolved_numbered,
                parser=resolved_parser,
                disable_fallback_converters=resolved_disable_fallback,
                copy_assets=resolved_copy_assets,
                manifest=resolved_manifest,
                language=resolved_language,
                debug_snapshot=bool(debug_snapshot),
                slot_overrides=cli_slot_overrides,
                markdown_extensions=resolved_markdown_extensions,
                bibliography_files=bibliography_files,
                callbacks=callbacks,
                document_formats=document_formats,
            )
            return

        _convert_multiple_with_template(
            documents=documents,
            output_dir=(output_path or Path("build")).resolve(),
            selector=resolved_selector,
            full_document=resolved_full_document,
            base_level=resolved_base_level,
            heading_level=resolved_heading_level,
            drop_title=resolved_drop_title,
            numbered=resolved_numbered,
            parser=resolved_parser,
            disable_fallback_converters=resolved_disable_fallback,
            copy_assets=resolved_copy_assets,
            manifest=resolved_manifest,
            language=resolved_language,
            debug_snapshot=bool(debug_snapshot),
            slot_overrides=cli_slot_overrides,
            slot_assignments=cli_slot_assignments,
            markdown_extensions=resolved_markdown_extensions,
            bibliography_files=bibliography_files,
            template_name=template_name,
            template_runtime=template_runtime,
            callbacks=callbacks,
            document_formats=document_formats,
        )
    except ConversionError as exc:
        raise typer.Exit(code=1) from exc


def _convert_single_without_template(
    *,
    document_path: Path,
    output_mode: str,
    output_path: Path | None,
    selector: str,
    full_document: bool,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
    parser: str | None,
    disable_fallback_converters: bool,
    copy_assets: bool,
    manifest: bool,
    language: str | None,
    debug_snapshot: bool,
    slot_overrides: dict[str, str] | None,
    markdown_extensions: list[str],
    bibliography_files: list[Path],
    callbacks: ConversionCallbacks,
    input_format: InputKind,
) -> None:
    if output_mode == "directory" and output_path is not None:
        conversion_output_dir = output_path
    elif output_mode == "file" and output_path is not None:
        conversion_output_dir = output_path.parent
    else:
        conversion_output_dir = Path("build")

    document_context = prepare_document_context(
        document_path=document_path,
        kind=input_format,
        selector=selector,
        full_document=full_document,
        base_level=base_level,
        heading_level=heading_level,
        drop_title=drop_title,
        numbered=numbered,
        markdown_extensions=markdown_extensions,
        callbacks=callbacks,
        emit_error_callback=emit_error,
    )

    result = convert_document(
        document=document_context,
        output_dir=conversion_output_dir,
        parser=parser,
        disable_fallback_converters=disable_fallback_converters,
        copy_assets=copy_assets,
        manifest=manifest,
        template=None,
        persist_debug_html=debug_snapshot,
        language=language,
        slot_overrides=slot_overrides,
        bibliography_files=bibliography_files,
        callbacks=callbacks,
    )

    if output_mode in {"stdout", "directory"}:
        typer.echo(result.latex_output)
        return

    if output_mode == "file" and output_path is not None:
        try:
            write_output_file(output_path, result.latex_output)
        except OSError as exc:
            emit_error(str(exc), exception=exc)
            raise typer.Exit(code=1) from exc
        typer.secho(
            f"LaTeX document written to {output_path}",
            fg=typer.colors.GREEN,
        )


def _convert_single_with_template(
    *,
    document_path: Path,
    output_dir: Path,
    selector: str,
    full_document: bool,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
    parser: str | None,
    disable_fallback_converters: bool,
    copy_assets: bool,
    manifest: bool,
    language: str | None,
    debug_snapshot: bool,
    slot_overrides: dict[str, str] | None,
    markdown_extensions: list[str],
    bibliography_files: list[Path],
    template_name: str | None,
    template_runtime: TemplateRuntime | None,
    callbacks: ConversionCallbacks,
    input_format: InputKind,
) -> None:
    document_context = prepare_document_context(
        document_path=document_path,
        kind=input_format,
        selector=selector,
        full_document=full_document,
        base_level=base_level,
        heading_level=heading_level,
        drop_title=drop_title,
        numbered=numbered,
        markdown_extensions=markdown_extensions,
        callbacks=callbacks,
        emit_error_callback=emit_error,
    )

    result = convert_document(
        document=document_context,
        output_dir=output_dir,
        parser=parser,
        disable_fallback_converters=disable_fallback_converters,
        copy_assets=copy_assets,
        manifest=manifest,
        template=template_name,
        persist_debug_html=debug_snapshot,
        language=language,
        slot_overrides=slot_overrides,
        bibliography_files=bibliography_files,
        template_runtime=template_runtime,
        callbacks=callbacks,
    )

    if result.tex_path is not None:
        typer.secho(
            f"LaTeX document written to {result.tex_path}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.echo(result.latex_output)


def _convert_multiple_without_template(
    *,
    documents: list[Path],
    output_mode: str,
    output_path: Path | None,
    selector: str,
    full_document: bool,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
    parser: str | None,
    disable_fallback_converters: bool,
    copy_assets: bool,
    manifest: bool,
    language: str | None,
    debug_snapshot: bool,
    slot_overrides: dict[Path, dict[str, str]],
    markdown_extensions: list[str],
    bibliography_files: list[Path],
    callbacks: ConversionCallbacks,
    document_formats: Mapping[Path, InputKind],
) -> None:
    pieces: list[str] = []
    unique_stems = build_unique_stem_map(documents)

    for index, document_path in enumerate(documents):
        if output_mode == "directory" and output_path is not None:
            conversion_output_dir = output_path
        elif output_mode == "file" and output_path is not None:
            conversion_output_dir = output_path.parent
        else:
            conversion_output_dir = Path("build")

        document_context = prepare_document_context(
            document_path=document_path,
            kind=document_formats[document_path],
            selector=selector,
            full_document=full_document,
            base_level=base_level,
            heading_level=heading_level,
            drop_title=drop_title and index == 0,
            numbered=numbered,
            markdown_extensions=markdown_extensions,
            callbacks=callbacks,
            emit_error_callback=emit_error,
        )

        result = convert_document(
            document=document_context,
            output_dir=conversion_output_dir,
            parser=parser,
            disable_fallback_converters=disable_fallback_converters,
            copy_assets=copy_assets,
            manifest=manifest,
            template=None,
            persist_debug_html=debug_snapshot,
            language=language,
            slot_overrides=slot_overrides.get(document_path),
            bibliography_files=bibliography_files,
            callbacks=callbacks,
        )

        pieces.append(result.latex_output)

        if output_mode == "directory" and output_path is not None:
            target_file = output_path / f"{unique_stems[document_path]}.tex"
            try:
                write_output_file(target_file, result.latex_output)
            except OSError as exc:
                emit_error(str(exc), exception=exc)
                raise typer.Exit(code=1) from exc
            typer.secho(
                f"LaTeX document written to {target_file}",
                fg=typer.colors.GREEN,
            )

    joined_output = "\n\n".join(piece for piece in pieces if piece)

    if output_mode == "stdout":
        typer.echo(joined_output)
        return

    if output_mode == "file" and output_path is not None:
        try:
            write_output_file(output_path, joined_output)
        except OSError as exc:
            emit_error(str(exc), exception=exc)
            raise typer.Exit(code=1) from exc
        typer.secho(
            f"LaTeX document written to {output_path}",
            fg=typer.colors.GREEN,
        )


def _convert_multiple_with_template(
    *,
    documents: list[Path],
    output_dir: Path,
    selector: str,
    full_document: bool,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
    parser: str | None,
    disable_fallback_converters: bool,
    copy_assets: bool,
    manifest: bool,
    language: str | None,
    debug_snapshot: bool,
    slot_overrides: dict[Path, dict[str, str]],
    slot_assignments: dict[Path, list[SlotAssignment]],
    markdown_extensions: list[str],
    bibliography_files: list[Path],
    template_name: str | None,
    template_runtime: TemplateRuntime | None,
    callbacks: ConversionCallbacks,
    document_formats: Mapping[Path, InputKind],
) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        emit_error(f"Failed to prepare output directory '{output_dir}': {exc}", exception=exc)
        raise typer.Exit(code=1) from exc

    assert template_runtime is not None  # for type checkers
    unique_stems = build_unique_stem_map(documents)
    aggregated_slots: dict[str, list[str]] = {}
    shared_state = None
    bibliography_path = None
    template_overrides_master: dict[str, Any] | None = None

    default_slot_name = template_runtime.default_slot
    aggregated_slots.setdefault(default_slot_name, [])

    for index, document_path in enumerate(documents):
        document_context = prepare_document_context(
            document_path=document_path,
            kind=document_formats[document_path],
            selector=selector,
            full_document=full_document,
            base_level=base_level,
            heading_level=heading_level,
            drop_title=drop_title and index == 0,
            numbered=numbered,
            markdown_extensions=markdown_extensions,
            callbacks=callbacks,
            emit_error_callback=emit_error,
        )

        result = convert_document(
            document=document_context,
            output_dir=output_dir,
            parser=parser,
            disable_fallback_converters=disable_fallback_converters,
            copy_assets=copy_assets,
            manifest=manifest,
            template=template_name,
            persist_debug_html=debug_snapshot,
            language=language,
            slot_overrides=slot_overrides.get(document_path),
            bibliography_files=bibliography_files,
            state=shared_state,
            template_runtime=template_runtime,
            wrap_document=False,
            callbacks=callbacks,
        )

        shared_state = result.document_state
        bibliography_path = result.bibliography_path or bibliography_path
        if template_overrides_master is None:
            template_overrides_master = dict(result.template_overrides)

        fragment_stem = unique_stems[document_path]
        fragment_path = output_dir / f"{fragment_stem}.tex"
        try:
            write_output_file(fragment_path, result.latex_output)
        except OSError as exc:
            emit_error(str(exc), exception=exc)
            raise typer.Exit(code=1) from exc
        typer.secho(
            f"LaTeX fragment written to {fragment_path}",
            fg=typer.colors.GREEN,
        )

        assignments = slot_assignments.get(document_path, [])
        full_slots = {assignment.slot for assignment in assignments if assignment.full_document}

        fragment_reference = fragment_path.stem
        if default_slot_name not in aggregated_slots:
            aggregated_slots[default_slot_name] = []
        if default_slot_name not in full_slots and result.latex_output.strip():
            aggregated_slots[default_slot_name].append(f"\\input{{{fragment_reference}}}")

        for slot_name in full_slots:
            aggregated_slots.setdefault(slot_name, []).append(f"\\input{{{fragment_reference}}}")

        for slot_name, fragment_content in result.slot_outputs.items():
            if not fragment_content:
                continue
            if slot_name == default_slot_name and slot_name not in full_slots:
                continue
            if slot_name in full_slots:
                continue
            aggregated_slots.setdefault(slot_name, []).append(fragment_content)

    if shared_state is None:
        shared_state = DocumentState()
    if template_overrides_master is None:
        template_overrides_master = {}

    aggregated_render = {
        slot: "\n\n".join(chunk for chunk in chunks if chunk)
        for slot, chunks in aggregated_slots.items()
    }

    main_slot_name = template_runtime.default_slot
    main_content = aggregated_render.get(main_slot_name, "")

    template_context = template_runtime.instance.prepare_context(
        main_content,
        overrides=template_overrides_master if template_overrides_master else None,
    )

    for slot_name, content in aggregated_render.items():
        if slot_name == main_slot_name:
            continue
        template_context[slot_name] = content

    template_context["index_entries"] = shared_state.has_index_entries
    template_context["acronyms"] = shared_state.acronyms.copy()
    template_context["citations"] = list(shared_state.citations)
    template_context["bibliography_entries"] = shared_state.bibliography
    if shared_state.citations and bibliography_path is not None:
        template_context["bibliography"] = bibliography_path.stem
        template_context["bibliography_resource"] = bibliography_path.name
        if not template_context.get("bibliography_style"):
            template_context["bibliography_style"] = "plain"

    final_output = template_runtime.instance.wrap_document(
        main_content,
        context=template_context,
    )

    try:
        copy_template_assets(
            template_runtime.instance,
            output_dir,
            context=template_context,
            overrides=template_overrides_master if template_overrides_master else None,
        )
    except TemplateError as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc

    main_basename = f"{unique_stems[documents[0]]}-collection"
    main_tex_path = output_dir / f"{main_basename}.tex"
    try:
        write_output_file(main_tex_path, final_output)
    except OSError as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"LaTeX document written to {main_tex_path}",
        fg=typer.colors.GREEN,
    )
