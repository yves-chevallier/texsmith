from __future__ import annotations

import hashlib
from enum import Enum
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Optional

from bs4 import BeautifulSoup, FeatureNotFound
import typer

from .config import BookConfig
from .exceptions import LatexRenderingError, TransformerExecutionError
from .renderer import LaTeXRenderer
from .transformers import register_converter


app = typer.Typer(
    help="Convert MkDocs HTML fragments into LaTeX.",
    context_settings={"help_option_names": ["--help"]},
)


@app.callback()
def _app_root() -> None:
    """Top-level CLI entry point to enable subcommands."""
    # Intentionally empty; required so Typer treats the app as a command group.
    return None


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
    parser: Optional[str] = typer.Option(
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
    template: Optional[str] = typer.Option(
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
    markdown_extensions: list[str] = typer.Option(
        [],
        "--markdown-extensions",
        "-e",
        help=(
            "Comma or space separated list of Python Markdown extensions to load."
        ),
    ),
) -> None:
    """Convert an MkDocs HTML page to LaTeX."""

    try:
        input_payload = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        typer.secho(
            f"Failed to read input document: {exc}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1) from exc

    normalized_extensions = _normalize_markdown_extensions(markdown_extensions)

    try:
        input_kind = _classify_input_source(input_path)
    except UnsupportedInputError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    is_markdown = input_kind is InputKind.MARKDOWN

    if is_markdown:
        try:
            html = _render_markdown(input_payload, normalized_extensions)
        except MarkdownConversionError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
    else:
        html = input_payload

    if not full_document and not is_markdown:
        try:
            html = _extract_content(html, selector)
        except ValueError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

    if debug:
        _persist_debug_artifacts(output_dir, input_path, html)

    config = BookConfig(project_dir=input_path.parent)

    renderer_kwargs: dict[str, Any] = {
        "output_root": output_dir,
        "copy_assets": copy_assets,
    }
    renderer_kwargs["parser"] = parser or "html.parser"

    def renderer_factory() -> LaTeXRenderer:
        return LaTeXRenderer(config=config, **renderer_kwargs)

    runtime: dict[str, object] = {
        "base_level": base_level + heading_level,
        "numbered": numbered,
        "source_dir": input_path.parent,
        "document_path": input_path,
        "copy_assets": copy_assets,
    }
    if manifest:
        runtime["generate_manifest"] = True
    if template:
        runtime["template"] = template
    if drop_title:
        runtime["drop_title"] = True

    if not disable_fallback_converters:
        _ensure_fallback_converters()

    try:
        latex_output = _render_with_fallback(renderer_factory, html, runtime)
    except LatexRenderingError as exc:
        typer.secho(
            _format_rendering_error(exc),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    typer.echo(latex_output)


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
) -> str:
    attempts = 0
    while True:
        renderer = renderer_factory()
        try:
            return renderer.render(html, runtime=runtime)
        except LatexRenderingError as exc:
            attempts += 1
            if attempts >= 5 or not _attempt_transformer_fallback(exc):
                raise


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
    if shutil.which("docker"):
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


def _normalize_markdown_extensions(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
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


def _render_markdown(source: str, extensions: list[str]) -> str:
    try:
        import markdown
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise MarkdownConversionError(
            "Python Markdown is required to process Markdown inputs; "
            "install the 'markdown' package."
        ) from exc

    try:
        md = markdown.Markdown(extensions=extensions)
    except Exception as exc:  # pragma: no cover - library-controlled
        raise MarkdownConversionError(
            f"Failed to initialize Markdown processor: {exc}"
        ) from exc

    try:
        return md.convert(source)
    except Exception as exc:  # pragma: no cover - library-controlled
        raise MarkdownConversionError(
            f"Failed to convert Markdown source: {exc}"
        ) from exc
