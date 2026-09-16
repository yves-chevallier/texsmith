"""The ``texsmith site`` commands: what a site generator needs made ahead of it.

``texsmith site assets`` writes the files a TeXSmith site cannot produce while
it renders — the stylesheet, the ``.snippet`` previews and the SVG of every
``.drawio`` image — under ``docs_dir``, where they are sources of the site like
any hand-written image. Zensical needs this: it clears the site directory
before a build and replays cached pages without calling Python, so nothing a
render writes can be relied upon. MkDocs does not need it, and does not mind
it: it copies the files it finds and skips generating its own.

``texsmith site build`` is the other half of what a generator without plugin
hooks cannot do: the PDF book of the site, which MkDocs builds from
``on_post_build``. It reads the same configuration file, resolves the same
navigation and runs the same builder over the same files, so the ``.tex`` it
writes is the one ``mkdocs build`` writes, byte for byte.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from texsmith.diagnostics import LoggingEmitter
from texsmith.site import assets
from texsmith.site.book import BookError, build_books
from texsmith.site.config import CONFIG_NAMES, SiteConfig, config_file_in, load_site_config

from .._options import BuildDirOption, DiagnosticsJsonOption, StrictOption
from ..diagnostics import CliEmitter
from ..presenter import write_diagnostics_json
from ..state import emit_error, emit_warning, get_cli_state


app = typer.Typer(
    help="Prepare a documentation site built by MkDocs or Zensical.",
    no_args_is_help=True,
)

#: Every sub-command takes the same optional path to the site's configuration.
ConfigArgument = Annotated[
    Path | None,
    typer.Argument(
        metavar="CONFIG",
        help=(
            "The site's configuration file. Defaults to the first of "
            f"{', '.join(CONFIG_NAMES)} in the current directory."
        ),
        exists=True,
        dir_okay=False,
    ),
]


def _display_path(target: Path, root: Path) -> str:
    """``target`` seen from the project directory, when it sits under it."""
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return target.as_posix()


def site_configuration(config: Path | None) -> SiteConfig:
    """Read the configuration a sub-command was given, or the one in this directory."""
    config_path = config or config_file_in(Path.cwd())
    if config_path is None:
        emit_error(
            f"No site configuration found; expected one of {', '.join(CONFIG_NAMES)} "
            "in the current directory."
        )
        raise typer.Exit(code=1)
    return load_site_config(config_path)


@app.command("assets")
def site_assets(config: ConfigArgument = None) -> None:
    """Write the stylesheet, the snippet previews and the diagrams into the docs."""
    console = get_cli_state().console
    site_config = site_configuration(config)
    docs_dir = site_config.docs_dir

    def announce(preview: assets.Preview) -> None:
        verb = "rendered" if preview.built else "up to date"
        console.print(f"{preview.page}: {preview.basename} ({verb})")

    generated = assets.generate(
        site_config,
        emitter=LoggingEmitter(),
        on_preview=announce,
    )

    for drawing in generated.drawings:
        verb = "exported" if drawing.built else "up to date"
        console.print(f"{drawing.page}: {drawing.uri} ({verb})")
    for failure in generated.failures:
        emit_warning(f"{failure.page}: {failure.message}")
    for name in generated.pruned:
        console.print(f"pruned {name}: no page asks for it any more")

    root = docs_dir.parent
    built = sum(1 for preview in generated.previews if preview.built)
    exported = sum(1 for drawing in generated.drawings if drawing.built)
    console.print(
        f"{len(generated.previews)} snippet previews under "
        f"{assets.snippet_dir(docs_dir).relative_to(root)}: {built} rendered. "
        f"{len(generated.drawings)} draw.io diagrams under "
        f"{assets.drawio_dir(docs_dir).relative_to(root)}: {exported} exported. "
        f"{len(generated.pruned)} pruned, {len(generated.failures)} failed. "
        f"Stylesheet at {generated.stylesheet.relative_to(root)}."
    )


@app.command("build")
def site_build(
    config: ConfigArgument = None,
    build_dir: BuildDirOption = None,
    book: Annotated[
        str | None,
        typer.Option(
            "--book",
            metavar="TITLE",
            help="Build only the book with that title, instead of every book declared.",
            show_default=False,
        ),
    ] = None,
    pdf: Annotated[
        bool,
        typer.Option(
            "--pdf/--no-pdf",
            help="Compile the PDF once the bundle is written, or stop at the '.tex'.",
        ),
    ] = True,
    strict: StrictOption = False,
    diagnostics_json: DiagnosticsJsonOption = None,
) -> None:
    """Build the PDF books the site declares under its 'texsmith' options."""
    state = get_cli_state()
    console = state.console
    site_config = site_configuration(config)
    emitter = CliEmitter(state=state)

    def flush(failure: str | None = None) -> None:
        """Dump the diagnostics and apply ``--strict``, before the engine runs."""
        if diagnostics_json is not None:
            try:
                write_diagnostics_json(diagnostics_json, emitter.sink)
            except OSError as exc:
                emit_error(f"Failed to write diagnostics to '{diagnostics_json}': {exc}", exc)
                raise typer.Exit(code=1) from exc
        if failure is not None:
            emit_error(failure)
            raise typer.Exit(code=1)
        if strict and emitter.sink.strict_failed():
            emit_error("Diagnostics were recorded and --strict is on.")
            raise typer.Exit(code=1)

    try:
        results = build_books(
            site_config,
            emitter=emitter,
            build_dir=build_dir,
            title=book,
            compile_pdf=pdf,
            on_written=lambda _result: flush(),
        )
    except BookError as exc:
        flush(str(exc))
        raise typer.Exit(code=1) from exc  # pragma: no cover - flush always exits

    flush()
    root = site_config.project_dir
    for result in results:
        target = result.pdf_path or result.tex_path
        console.print(f"{result.title}: {_display_path(target, root)}")
