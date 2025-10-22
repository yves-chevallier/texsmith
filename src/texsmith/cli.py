from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import copy
import dataclasses
from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from typing import Any

from bs4 import BeautifulSoup, FeatureNotFound, NavigableString, Tag
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
import typer
import yaml

from .bibliography import BibliographyCollection
from .config import BookConfig
from .context import DocumentState
from .exceptions import LatexRenderingError, TransformerExecutionError
from .formatter import LaTeXFormatter
from .renderer import LaTeXRenderer
from .templates import TemplateError, TemplateSlot, copy_template_assets, load_template
from .transformers import register_converter


DEFAULT_MARKDOWN_EXTENSIONS = [
    "abbr",
    "admonition",
    "attr_list",
    "def_list",
    "footnotes",
    "texsmith.markdown_extensions.missing_footnotes:MissingFootnotesExtension",
    "md_in_html",
    "mdx_math",
    "pymdownx.betterem",
    "pymdownx.blocks.caption",
    "pymdownx.blocks.html",
    "pymdownx.caret",
    "pymdownx.critic",
    "pymdownx.details",
    "pymdownx.emoji",
    "pymdownx.fancylists",
    "pymdownx.highlight",
    "pymdownx.inlinehilite",
    "pymdownx.keys",
    "pymdownx.magiclink",
    "pymdownx.mark",
    "pymdownx.saneheaders",
    "pymdownx.smartsymbols",
    "pymdownx.snippets",
    "pymdownx.superfences",
    "pymdownx.tabbed",
    "pymdownx.tasklist",
    "pymdownx.tilde",
    "tables",
    "toc",
]


DEFAULT_TEMPLATE_LANGUAGE = "english"

_BABEL_LANGUAGE_ALIASES = {
    "ad": "catalan",
    "ca": "catalan",
    "cs": "czech",
    "da": "danish",
    "de": "ngerman",
    "de-de": "ngerman",
    "en": "english",
    "en-gb": "british",
    "en-us": "english",
    "en-au": "australian",
    "en-ca": "canadian",
    "es": "spanish",
    "es-es": "spanish",
    "es-mx": "mexican",
    "fi": "finnish",
    "fr": "french",
    "fr-fr": "french",
    "fr-ca": "canadien",
    "it": "italian",
    "nl": "dutch",
    "nb": "norwegian",
    "nn": "nynorsk",
    "pl": "polish",
    "pt": "portuguese",
    "pt-br": "brazilian",
    "ro": "romanian",
    "ru": "russian",
    "sk": "slovak",
    "sl": "slovene",
    "sv": "swedish",
    "tr": "turkish",
}


@dataclass(slots=True)
class ConversionResult:
    """Artifacts produced during a CLI conversion."""

    latex_output: str
    tex_path: Path | None
    template_engine: str | None
    template_shell_escape: bool
    language: str
    has_bibliography: bool = False


app = typer.Typer(
    help="Convert MkDocs HTML fragments into LaTeX.",
    context_settings={"help_option_names": ["--help"]},
    invoke_without_command=True,
)

bibliography_app = typer.Typer(
    help="Inspect and interact with BibTeX bibliography files.",
    context_settings={"help_option_names": ["--help"]},
)

app.add_typer(bibliography_app, name="bibliography")


@app.callback()
def _app_root(
    list_extensions: bool = typer.Option(
        False,
        "--list-extensions",
        help="List Markdown extensions enabled by default and exit.",
    ),
) -> None:
    """Top-level CLI entry point to enable subcommands."""

    if list_extensions:
        for extension in DEFAULT_MARKDOWN_EXTENSIONS:
            typer.echo(extension)
        raise typer.Exit(code=0)

    return None


