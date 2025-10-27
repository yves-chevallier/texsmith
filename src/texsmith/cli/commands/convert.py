"""Implementation of the `texsmith convert` command."""

from __future__ import annotations

from pathlib import Path

import typer

from ...api import convert_documents, get_template
from ...api.document import Document
from ...api.pipeline import RenderSettings
from ...conversion import (
    DOCUMENT_SELECTOR_SENTINEL,
    ConversionCallbacks,
    ConversionError,
    InputKind,
    UnsupportedInputError,
)
from ...markdown import resolve_markdown_extensions
from ...templates import TemplateError
from ..state import debug_enabled, emit_error, emit_warning
from ..utils import (
    classify_input_source,
    determine_output_target,
    organise_slot_overrides,
    resolve_option,
    split_document_inputs,
    write_output_file,
)


def convert(
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
    legacy_latex_accents: bool = typer.Option(
        False,
        "--legacy-latex-accents/--unicode-latex-accents",
        help=(
            "Escape accented characters and ligatures with legacy LaTeX macros instead of "
            "emitting Unicode glyphs (defaults to Unicode output)."
        ),
    ),
    slots: list[str] = typer.Option(
        [],
        "--slot",
        "-s",
        help=(
            "Inject a document or section into a template slot. "
            "Use 'slot:label' for single documents or 'slot:file[:selector]' "
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

    raw_inputs = resolve_option(inputs if inputs is not None else [])
    if raw_inputs is None:
        resolved_inputs: list[Path] = []
    elif isinstance(raw_inputs, Path):
        resolved_inputs = [raw_inputs]
    else:
        resolved_inputs = list(raw_inputs)

    if input_path is not None:
        if resolved_inputs:
            raise typer.BadParameter("Provide either positional inputs or --input-path, not both.")
        resolved_inputs = [input_path]

    document_paths, bibliography_files = split_document_inputs(
        resolved_inputs,
        resolved_bibliography_option,
    )
    if not document_paths:
        raise typer.BadParameter("Provide a Markdown (.md) or HTML (.html) source document.")

    try:
        _, slot_assignments = organise_slot_overrides(resolve_option(slots), document_paths)
    except (typer.BadParameter, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    resolved_markdown_extensions = resolve_markdown_extensions(
        resolve_option(markdown_extensions),
        resolve_option(disable_markdown_extensions),
    )

    debug_snapshot = resolve_option(debug_html)
    if debug_snapshot is None:
        debug_snapshot = debug_enabled()

    template_identifier = resolve_option(template)
    output_option = resolve_option(output)
    template_selected = bool(template_identifier)

    output_mode, output_target = determine_output_target(
        template_selected,
        document_paths,
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
    resolved_legacy_latex_accents = bool(resolve_option(legacy_latex_accents))

    callbacks = ConversionCallbacks(
        emit_warning=lambda message, exception=None: emit_warning(message, exception=exception),
        emit_error=lambda message, exception=None: emit_error(message, exception=exception),
        debug_enabled=debug_enabled(),
    )

    settings = RenderSettings(
        parser=resolved_parser,
        disable_fallback_converters=resolved_disable_fallback,
        copy_assets=resolved_copy_assets,
        manifest=resolved_manifest,
        persist_debug_html=bool(debug_snapshot),
        language=resolved_language,
        legacy_latex_accents=resolved_legacy_latex_accents,
    )

    documents: list[Document] = []
    path_to_document: dict[Path, Document] = {}

    for index, document_path in enumerate(document_paths):
        try:
            input_kind = classify_input_source(document_path)
        except UnsupportedInputError as exc:
            if callbacks.emit_error is not None:
                callbacks.emit_error(str(exc), exc)
            else:
                emit_error(str(exc), exception=exc)
            raise typer.Exit(code=1) from exc

        drop_current = resolved_drop_title and index == 0

        try:
            if input_kind is InputKind.MARKDOWN:
                document = Document.from_markdown(
                    document_path,
                    extensions=resolved_markdown_extensions,
                    heading=resolved_heading_level,
                    base_level=resolved_base_level,
                    drop_title=drop_current,
                    numbered=resolved_numbered,
                    callbacks=callbacks,
                )
            else:
                document = Document.from_html(
                    document_path,
                    selector=resolved_selector,
                    heading=resolved_heading_level,
                    base_level=resolved_base_level,
                    drop_title=drop_current,
                    numbered=resolved_numbered,
                    full_document=resolved_full_document,
                    callbacks=callbacks,
                )
        except ConversionError as exc:
            raise typer.Exit(code=1) from exc

        documents.append(document)
        path_to_document[document_path] = document

    for path, assignments in slot_assignments.items():
        document = path_to_document.get(path)
        if document is None:
            continue
        for assignment in assignments:
            selector = assignment.selector
            if selector and selector != DOCUMENT_SELECTOR_SENTINEL:
                document.assign_slot(
                    assignment.slot,
                    selector=selector,
                    include_document=assignment.full_document,
                )
            else:
                document.assign_slot(assignment.slot, include_document=True)

    if not template_selected:
        bundle = convert_documents(
            documents,
            output_dir=output_path if output_mode == "directory" else None,
            settings=settings,
            callbacks=callbacks,
            bibliography_files=bibliography_files,
        )

        if output_mode == "stdout":
            typer.echo(bundle.combined_output())
            return

        if output_mode == "file":
            if output_path is None:
                raise typer.BadParameter("Output path is required when writing to a file.")
            try:
                write_output_file(output_path, bundle.combined_output())
            except OSError as exc:
                emit_error(str(exc), exception=exc)
                raise typer.Exit(code=1) from exc
            typer.secho(
                f"LaTeX document written to {output_path}",
                fg=typer.colors.GREEN,
            )
            return

        if output_mode == "directory":
            for fragment in bundle.fragments:
                if fragment.output_path is not None:
                    typer.secho(
                        f"LaTeX document written to {fragment.output_path}",
                        fg=typer.colors.GREEN,
                    )
            return

        raise RuntimeError(f"Unsupported output mode '{output_mode}'.")

    try:
        session = get_template(
            template_identifier,
            settings=settings,
            callbacks=callbacks,
        )
    except TemplateError as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc

    if bibliography_files:
        session.add_bibliography(*bibliography_files)

    for document in documents:
        session.add_document(document)

    render_dir = (output_path or Path("build")).resolve()
    try:
        render_result = session.render(render_dir)
    except (TemplateError, ConversionError) as exc:
        emit_error(str(exc), exception=exc)
        raise typer.Exit(code=1) from exc

    for fragment_path in render_result.fragment_paths:
        typer.secho(
            f"LaTeX fragment written to {fragment_path}",
            fg=typer.colors.GREEN,
        )

    typer.secho(
        f"LaTeX document written to {render_result.main_tex_path}",
        fg=typer.colors.GREEN,
    )
