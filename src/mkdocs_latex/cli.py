from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from typing import Any, Callable, Iterable, Mapping, Optional

from bs4 import BeautifulSoup, FeatureNotFound
import typer
import yaml

from .config import BookConfig
from .exceptions import LatexRenderingError, TransformerExecutionError
from .context import DocumentState
from .renderer import LaTeXRenderer
from .templates import TemplateError, copy_template_assets, load_template
from .transformers import register_converter


DEFAULT_MARKDOWN_EXTENSIONS = [
    "extra",  # Tableaux, listes imbriquées, etc.
    "abbr",  # Abréviations
    "attr_list",  # Attributs sur les éléments HTML
    "def_list",  # Listes de définitions
    "fenced_code",  # Blocs de code délimités par ```
    "smarty",  # SmartyPants
    "tables",  # Tables
    "mdx_math",  # Support des formules mathématiques
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
)


@app.callback()
def _app_root() -> None:
    """Top-level CLI entry point to enable subcommands."""
    # Intentionally empty; required so Typer treats the app as a command group.
    return None


def _convert_document(
    input_path: Path,
    output_dir: Path,
    selector: str,
    full_document: bool,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
    parser: Optional[str],
    disable_fallback_converters: bool,
    copy_assets: bool,
    manifest: bool,
    template: Optional[str],
    debug: bool,
    language: Optional[str],
    markdown_extensions: list[str],
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
    runtime["language"] = resolved_language
    if manifest:
        runtime["generate_manifest"] = True
    if drop_title:
        runtime["drop_title"] = True

    template_overrides = _build_template_overrides(front_matter)
    template_overrides["language"] = resolved_language
    meta_section = template_overrides.get("meta")
    if isinstance(meta_section, dict):
        meta_section.setdefault("language", resolved_language)

    template_info_engine: str | None = None
    template_requires_shell_escape = False
    template_instance = None
    template_context: dict[str, Any] | None = None
    if template:
        try:
            template_instance = load_template(template)
        except TemplateError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        runtime["template"] = template_instance.info.name
        template_info_engine = template_instance.info.engine
        template_requires_shell_escape = bool(template_instance.info.shell_escape)

    if not disable_fallback_converters:
        _ensure_fallback_converters()

    try:
        latex_output, document_state = _render_with_fallback(
            renderer_factory, html, runtime
        )
    except LatexRenderingError as exc:
        typer.secho(
            _format_rendering_error(exc),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    tex_path: Path | None = None
    if template_instance is not None:
        try:
            template_context = template_instance.prepare_context(
                latex_output,
                overrides=template_overrides if template_overrides else None,
            )
            template_context["index_entries"] = document_state.has_index_entries
            template_context["acronyms"] = dict(document_state.acronyms)
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
    language: Optional[str] = typer.Option(
        None,
        "--language",
        help="Language code passed to babel (defaults to metadata or english).",
    ),
    markdown_extensions: list[str] = typer.Option(
        [],
        "--markdown-extensions",
        "-e",
        help=("Comma or space separated list of Python Markdown extensions to load."),
    ),
) -> None:
    """Convert an MkDocs HTML page to LaTeX."""

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
        markdown_extensions=_resolve_option(markdown_extensions),
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
    language: Optional[str] = typer.Option(
        None,
        "--language",
        help="Language code passed to babel (defaults to metadata or english).",
    ),
    markdown_extensions: list[str] = typer.Option(
        [],
        "--markdown-extensions",
        "-e",
        help=("Comma or space separated list of Python Markdown extensions to load."),
    ),
) -> None:
    """Convert inputs and compile the rendered document with latexmk."""

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
        markdown_extensions=_resolve_option(markdown_extensions),
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
) -> tuple[str, DocumentState]:
    attempts = 0
    state = DocumentState()
    while True:
        renderer = renderer_factory()
        try:
            output = renderer.render(html, runtime=runtime, state=state)
            return output, state
        except LatexRenderingError as exc:
            attempts += 1
            if attempts >= 5 or not _attempt_transformer_fallback(exc):
                raise
            state = DocumentState()


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
        _normalise_template_language(
            _extract_language_from_front_matter(front_matter)
        ),
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
