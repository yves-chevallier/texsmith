"""Shared Typer option definitions for CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

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
    ),
]

SelectorOption = Annotated[
    str,
    typer.Option(
        "--selector",
        help="CSS selector to extract the MkDocs article content.",
    ),
]

FullDocumentOption = Annotated[
    bool,
    typer.Option(
        "--full-document",
        help="Disable article extraction and render the entire HTML file.",
    ),
]

BaseLevelOption = Annotated[
    int,
    typer.Option(
        "--base-level",
        help="Shift detected heading levels by this offset.",
    ),
]

HeadingLevelOption = Annotated[
    int,
    typer.Option(
        "--heading-level",
        "-h",
        min=0,
        help="Indent all headings by the selected depth (e.g. 1 turns sections into subsections).",
    ),
]

DropTitleOption = Annotated[
    bool,
    typer.Option(
        "--drop-title/--keep-title",
        help="Drop the first document title heading.",
    ),
]

NumberedOption = Annotated[
    bool,
    typer.Option(
        "--numbered/--unnumbered",
        help="Toggle numbered headings.",
    ),
]

ParserOption = Annotated[
    str | None,
    typer.Option(
        "--parser",
        help='BeautifulSoup parser backend to use (defaults to "html.parser").',
    ),
]

DisableFallbackOption = Annotated[
    bool,
    typer.Option(
        "--no-fallback-converters",
        help="Disable registration of placeholder converters when Docker is unavailable.",
    ),
]

CopyAssetsOption = Annotated[
    bool,
    typer.Option(
        "--copy-assets/--no-copy-assets",
        help="Toggle copying of remote assets to the output directory.",
    ),
]

CopyAssetsOptionWithShort = Annotated[
    bool,
    typer.Option(
        "--copy-assets/--no-copy-assets",
        "-a/-A",
        help="Toggle copying of remote assets to the output directory.",
    ),
]

ManifestOption = Annotated[
    bool,
    typer.Option(
        "--manifest/--no-manifest",
        help="Generate a manifest.json file alongside the LaTeX output.",
    ),
]

ManifestOptionWithShort = Annotated[
    bool,
    typer.Option(
        "--manifest/--no-manifest",
        "-m/-M",
        help="Generate a manifest.json file alongside the LaTeX output.",
    ),
]

DebugHtmlOption = Annotated[
    bool | None,
    typer.Option(
        "--debug-html/--no-debug-html",
        help="Persist intermediate HTML snapshots (inherits from --debug when omitted).",
    ),
]

LanguageOption = Annotated[
    str | None,
    typer.Option(
        "--language",
        help="Language code passed to babel (defaults to metadata or english).",
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
    ),
]

DisableMarkdownExtensionsOption = Annotated[
    list[str] | None,
    typer.Option(
        "--disable-markdown-extensions",
        "--disable-extension",
        "-d",
        help=(
            "Markdown extensions to disable. Provide a comma separated list or repeat the option "
            "multiple times."
        ),
        show_default=False,
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
    ),
]

OutputDirOption = Annotated[
    Path,
    typer.Option(
        "--output-dir",
        "-o",
        help="Directory used to collect generated assets (if any).",
        resolve_path=True,
    ),
]

TemplateOption = Annotated[
    str | None,
    typer.Option(
        "--template",
        "-t",
        help=(
            "Select a LaTeX template to use during conversion. Accepts a local path or a registered "
            "template name."
        ),
    ),
]
