"""Compile a rendered template into a PDF.

Selecting an engine, acquiring the binaries it needs and running it is a
build concern, not a conversion one: this used to be a method of
``ConversionService``, which imported a third of ``adapters.latex`` to carry
it. ``run_engine`` is injected so a caller (or a test) substitutes the
execution step without patching module globals.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from texsmith.adapters.latex.engines import (
    EngineChoice,
    EngineFeatures,
    EngineResult,
    build_engine_command,
    build_tex_env,
    compute_features,
    ensure_command_paths,
    missing_dependencies,
    resolve_engine,
    run_engine_command,
)
from texsmith.adapters.latex.pyxindy import is_available as pyxindy_available
from texsmith.adapters.latex.tectonic import (
    BiberAcquisitionError,
    MakeglossariesAcquisitionError,
    TectonicAcquisitionError,
    select_biber_binary,
    select_makeglossaries,
    select_tectonic_binary,
)
from texsmith.core.exceptions import ConversionError


logger = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.conversion.renderer import TemplateRenderResult


__all__ = ["build_pdf", "compile_tex"]


def compile_tex(
    main_tex_path: Path,
    features: EngineFeatures,
    *,
    engine: str | None = "tectonic",
    template_engine: str | None = None,
    classic_output: bool = False,
    isolate_cache: bool = False,
    env: Mapping[str, str] | None = None,
    console: Any | None = None,
    verbosity: int = 0,
    use_system_tectonic: bool = False,
    prepare: Callable[[EngineChoice, EngineFeatures], None] | None = None,
    run_engine: Callable[..., EngineResult] = run_engine_command,
) -> EngineResult:
    """Run the engine over one ``.tex``: choose it, acquire what it needs, run it.

    One implementation for the two documents TeXSmith compiles — the single
    document of ``texsmith doc.md --build`` and the book of a site — so the
    auxiliary programs ``features`` calls for run for both. They are what
    ``features`` is *for*: the runner is what turns ``has_index`` into a
    ``makeindex``/``xindy`` pass between two engine runs, so a caller that
    leaves them out gets a document whose index prints nothing at all.

    ``prepare`` is called with the resolved choice before the command is
    built, for a caller that has a file to write first (the book's
    ``.latexmkrc``). ``run_engine`` is the execution step, injectable so a
    test substitutes it without monkeypatching module globals.
    """
    choice = resolve_engine(engine, template_engine)
    tectonic_binary: Path | None = None
    biber_binary: Path | None = None
    makeglossaries_binary: Path | None = None
    bundled_bin: Path | None = None
    if choice.backend == "tectonic":
        try:
            selection = select_tectonic_binary(use_system_tectonic, console=console)
            if features.bibliography and not use_system_tectonic:
                biber_binary = select_biber_binary(console=console)
                bundled_bin = biber_binary.parent
            if features.has_glossary and not pyxindy_available():
                glossaries = select_makeglossaries(console=console)
                makeglossaries_binary = glossaries.path
                if glossaries.source == "bundled":
                    bundled_bin = bundled_bin or glossaries.path.parent
        except (
            TectonicAcquisitionError,
            BiberAcquisitionError,
            MakeglossariesAcquisitionError,
        ) as exc:
            raise ConversionError(str(exc)) from exc
        tectonic_binary = selection.path

    available_bins: dict[str, Path] = {}
    if biber_binary:
        available_bins["biber"] = biber_binary
    if makeglossaries_binary:
        available_bins["makeglossaries"] = makeglossaries_binary

    missing = missing_dependencies(
        choice,
        features,
        use_system_tectonic=use_system_tectonic and choice.backend == "tectonic",
        available_binaries=available_bins or None,
    )
    if missing:
        formatted = ", ".join(sorted(set(missing)))
        raise ConversionError(f"Missing required LaTeX tools for '{choice.label}': {formatted}")

    if prepare is not None:
        prepare(choice, features)

    command_plan = ensure_command_paths(
        build_engine_command(
            choice,
            features,
            main_tex_path=main_tex_path,
            tectonic_binary=tectonic_binary,
        )
    )
    base_env = build_tex_env(
        main_tex_path.parent,
        isolate_cache=isolate_cache,
        extra_path=bundled_bin,
        biber_path=biber_binary,
    )
    merged_env = dict(base_env)
    if env:
        merged_env.update(env)

    result = run_engine(
        command_plan,
        backend=choice.backend,
        workdir=main_tex_path.parent,
        env=merged_env,
        console=console,
        verbosity=verbosity,
        classic_output=classic_output,
        features=features,
    )
    _attach_reference_pages(main_tex_path)
    return result


def build_pdf(
    render_result: TemplateRenderResult,
    *,
    engine: str | None = "tectonic",
    classic_output: bool = False,
    isolate_cache: bool = False,
    env: Mapping[str, str] | None = None,
    console: Any | None = None,
    verbosity: int = 0,
    use_system_tectonic: bool = False,
    run_engine: Callable[..., EngineResult] = run_engine_command,
) -> EngineResult:
    """Compile a rendered template into a PDF: the features of one render, then :func:`compile_tex`."""
    return compile_tex(
        render_result.main_tex_path,
        compute_features(
            requires_shell_escape=render_result.requires_shell_escape,
            bibliography=render_result.has_bibliography,
            document_state=render_result.document_state,
            template_context=render_result.context,
        ),
        engine=engine,
        template_engine=render_result.template_engine,
        classic_output=classic_output,
        isolate_cache=isolate_cache,
        env=env,
        console=console,
        verbosity=verbosity,
        use_system_tectonic=use_system_tectonic,
        run_engine=run_engine,
    )


def _attach_reference_pages(main_tex_path: Path) -> None:
    """Fold the page numbers of the finished run into the published inventory."""
    from texsmith.core.crossrefs import INVENTORY_SUFFIX, attach_pages

    inventory = main_tex_path.with_name(f"{main_tex_path.stem}{INVENTORY_SUFFIX}")
    if not inventory.exists():
        return
    try:
        attach_pages(inventory, main_tex_path.with_suffix(".aux"))
    except OSError as exc:  # pragma: no cover - the PDF itself is fine
        logger.warning("Could not attach page numbers to '%s': %s", inventory, exc)
