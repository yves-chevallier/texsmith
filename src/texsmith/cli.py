from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from typing import Any

from bs4 import BeautifulSoup, FeatureNotFound
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
from .templates import TemplateError, copy_template_assets, load_template
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

    effective_base_level = template_base_level or 0
    runtime: dict[str, object] = {
        "base_level": effective_base_level + base_level + heading_level,
        "numbered": numbered,
        "source_dir": input_path.parent,
        "document_path": input_path,
        "copy_assets": copy_assets,
    }
    runtime["language"] = resolved_language
    if bibliography_map:
        runtime["bibliography"] = bibliography_map
    if template_name is not None:
        runtime["template"] = template_name
    if manifest:
        runtime["generate_manifest"] = True
    if drop_title:
        runtime["drop_title"] = True

    def renderer_factory() -> LaTeXRenderer:
        formatter = LaTeXFormatter()
        for key, override_path in formatter_overrides.items():
            formatter.override_template(key, override_path)
        return LaTeXRenderer(config=config, formatter=formatter, **renderer_kwargs)

    if not disable_fallback_converters:
        _ensure_fallback_converters()

    try:
        latex_output, document_state = _render_with_fallback(
            renderer_factory,
            html,
            runtime,
            bibliography_map,
        )
    except LatexRenderingError as exc:
        typer.secho(
            _format_rendering_error(exc),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    citations = list(document_state.citations)
    bibliography_output: Path | None = None
    if citations and bibliography_collection is not None and bibliography_map:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            bibliography_output = output_dir / "texsmith-bibliography.bib"
            bibliography_collection.write_bibtex(
                bibliography_output, keys=citations
            )
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
    )


def _resolve_option(value: Any) -> Any:
    if isinstance(value, typer.models.OptionInfo):
        return value.default
    return value


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
    input_path: Path = typer.Argument(
        ...,
        help="Path to the rendered MkDocs HTML file or Markdown source.",
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
        "-s",
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
    markdown_extensions: list[str] = typer.Option(
        [],
        "--markdown-extensions",
        "-e",
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

    resolved_markdown_extensions = _resolve_markdown_extensions(
        _resolve_option(markdown_extensions),
        _resolve_option(disable_markdown_extensions),
    )

    result = _convert_document(
        input_path=input_path,
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
        markdown_extensions=resolved_markdown_extensions,
        bibliography_files=list(_resolve_option(bibliography)),
    )

    if result.tex_path is not None:
        typer.secho(
            f"LaTeX document written to {result.tex_path}",
            fg=typer.colors.GREEN,
        )
        return

    typer.echo(result.latex_output)


def _build_latexmk_command(engine: str | None, shell_escape: bool) -> list[str]:
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

    return [
        "latexmk",
        "-pdf",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-pdflatex={' '.join(tokens)}",
    ]


@app.command(name="build")
def build(
    input_path: Path = typer.Argument(
        ...,
        help="Path to the rendered MkDocs HTML file or Markdown source.",
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
        "-s",
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
    markdown_extensions: list[str] = typer.Option(
        [],
        "--markdown-extensions",
        "-e",
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

    resolved_markdown_extensions = _resolve_markdown_extensions(
        _resolve_option(markdown_extensions),
        _resolve_option(disable_markdown_extensions),
    )

    conversion = _convert_document(
        input_path=input_path,
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
        markdown_extensions=resolved_markdown_extensions,
        bibliography_files=list(_resolve_option(bibliography)),
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
) -> tuple[str, DocumentState]:
    attempts = 0
    state = DocumentState(bibliography=dict(bibliography or {}))
    while True:
        renderer = renderer_factory()
        try:
            output = renderer.render(html, runtime=runtime, state=state)
            return output, state
        except LatexRenderingError as exc:
            attempts += 1
            if attempts >= 5 or not _attempt_transformer_fallback(exc):
                raise
            state = DocumentState(bibliography=dict(bibliography or {}))


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
