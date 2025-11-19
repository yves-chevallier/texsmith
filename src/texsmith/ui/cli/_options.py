"""Shared Typer option definitions for CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


INPUTS_PANEL = "Input Handling"
STRUCTURE_PANEL = "Structure"
RENDERING_PANEL = "Rendering"
OUTPUT_PANEL = "Output"
TEMPLATE_PANEL = "Template"
DIAGNOSTICS_PANEL = "Diagnostics"

InputPathArgument = Annotated[
    list[Path] | None,
    typer.Argument(
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
        rich_help_panel=INPUTS_PANEL,
    ),
]

SelectorOption = Annotated[
    str,
    typer.Option(
        "--selector",
        help="CSS selector to extract the MkDocs article content.",
        rich_help_panel=INPUTS_PANEL,
    ),
]

FullDocumentOption = Annotated[
    bool,
    typer.Option(
        "--full-document",
        help="Disable article extraction and render the entire HTML file.",
        rich_help_panel=INPUTS_PANEL,
    ),
]

BaseLevelOption = Annotated[
    int,
    typer.Option(
        "--base-level",
        help="Shift detected heading levels by this offset.",
        rich_help_panel=STRUCTURE_PANEL,
    ),
]

HeadingLevelOption = Annotated[
    int,
    typer.Option(
        "--heading-level",
        "-h",
        min=0,
        help="Indent all headings by the selected depth (e.g. 1 turns sections into subsections).",
        rich_help_panel=STRUCTURE_PANEL,
    ),
]

DropTitleOption = Annotated[
    bool,
    typer.Option(
        "--drop-title/--keep-title",
        help="Drop the first document title heading.",
        rich_help_panel=STRUCTURE_PANEL,
    ),
]

TitleFromHeadingOption = Annotated[
    bool,
    typer.Option(
        "--title-from-heading/--title-from-frontmatter",
        help="Treat the first heading as the template title and remove it from the document.",
        rich_help_panel=TEMPLATE_PANEL,
    ),
]

NumberedOption = Annotated[
    bool,
    typer.Option(
        "--numbered/--unnumbered",
        help="Toggle numbered headings.",
        rich_help_panel=STRUCTURE_PANEL,
    ),
]

ParserOption = Annotated[
    str | None,
    typer.Option(
        "--parser",
        help='BeautifulSoup parser backend to use (defaults to "html.parser").',
        rich_help_panel=INPUTS_PANEL,
    ),
]

DisableFallbackOption = Annotated[
    bool,
    typer.Option(
        "--no-fallback-converters",
        help="Disable registration of placeholder converters when Docker is unavailable.",
        rich_help_panel=RENDERING_PANEL,
    ),
]

CopyAssetsOption = Annotated[
    bool,
    typer.Option(
        "--copy-assets/--no-copy-assets",
        help="Toggle copying of remote assets to the output directory.",
        rich_help_panel=RENDERING_PANEL,
    ),
]

CopyAssetsOptionWithShort = Annotated[
    bool,
    typer.Option(
        "--copy-assets/--no-copy-assets",
        "-c/-C",
        help="Toggle copying of remote assets to the output directory.",
        rich_help_panel=RENDERING_PANEL,
    ),
]

ConvertAssetsOption = Annotated[
    bool,
    typer.Option(
        "--convert-assets/--no-convert-assets",
        help=(
            "Convert bitmap assets (PNG/JPEG) to PDF even when LaTeX supports the original format."
        ),
        rich_help_panel=RENDERING_PANEL,
    ),
]

HashAssetsOption = Annotated[
    bool,
    typer.Option(
        "--hash-assets/--no-hash-assets",
        help="Hash stored asset filenames instead of preserving their original names.",
        rich_help_panel=RENDERING_PANEL,
    ),
]

TemplateAttributeOption = Annotated[
    list[str] | None,
    typer.Option(
        "--attribute",
        "-a",
        help="Override template attributes as key=value pairs (e.g. -a emoji=color).",
        show_default=False,
        rich_help_panel=TEMPLATE_PANEL,
    ),
]

ManifestOption = Annotated[
    bool,
    typer.Option(
        "--manifest/--no-manifest",
        help="Generate a manifest.json file alongside the LaTeX output.",
        rich_help_panel=RENDERING_PANEL,
    ),
]

ManifestOptionWithShort = Annotated[
    bool,
    typer.Option(
        "--manifest/--no-manifest",
        "-m/-M",
        help="Generate a manifest.json file alongside the LaTeX output.",
        rich_help_panel=RENDERING_PANEL,
    ),
]

DebugHtmlOption = Annotated[
    bool | None,
    typer.Option(
        "--debug-html/--no-debug-html",
        help="Persist intermediate HTML snapshots (inherits from --debug when omitted).",
        rich_help_panel=DIAGNOSTICS_PANEL,
    ),
]

LanguageOption = Annotated[
    str | None,
    typer.Option(
        "--language",
        help="Language code passed to babel (defaults to metadata or english).",
        rich_help_panel=RENDERING_PANEL,
    ),
]

SlotsOption = Annotated[
    list[str] | None,
    typer.Option(
        "--slot",
        "-s",
        help=(
            "Inject a document section into a template slot using 'slot:Section'. Repeat to map "
            "multiple sections."
        ),
        show_default=False,
        rich_help_panel=TEMPLATE_PANEL,
    ),
]

MarkdownExtensionsOption = Annotated[
    list[str] | None,
    typer.Option(
        "--markdown-extensions",
        "-x",
        help=(
            "Additional Markdown extensions to enable (comma or space separated values are accepted)."
        ),
        show_default=False,
        rich_help_panel=RENDERING_PANEL,
    ),
]

DisableMarkdownExtensionsOption = Annotated[
    list[str] | None,
    typer.Option(
        "--disable-extension",
        "-d",
        help=(
            "Markdown extensions to disable. Provide a comma separated list or repeat the option "
            "multiple times."
        ),
        show_default=False,
        rich_help_panel=RENDERING_PANEL,
    ),
]

BibliographyOption = Annotated[
    list[Path] | None,
    typer.Option(
        "--bibliography",
        "-b",
        help="BibTeX files merged and exposed to the renderer.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        show_default=False,
        rich_help_panel=TEMPLATE_PANEL,
    ),
]

OutputPathOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        "-o",
        "--output-dir",
        help="Output file or directory. Defaults to stdout unless a template is used.",
        show_default=False,
        rich_help_panel=OUTPUT_PANEL,
    ),
]

OutputDirOption = Annotated[
    Path,
    typer.Option(
        "--output-dir",
        "-o",
        help="Directory used to collect generated assets (if any).",
        resolve_path=True,
        rich_help_panel=OUTPUT_PANEL,
    ),
]

TemplateOption = Annotated[
    str | None,
    typer.Option(
        "--template",
        "-t",
        help=(
            "Select a LaTeX template to use during conversion. Accepts a local path, entry point, "
            "or built-in slug such as 'article' or 'letter'."
        ),
        rich_help_panel=TEMPLATE_PANEL,
    ),
]

OpenLogOption = Annotated[
    bool,
    typer.Option(
        "--open-log/--no-open-log",
        help="Open the latexmk log with the system viewer when compilation fails.",
        rich_help_panel=DIAGNOSTICS_PANEL,
    ),
]