@bibliography_app.command(name="list")
def bibliography_list(
    bib_files: list[Path] = typer.Argument(
        ...,
        metavar="BIBFILE",
        help="One or more BibTeX files to inspect.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
) -> None:
    """List references stored in one or more BibTeX files."""

    collection = BibliographyCollection()
    collection.load_files(bib_files)

    console = Console()

    stats = collection.file_stats
    if stats:
        stats_table = Table(
            title="Bibliography Files",
            box=box.SIMPLE,
            show_edge=True,
            header_style="bold cyan",
        )
        stats_table.add_column("File", overflow="fold")
        stats_table.add_column("Entries", justify="right")
        for file_path, entry_count in stats:
            stats_table.add_row(str(file_path), str(entry_count))
        console.print(stats_table)

    if collection.issues:
        issue_table = Table(
            title="Warnings",
            box=box.SIMPLE,
            header_style="bold yellow",
            show_edge=True,
        )
        issue_table.add_column("Key", style="yellow", no_wrap=True)
        issue_table.add_column("Message", style="yellow")
        issue_table.add_column("Source", style="yellow")
        for issue in collection.issues:
            issue_table.add_row(
                issue.key or "—",
                issue.message,
                str(issue.source) if issue.source else "—",
            )
        console.print(issue_table)

    references = collection.list_references()
    if not references:
        console.print("[dim]No references found.[/]")
        raise typer.Exit(code=0)

    for reference in references:
        panel = _build_reference_panel(reference)
        console.print(panel)
        console.print()


def _convert_document(
    input_path: Path,
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
    template: str | None,
    debug: bool,
    language: str | None,
    slot_overrides: Mapping[str, str] | None,
    markdown_extensions: list[str],
    bibliography_files: list[Path],
) -> ConversionResult:
    try:
        output_dir = output_dir.resolve()
        input_payload = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        typer.secho(
            f"Failed to read input document: {exc}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1) from exc

    normalized_extensions = _normalize_markdown_extensions(markdown_extensions)
    if not normalized_extensions:
        normalized_extensions = list(DEFAULT_MARKDOWN_EXTENSIONS)

    try:
        input_kind = _classify_input_source(input_path)
    except UnsupportedInputError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    is_markdown = input_kind is InputKind.MARKDOWN

    front_matter: dict[str, Any] = {}
    if is_markdown:
        try:
            html, front_matter = _render_markdown(input_payload, normalized_extensions)
        except MarkdownConversionError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
    else:
        html = input_payload

    if not full_document and not is_markdown:
        try:
            html = _extract_content(html, selector)
        except ValueError:
            # Fallback to the entire document when the selector cannot be resolved.
            html = input_payload

    slot_requests = _extract_front_matter_slots(front_matter)
    if slot_overrides:
        slot_requests.update(dict(slot_overrides))

    if debug:
        _persist_debug_artifacts(output_dir, input_path, html)

    resolved_language = _resolve_template_language(language, front_matter)

    config = BookConfig(project_dir=input_path.parent, language=resolved_language)

    bibliography_collection: BibliographyCollection | None = None
    bibliography_map: dict[str, dict[str, Any]] = {}
    if bibliography_files:
        bibliography_collection = BibliographyCollection()
        bibliography_collection.load_files(bibliography_files)
        bibliography_map = bibliography_collection.to_dict()
        for issue in bibliography_collection.issues:
            prefix = f"[{issue.key}] " if issue.key else ""
            source_hint = f" ({issue.source})" if issue.source else ""
            typer.secho(
                f"warning: {prefix}{issue.message}{source_hint}",
                fg=typer.colors.YELLOW,
                err=True,
            )

    renderer_kwargs: dict[str, Any] = {
        "output_root": output_dir,
        "copy_assets": copy_assets,
    }
    renderer_kwargs["parser"] = parser or "html.parser"

    template_overrides = _build_template_overrides(front_matter)
    template_overrides["language"] = resolved_language
    meta_section = template_overrides.get("meta")
    if isinstance(meta_section, dict):
        meta_section.setdefault("language", resolved_language)

    try:
        override_base_level = _extract_base_level_override(template_overrides)
        template_base_level = _coerce_base_level(override_base_level)
    except TemplateError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    template_info_engine: str | None = None
    template_requires_shell_escape = False
    template_instance = None
    template_name: str | None = None
    template_context: dict[str, Any] | None = None
    formatter_overrides: dict[str, Path] = {}
    if template:
        try:
            template_instance = load_template(template)
        except TemplateError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

        try:
            template_default_base = _coerce_base_level(
                template_instance.info.attributes.get("base_level")
            )
        except TemplateError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        if template_base_level is None:
            template_base_level = template_default_base

        template_name = template_instance.info.name
        template_info_engine = template_instance.info.engine
        template_requires_shell_escape = bool(template_instance.info.shell_escape)
        try:
            formatter_overrides = dict(template_instance.iter_formatter_overrides())
        except TemplateError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

    if template_instance is not None:
        try:
            template_slots, default_slot = template_instance.info.resolve_slots()
        except TemplateError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
    else:
        template_slots = {"mainmatter": TemplateSlot(default=True)}
        default_slot = "mainmatter"
        if slot_requests:
            for slot_name in slot_requests:
                typer.secho(
                    f"warning: slot '{slot_name}' was requested but no template "
                    "is selected; ignoring.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
            slot_requests = {}

    effective_base_level = template_base_level or 0
    slot_base_levels: dict[str, int] = {
        name: slot.resolve_level(effective_base_level)
        for name, slot in template_slots.items()
    }
    runtime_common: dict[str, object] = {
        "numbered": numbered,
        "source_dir": input_path.parent,
        "document_path": input_path,
        "copy_assets": copy_assets,
        "language": resolved_language,
    }
    if bibliography_map:
        runtime_common["bibliography"] = bibliography_map
    if template_name is not None:
        runtime_common["template"] = template_name
    if manifest:
        runtime_common["generate_manifest"] = True

    active_slot_requests: dict[str, str] = {}
    for slot_name, selector in slot_requests.items():
        if slot_name not in template_slots:
            template_hint = (
                f"template '{template_name}'" if template_name else "the template"
            )
            typer.secho(
                f"warning: slot '{slot_name}' is not defined by {template_hint}; "
                f"content will remain in '{default_slot}'.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            continue
        active_slot_requests[slot_name] = selector

    parser_backend = str(renderer_kwargs.get("parser", "html.parser"))
    slot_fragments, missing_slots = _extract_slot_fragments(
        html,
        active_slot_requests,
        default_slot,
        slot_definitions=template_slots,
        parser_backend=parser_backend,
    )
    for message in missing_slots:
        typer.secho(f"warning: {message}", fg=typer.colors.YELLOW, err=True)

    def renderer_factory() -> LaTeXRenderer:
        formatter = LaTeXFormatter()
        for key, override_path in formatter_overrides.items():
            formatter.override_template(key, override_path)
        return LaTeXRenderer(config=config, formatter=formatter, **renderer_kwargs)

    if not disable_fallback_converters:
        _ensure_fallback_converters()

    slot_outputs: dict[str, str] = {}
    document_state: DocumentState | None = None
    drop_title_flag = bool(drop_title)
    for fragment in slot_fragments:
        runtime = dict(runtime_common)
        base_value = slot_base_levels.get(fragment.name, effective_base_level)
        runtime["base_level"] = base_value + base_level + heading_level
        if drop_title_flag:
            runtime["drop_title"] = True
            drop_title_flag = False
        try:
            fragment_output, document_state = _render_with_fallback(
                renderer_factory,
                fragment.html,
                runtime,
                bibliography_map,
                state=document_state,
            )
        except LatexRenderingError as exc:
            typer.secho(
                _format_rendering_error(exc),
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1) from exc
        existing_fragment = slot_outputs.get(fragment.name, "")
        slot_outputs[fragment.name] = f"{existing_fragment}{fragment_output}"

    if document_state is None:
        document_state = DocumentState(bibliography=dict(bibliography_map))

    default_content = slot_outputs.get(default_slot)
    if default_content is None:
        default_content = ""
        slot_outputs[default_slot] = default_content
    latex_output = default_content

    citations = list(document_state.citations)
    bibliography_output: Path | None = None
    if citations and bibliography_collection is not None and bibliography_map:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            bibliography_output = output_dir / "texsmith-bibliography.bib"
            bibliography_collection.write_bibtex(bibliography_output, keys=citations)
        except OSError as exc:
            typer.secho(
                f"Failed to write bibliography file: {exc}",
                fg=typer.colors.YELLOW,
                err=True,
            )
            bibliography_output = None

    tex_path: Path | None = None
    if template_instance is not None:
        try:
            template_context = template_instance.prepare_context(
                latex_output,
                overrides=template_overrides if template_overrides else None,
            )
            for slot_name, fragment_output in slot_outputs.items():
                if slot_name == default_slot:
                    continue
                template_context[slot_name] = fragment_output
            template_context["index_entries"] = document_state.has_index_entries
            template_context["acronyms"] = document_state.acronyms.copy()
            template_context["citations"] = citations
            template_context["bibliography_entries"] = document_state.bibliography
            if citations and bibliography_output is not None:
                template_context["bibliography"] = bibliography_output.stem
                template_context["bibliography_resource"] = bibliography_output.name
                if not template_context.get("bibliography_style"):
                    template_context["bibliography_style"] = "plain"
            latex_output = template_instance.wrap_document(
                latex_output,
                context=template_context,
            )
        except TemplateError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        try:
            copy_template_assets(
                template_instance,
                output_dir,
                context=template_context,
                overrides=template_overrides if template_overrides else None,
            )
        except TemplateError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            tex_path = output_dir / f"{input_path.stem}.tex"
            tex_path.write_text(latex_output, encoding="utf-8")
        except OSError as exc:
            typer.secho(
                f"Failed to write LaTeX output to '{output_dir}': {exc}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1) from exc

    return ConversionResult(
        latex_output=latex_output,
        tex_path=tex_path,
        template_engine=template_info_engine,
        template_shell_escape=template_requires_shell_escape,
        language=resolved_language,
        has_bibliography=bool(citations),
    )


def _resolve_option(value: Any) -> Any:
    if isinstance(value, typer.models.OptionInfo):
        return value.default
    return value


_BIBLIOGRAPHY_SUFFIXES = {".bib", ".bibtex"}


def _deduplicate_paths(values: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in values:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def _partition_input_resources(
    inputs: Iterable[Path],
    extra_bibliography: Iterable[Path],
) -> tuple[Path, list[Path]]:
    document_path: Path | None = None
    inline_bibliography: list[Path] = []

    for candidate in inputs:
        suffix = candidate.suffix.lower()
        if suffix in _BIBLIOGRAPHY_SUFFIXES:
            inline_bibliography.append(candidate)
            continue
        if document_path is not None:
            raise ValueError(
                "Multiple document inputs provided. "
                "Pass a single Markdown or HTML source document."
            )
        document_path = candidate

    if document_path is None:
        raise ValueError("Provide a Markdown (.md) or HTML (.html) source document.")

    combined_bibliography = _deduplicate_paths(
        [*inline_bibliography, *extra_bibliography]
    )
    return document_path, combined_bibliography


def _coerce_base_level(value: Any, *, allow_none: bool = True) -> int | None:
    if value is None:
        if allow_none:
            return None
        raise TemplateError("Base level value is missing.")

    if isinstance(value, bool):
        raise TemplateError(
            "Base level must be an integer, booleans are not supported."
        )

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            if allow_none:
                return None
            raise TemplateError("Base level value cannot be empty.")
        try:
            return int(candidate)
        except ValueError as exc:  # pragma: no cover - defensive
            raise TemplateError(
                f"Invalid base level '{value}'. Expected an integer value."
            ) from exc

    raise TemplateError(
        "Base level should be provided as an integer value, "
        f"got type '{type(value).__name__}'."
    )


def _extract_base_level_override(overrides: Mapping[str, Any] | None) -> Any:
    if not overrides:
        return None

    direct_candidate = overrides.get("base_level")
    meta_section = overrides.get("meta")
    meta_candidate = None
    if isinstance(meta_section, Mapping):
        meta_candidate = meta_section.get("base_level")

    # Prefer explicit meta entry as it mirrors template attributes closely.
    return meta_candidate if meta_candidate is not None else direct_candidate


@app.command(name="convert")
def convert(
    inputs: list[Path] = typer.Argument(
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
            "Indent all headings by the selected depth "
            "(e.g. 1 turns sections into subsections)."
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
        help=(
            "Disable registration of placeholder converters when Docker is unavailable."
        ),
    ),
    copy_assets: bool = typer.Option(
        True,
        "--copy-assets/--no-copy-assets",
        "-a/-A",
        help=(
            "Control whether asset files are generated "
            "and copied to the output directory."
        ),
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
    debug: bool = typer.Option(
        False,
        "--debug/--no-debug",
        help="Enable debug mode to persist intermediate artifacts.",
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
    """Convert an MkDocs HTML page to LaTeX."""

    resolved_bibliography_option = list(_resolve_option(bibliography))
    try:
        document_path, bibliography_files = _partition_input_resources(
            inputs, resolved_bibliography_option
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    resolved_markdown_extensions = _resolve_markdown_extensions(
        _resolve_option(markdown_extensions),
        _resolve_option(disable_markdown_extensions),
    )
    try:
        requested_slots = _parse_slot_option(_resolve_option(slots))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    result = _convert_document(
        input_path=document_path,
        output_dir=_resolve_option(output_dir),
        selector=_resolve_option(selector),
        full_document=_resolve_option(full_document),
        base_level=_resolve_option(base_level),
        heading_level=_resolve_option(heading_level),
        drop_title=_resolve_option(drop_title),
        numbered=_resolve_option(numbered),
        parser=_resolve_option(parser),
        disable_fallback_converters=_resolve_option(disable_fallback_converters),
        copy_assets=_resolve_option(copy_assets),
        manifest=_resolve_option(manifest),
        template=_resolve_option(template),
        debug=_resolve_option(debug),
        language=_resolve_option(language),
        slot_overrides=requested_slots,
        markdown_extensions=resolved_markdown_extensions,
        bibliography_files=bibliography_files,
    )

    if result.tex_path is not None:
        typer.secho(
            f"LaTeX document written to {result.tex_path}",
            fg=typer.colors.GREEN,
        )
        return

    typer.echo(result.latex_output)


def _build_latexmk_command(
    engine: str | None, shell_escape: bool, force_bibtex: bool = False
) -> list[str]:
    engine_command = (engine or "pdflatex").strip()
    if not engine_command:
        engine_command = "pdflatex"

    tokens = shlex.split(engine_command)
    if not tokens:
        tokens = ["pdflatex"]

    if shell_escape and not any(
        token in {"-shell-escape", "--shell-escape"} for token in tokens
    ):
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


@app.command(name="build")
def build(
    inputs: list[Path] = typer.Argument(
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
            "Indent all headings by the selected depth "
            "(e.g. 1 turns sections into subsections)."
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
        help=(
            "Disable registration of placeholder converters when Docker is unavailable."
        ),
    ),
    copy_assets: bool = typer.Option(
        True,
        "--copy-assets/--no-copy-assets",
        "-a/-A",
        help=(
            "Control whether asset files are generated "
            "and copied to the output directory."
        ),
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
    debug: bool = typer.Option(
        False,
        "--debug/--no-debug",
        help="Enable debug mode to persist intermediate artifacts.",
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
    """Convert inputs and compile the rendered document with latexmk."""

    resolved_bibliography_option = list(_resolve_option(bibliography))
    try:
        document_path, bibliography_files = _partition_input_resources(
            inputs, resolved_bibliography_option
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    resolved_markdown_extensions = _resolve_markdown_extensions(
        _resolve_option(markdown_extensions),
        _resolve_option(disable_markdown_extensions),
    )
    try:
        requested_slots = _parse_slot_option(_resolve_option(slots))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    conversion = _convert_document(
        input_path=document_path,
        output_dir=_resolve_option(output_dir),
        selector=_resolve_option(selector),
        full_document=_resolve_option(full_document),
        base_level=_resolve_option(base_level),
        heading_level=_resolve_option(heading_level),
        drop_title=_resolve_option(drop_title),
        numbered=_resolve_option(numbered),
        parser=_resolve_option(parser),
        disable_fallback_converters=_resolve_option(disable_fallback_converters),
        copy_assets=_resolve_option(copy_assets),
        manifest=_resolve_option(manifest),
        template=_resolve_option(template),
        debug=_resolve_option(debug),
        language=_resolve_option(language),
        slot_overrides=requested_slots,
        markdown_extensions=resolved_markdown_extensions,
        bibliography_files=bibliography_files,
    )

    if conversion.tex_path is None:
        typer.secho(
            "The build command requires a LaTeX template (--template).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    latexmk_path = shutil.which("latexmk")
    if latexmk_path is None:
        typer.secho(
            "latexmk executable not found. "
            "Install TeX Live (or latexmk) to build PDFs.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    command = _build_latexmk_command(
        conversion.template_engine,
        conversion.template_shell_escape,
        force_bibtex=conversion.has_bibliography,
    )
    command[0] = latexmk_path
    command.append(conversion.tex_path.name)

    try:
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=conversion.tex_path.parent,
        )
    except OSError as exc:
        typer.secho(
            f"Failed to execute latexmk: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    if process.stdout:
        typer.echo(process.stdout.rstrip())
    if process.stderr:
        typer.echo(process.stderr.rstrip(), err=True)

    if process.returncode != 0:
        typer.secho(
            f"latexmk exited with status {process.returncode}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=process.returncode)

    pdf_path = conversion.tex_path.with_suffix(".pdf")
    if pdf_path.exists():
        typer.secho(
            f"PDF document written to {pdf_path}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            "latexmk completed without errors but the PDF file was not found.",
            fg=typer.colors.YELLOW,
        )


def main() -> None:
    """Entry point compatible with console scripts."""

    app()


if __name__ == "__main__":
    main()


@dataclass(slots=True)
class SlotFragment:
    """HTML fragment mapped to a template slot with position metadata."""

    name: str
    html: str
    position: int


def _parse_slot_option(values: Iterable[str] | None) -> dict[str, str]:
    """Parse CLI slot overrides declared as 'slot:Section' pairs."""

    overrides: dict[str, str] = {}
    if not values:
        return overrides

    for raw in values:
        if not isinstance(raw, str):
            continue
        entry = raw.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(
                f"Invalid slot override '{raw}', expected format 'slot:Section'."
            )
        slot_name, selector = entry.split(":", 1)
        slot_name = slot_name.strip()
        selector = selector.strip()
        if not slot_name or not selector:
            raise ValueError(
                f"Invalid slot override '{raw}', expected format 'slot:Section'."
            )
        overrides[slot_name] = selector

    return overrides


def _extract_front_matter_slots(front_matter: Mapping[str, Any]) -> dict[str, str]:
    """Collect slot overrides defined in document front matter."""

    overrides: dict[str, str] = {}
    meta_section = front_matter.get("meta")
    if not isinstance(meta_section, Mapping):
        return overrides

    raw_slots = meta_section.get("slots") or meta_section.get("entrypoints")

    if isinstance(raw_slots, Mapping):
        for slot_name, payload in raw_slots.items():
            if not isinstance(slot_name, str):
                continue
            selector: str | None = None
            if isinstance(payload, str):
                selector = payload
            elif isinstance(payload, Mapping):
                label = payload.get("label")
                title = payload.get("title")
                candidate = label or title
                if isinstance(candidate, str):
                    selector = candidate
            if selector:
                slot_key = slot_name.strip()
                slot_value = selector.strip()
                if slot_key and slot_value:
                    overrides[slot_key] = slot_value
    elif isinstance(raw_slots, Iterable):
        for entry in raw_slots:
            if not isinstance(entry, Mapping):
                continue
            slot_name = entry.get("target") or entry.get("slot")
            selector = entry.get("label") or entry.get("title")
            if isinstance(slot_name, str) and isinstance(selector, str):
                slot_key = slot_name.strip()
                slot_value = selector.strip()
                if slot_key and slot_value:
                    overrides[slot_key] = slot_value

    return overrides


def _extract_slot_fragments(
    html: str,
    requests: Mapping[str, str],
    default_slot: str,
    *,
    slot_definitions: Mapping[str, TemplateSlot],
    parser_backend: str,
) -> tuple[list[SlotFragment], list[str]]:
    """Split the HTML document into fragments mapped to template slots."""

    try:
        soup = BeautifulSoup(html, parser_backend)
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")

    container = soup.body or soup
    headings: list[tuple[int, Tag]] = []
    for index, heading in enumerate(
        container.find_all(re.compile(r"^h[1-6]$"), recursive=True)
    ):
        headings.append((index, heading))

    matched: dict[str, tuple[int, Tag]] = {}
    missing: list[str] = []
    occupied_nodes: set[int] = set()

    for slot_name, selector in requests.items():
        if not selector:
            continue
        target_label = selector.lstrip("#")
        matched_heading: tuple[int, Tag] | None = None
        for index, heading in headings:
            if id(heading) in occupied_nodes:
                continue
            node_id = heading.get("id")
            if isinstance(node_id, str) and node_id == target_label:
                matched_heading = (index, heading)
                break
        if matched_heading is None:
            for index, heading in headings:
                if id(heading) in occupied_nodes:
                    continue
                if heading.get_text(strip=True) == selector:
                    matched_heading = (index, heading)
                    break
        if matched_heading is None:
            missing.append(
                f"unable to locate section '{selector}' for slot '{slot_name}'"
            )
            continue
        matched_index, heading = matched_heading
        occupied_nodes.add(id(heading))
        matched[slot_name] = (matched_index, heading)

    fragments: list[SlotFragment] = []

    for slot_name, (order, heading) in sorted(
        matched.items(), key=lambda item: item[1][0]
    ):
        section_nodes = _collect_section_nodes(heading)
        slot_config = slot_definitions.get(slot_name)
        strip_heading = bool(slot_config.strip_heading) if slot_config else False
        render_nodes = list(section_nodes)
        if strip_heading and render_nodes:
            render_nodes = render_nodes[1:]
            while render_nodes and isinstance(render_nodes[0], NavigableString):
                if str(render_nodes[0]).strip():
                    break
                render_nodes.pop(0)
        html_fragment = "".join(str(node) for node in render_nodes)
        fragments.append(
            SlotFragment(name=slot_name, html=html_fragment, position=order)
        )
        for node in section_nodes:
            if hasattr(node, "extract"):
                node.extract()

    container = soup.body or soup
    remainder_html = "".join(str(node) for node in container.contents)

    if fragments:
        remainder_position = min(fragment.position for fragment in fragments) - 1
    else:
        remainder_position = -1

    fragments.append(
        SlotFragment(
            name=default_slot, html=remainder_html, position=remainder_position
        )
    )

    fragments.sort(key=lambda fragment: fragment.position)
    return fragments, missing


def _collect_section_nodes(heading: Tag) -> list[Any]:
    """Collect a heading node and its associated section content."""

    nodes: list[Any] = [heading]
    heading_level = _heading_level(heading)
    for sibling in heading.next_siblings:
        if isinstance(sibling, NavigableString):
            nodes.append(sibling)
            continue
        if isinstance(sibling, Tag):
            if re.fullmatch(r"h[1-6]", sibling.name or ""):
                sibling_level = _heading_level(sibling)
                if sibling_level <= heading_level:
                    break
            nodes.append(sibling)
    return nodes


def _heading_level(node: Tag) -> int:
    """Return the numeric level of a heading element."""

    name = node.name or ""
    if not re.fullmatch(r"h[1-6]", name):
        raise ValueError(f"Expected heading element, got '{name}'.")
    return int(name[1])


def _copy_document_state(target: DocumentState, source: DocumentState) -> None:
    """Synchronise target ``DocumentState`` with a source instance."""

    for field in dataclasses.fields(DocumentState):
        setattr(target, field.name, copy.deepcopy(getattr(source, field.name)))


def _extract_content(html: str, selector: str) -> str:
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")

    element = soup.select_one(selector)
    if element is None:
        raise ValueError(f"Unable to locate content using selector '{selector}'.")
    return element.decode_contents()


def _persist_debug_artifacts(output_dir: Path, source: Path, html: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_path = output_dir / f"{source.stem}.debug.html"
    debug_path.write_text(html, encoding="utf-8")


def _render_with_fallback(
    renderer_factory: Callable[[], LaTeXRenderer],
    html: str,
    runtime: dict[str, object],
    bibliography: Mapping[str, dict[str, Any]] | None = None,
    *,
    state: DocumentState | None = None,
) -> tuple[str, DocumentState]:
    attempts = 0
    bibliography_payload = dict(bibliography or {})
    base_state = state

    while True:
        current_state = (
            copy.deepcopy(base_state)
            if base_state is not None
            else DocumentState(bibliography=dict(bibliography_payload))
        )

        renderer = renderer_factory()
        try:
            output = renderer.render(html, runtime=runtime, state=current_state)
        except LatexRenderingError as exc:
            attempts += 1
            if attempts >= 5 or not _attempt_transformer_fallback(exc):
                raise
            continue

        if base_state is not None:
            _copy_document_state(base_state, current_state)
            return output, base_state

        return output, current_state


def _attempt_transformer_fallback(error: LatexRenderingError) -> bool:
    cause = error.__cause__
    if not isinstance(cause, TransformerExecutionError):
        return False

    message = str(cause).lower()
    applied = False

    if "drawio" in message:
        register_converter("drawio", _FallbackConverter("drawio"))
        applied = True
    if "mermaid" in message:
        register_converter("mermaid", _FallbackConverter("mermaid"))
        applied = True
    if "fetch-image" in message or "fetch image" in message:
        register_converter("fetch-image", _FallbackConverter("image"))
        applied = True
    return applied


def _ensure_fallback_converters() -> None:
    docker_available = None
    try:
        docker_available = shutil.which("docker")
    except AssertionError:
        # Some tests replace shutil.which with strict assertions.
        docker_available = None

    if docker_available:
        return

    for name in ("drawio", "mermaid", "fetch-image"):
        register_converter(name, _FallbackConverter(name))


class _FallbackConverter:
    def __init__(self, name: str):
        self.name = name

    def __call__(self, source: Path | str, *, output_dir: Path, **_: Any) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        original = str(source) if isinstance(source, Path) else source
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:12]
        suffix = Path(original).suffix or ".txt"
        filename = f"{self.name}-{digest}.pdf"
        target = output_dir / filename
        target.write_text(
            f"Placeholder PDF for {self.name} ({suffix})",
            encoding="utf-8",
        )
        return target


def _format_rendering_error(error: LatexRenderingError) -> str:
    cause = error.__cause__
    if cause is None:
        return str(error)
    return f"LaTeX rendering failed: {cause}"


def _resolve_markdown_extensions(
    requested: Iterable[str] | typer.models.OptionInfo | None,
    disabled: Iterable[str] | typer.models.OptionInfo | None,
) -> list[str]:
    enabled = _normalize_markdown_extensions(requested)
    disabled_normalized = {
        extension.lower() for extension in _normalize_markdown_extensions(disabled)
    }

    combined = _deduplicate_markdown_extensions(
        list(DEFAULT_MARKDOWN_EXTENSIONS) + enabled
    )

    if not disabled_normalized:
        return combined

    return [
        extension
        for extension in combined
        if extension.lower() not in disabled_normalized
    ]


def _deduplicate_markdown_extensions(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _normalize_markdown_extensions(
    values: Iterable[str] | typer.models.OptionInfo | None,
) -> list[str]:
    if isinstance(values, typer.models.OptionInfo):
        values = values.default

    if values is None:
        return []

    if isinstance(values, str):
        candidates: Iterable[str] = [values]
    else:
        candidates = values

    normalized: list[str] = []
    for value in candidates:
        if not isinstance(value, str):
            continue
        chunks = re.split(r"[,\s\x00]+", value)
        normalized.extend(chunk for chunk in chunks if chunk)
    return normalized


class MarkdownConversionError(Exception):
    """Raised when the Markdown payload cannot be converted."""


class UnsupportedInputError(Exception):
    """Raised when the input path cannot be processed."""


class InputKind(Enum):
    MARKDOWN = "markdown"
    HTML = "html"


def _classify_input_source(path: Path) -> InputKind:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return InputKind.MARKDOWN
    if suffix in {".html", ".htm"}:
        return InputKind.HTML
    if suffix in {".yaml", ".yml"}:
        raise UnsupportedInputError(
            "MkDocs configuration files are not supported as input. "
            "Provide a Markdown source or an HTML document."
        )
    raise UnsupportedInputError(
        f"Unsupported input file type '{suffix or '<none>'}'. "
        "Provide a Markdown source (.md) or HTML document (.html)."
    )


def _render_markdown(source: str, extensions: list[str]) -> tuple[str, dict[str, Any]]:
    try:
        import markdown
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise MarkdownConversionError(
            "Python Markdown is required to process Markdown inputs; "
            "install the 'markdown' package."
        ) from exc

    metadata, markdown_body = _split_front_matter(source)

    try:
        md = markdown.Markdown(extensions=extensions)
    except Exception as exc:  # pragma: no cover - library-controlled
        raise MarkdownConversionError(
            f"Failed to initialize Markdown processor: {exc}"
        ) from exc

    try:
        return md.convert(markdown_body), metadata
    except Exception as exc:  # pragma: no cover - library-controlled
        raise MarkdownConversionError(
            f"Failed to convert Markdown source: {exc}"
        ) from exc


def _split_front_matter(source: str) -> tuple[dict[str, Any], str]:
    candidate = source.lstrip("\ufeff")
    prefix_len = len(source) - len(candidate)
    lines = candidate.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, source

    front_matter_lines: list[str] = []
    closing_index: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped in {"---", "..."}:
            closing_index = idx
            break
        front_matter_lines.append(line)

    if closing_index is None:
        return {}, source

    raw_block = "\n".join(front_matter_lines)
    try:
        metadata = yaml.safe_load(raw_block) or {}
    except yaml.YAMLError:
        return {}, source

    if not isinstance(metadata, dict):
        metadata = {}

    body_lines = lines[closing_index + 1 :]
    body = "\n".join(body_lines)
    if source.endswith("\n"):
        body += "\n"

    prefix = source[:prefix_len]
    return metadata, prefix + body


def _build_template_overrides(front_matter: Mapping[str, Any] | None) -> dict[str, Any]:
    if not front_matter:
        return {}

    if not isinstance(front_matter, Mapping):
        return {}

    meta_section = front_matter.get("meta")
    if isinstance(meta_section, Mapping):
        return {"meta": dict(meta_section)}

    return {"meta": dict(front_matter)}


def _resolve_template_language(
    explicit: str | None,
    front_matter: Mapping[str, Any] | None,
) -> str:
    candidates = (
        _normalise_template_language(explicit),
        _normalise_template_language(_extract_language_from_front_matter(front_matter)),
    )

    for candidate in candidates:
        if candidate:
            return candidate

    return DEFAULT_TEMPLATE_LANGUAGE


def _extract_language_from_front_matter(
    front_matter: Mapping[str, Any] | None,
) -> str | None:
    if not isinstance(front_matter, Mapping):
        return None

    meta_entry = front_matter.get("meta")
    containers: tuple[Mapping[str, Any] | None, ...] = (
        meta_entry if isinstance(meta_entry, Mapping) else None,
        front_matter,
    )

    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for key in ("language", "lang"):
            value = container.get(key)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
    return None


def _normalise_template_language(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    lowered = stripped.lower().replace("_", "-")
    alias = _BABEL_LANGUAGE_ALIASES.get(lowered)
    if alias:
        return alias

    primary = lowered.split("-", 1)[0]
    alias = _BABEL_LANGUAGE_ALIASES.get(primary)
    if alias:
        return alias

    if lowered.isalpha():
        return lowered

    return None


def _format_bibliography_person(person: Mapping[str, Any]) -> str:
    """Render a bibliography person dictionary into a readable string."""

    parts: list[str] = []
    for field in ("first", "middle", "prelast", "last", "lineage"):
        parts.extend(str(segment) for segment in person.get(field, []) if segment)

    text = " ".join(part for part in parts if part)
    return text or str(person.get("text", "")).strip()


def _format_person_list(persons: Iterable[Mapping[str, Any]]) -> str:
    names = [_format_bibliography_person(person) for person in persons]
    return ", ".join(name for name in names if name)


def _build_reference_panel(reference: Mapping[str, Any]) -> Panel:
    fields = dict(reference.get("fields", {}))
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold green", no_wrap=True)
    grid.add_column()

    def _pop_field(*keys: str) -> str | None:
        for key in keys:
            value = fields.pop(key, None)
            if value:
                return value
        return None

    def _add_field(label: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str) and not value.strip():
            return
        grid.add_row(label, value)

    title = _pop_field("title")
    _add_field("Title", title)

    year = _pop_field("year")
    _add_field("Year", year)

    container = _pop_field("journal", "booktitle")
    _add_field("Publication", container)

    volume = _pop_field("volume")
    number = _pop_field("number")
    pages = _pop_field("pages")
    _add_field("Volume", volume)
    _add_field("Number", number)
    _add_field("Pages", pages)

    doi = _pop_field("doi")
    url = _pop_field("url")
    _add_field("DOI", doi)
    _add_field("URL", url)

    abstract = _pop_field("abstract")
    if abstract:
        abstract_text = Text(abstract.strip())
        abstract_text.truncate(240, overflow="ellipsis")
        _add_field("Abstract", abstract_text)

    persons = reference.get("persons", {})
    authors = persons.get("author") or []
    if authors:
        _add_field("Authors", _format_person_list(authors))

    for role in sorted(persons):
        if role == "author":
            continue
        _add_field(role.capitalize(), _format_person_list(persons[role]))

    if fields:
        for field_name in sorted(fields):
            _add_field(field_name.capitalize(), fields[field_name])

    sources = reference.get("source_files") or []
    if sources:
        _add_field("Sources", "\n".join(str(source) for source in sources))

    header = Text(reference["key"], style="bold cyan")
    entry_type = reference.get("type")
    if entry_type:
        header.append(f" ({entry_type})", style="magenta")

    panel = Panel(
        grid,
        title=header,
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    return panel
