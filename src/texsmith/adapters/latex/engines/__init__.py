"""Pluggable LaTeX engine helpers (latexmk, Tectonic, log parsing)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import io
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Literal

from rich.console import Console

from texsmith.core.context import DocumentState

from ..latexmk import (
    LatexmkEngine,
    build_engine_command as build_pdflatex_command,
    latexmk_pdf_flag,
    normalise_engine_command,
    normalise_index_engine,
)
from .latex import (
    LatexLogParser,
    LatexMessage,
    LatexMessageSeverity,
    LatexStreamResult,
    parse_latex_log,
    run_latex_engine,
)
from .tectonic import run_tectonic_engine


EngineBackend = Literal["tectonic", "latexmk"]


@dataclass(slots=True)
class EngineChoice:
    """Resolved backend and latexmk program selection."""

    backend: EngineBackend
    latexmk_engine: str | None

    @property
    def label(self) -> str:
        return "tectonic" if self.backend == "tectonic" else "latexmk"


@dataclass(slots=True)
class EngineFeatures:
    """Feature flags that influence engine configuration."""

    requires_shell_escape: bool
    bibliography: bool
    has_index: bool
    has_glossary: bool
    index_engine: str | None = None


@dataclass(slots=True)
class EngineCommand:
    """Executable command plus metadata."""

    argv: list[str]
    log_path: Path
    pdf_path: Path


@dataclass(slots=True)
class EngineResult:
    """Outcome of a LaTeX build run."""

    returncode: int
    messages: list[LatexMessage]
    command: list[str]
    log_path: Path
    pdf_path: Path


def resolve_engine(preference: str | None, template_engine: str | None) -> EngineChoice:
    """Resolve the engine backend and latexmk program to use."""
    candidate = preference.strip().lower() if preference else ""

    if candidate == "tectonic":
        return EngineChoice(backend="tectonic", latexmk_engine=None)

    if candidate in {"xelatex", "lualatex", "pdflatex"}:
        return EngineChoice(backend="latexmk", latexmk_engine=candidate)

    engine_value = template_engine if candidate == "template" else preference or template_engine

    return EngineChoice(backend="latexmk", latexmk_engine=engine_value)


def compute_features(
    *,
    requires_shell_escape: bool,
    bibliography: bool,
    document_state: DocumentState | None,
    template_context: Mapping[str, Any] | None,
) -> EngineFeatures:
    """Derive engine feature flags from render metadata."""
    has_index = bool(
        getattr(document_state, "has_index_entries", False)
        or getattr(document_state, "index_entries", [])
    )
    has_glossary = bool(
        getattr(document_state, "acronyms", {}) or getattr(document_state, "glossary", {})
    )

    index_engine: str | None = None
    if template_context:
        raw_engine = template_context.get("index_engine")
        if isinstance(raw_engine, str):
            candidate = raw_engine.strip()
            if candidate:
                index_engine = candidate

    return EngineFeatures(
        requires_shell_escape=requires_shell_escape,
        bibliography=bibliography,
        has_index=has_index,
        has_glossary=has_glossary,
        index_engine=index_engine,
    )


def missing_dependencies(
    choice: EngineChoice,
    features: EngineFeatures,
    *,
    use_system_tectonic: bool = False,
    available_binaries: Mapping[str, str | Path] | None = None,
) -> list[str]:
    """Return missing executables required by the selected engine."""
    missing: list[str] = []

    def _check(binary: str) -> None:
        if available_binaries and binary in available_binaries:
            candidate = Path(available_binaries[binary])
            if candidate.exists():
                return
        if shutil.which(binary) is None:
            missing.append(binary)

    if choice.backend == "tectonic":
        if use_system_tectonic:
            _check("tectonic")
    else:
        _check("latexmk")
        engine_config = normalise_engine_command(
            choice.latexmk_engine, shell_escape=features.requires_shell_escape
        )
        if engine_config.command:
            _check(engine_config.command[0])

    if features.bibliography:
        _check("biber")
    if features.has_index:
        index_engine = normalise_index_engine(features.index_engine)
        _check("texindy" if index_engine == "texindy" else "makeindex")
    if features.has_glossary:
        _check("makeglossaries")

    return missing


def build_engine_command(
    choice: EngineChoice,
    features: EngineFeatures,
    *,
    main_tex_path: Path,
    tectonic_binary: str | Path | None = None,
) -> EngineCommand:
    """Construct the command to compile the LaTeX document."""
    if choice.backend == "tectonic":
        binary = str(tectonic_binary) if tectonic_binary else "tectonic"
        argv = [
            binary,
            "-X",
            "compile",
            main_tex_path.name,
            "--keep-logs",
            "--keep-intermediates",
            "--synctex",
            "--outdir",
            ".",
        ]
        log_path = main_tex_path.with_suffix(".log")
        pdf_path = main_tex_path.with_suffix(".pdf")
        return EngineCommand(argv=argv, log_path=log_path, pdf_path=pdf_path)

    engine_config = normalise_engine_command(
        choice.latexmk_engine, shell_escape=features.requires_shell_escape
    )
    command = [
        "latexmk",
        latexmk_pdf_flag(engine_config.pdf_mode),
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-pdflatex={build_pdflatex_command(engine_config)}",
        main_tex_path.name,
    ]
    if features.bibliography:
        command.insert(2, "-bibtex")

    log_path = main_tex_path.with_suffix(".log")
    pdf_path = main_tex_path.with_suffix(".pdf")
    return EngineCommand(argv=command, log_path=log_path, pdf_path=pdf_path)


def ensure_command_paths(command: EngineCommand) -> EngineCommand:
    """Resolve the primary binary path for the generated command."""
    argv = list(command.argv)
    if argv:
        binary = argv[0]
        resolved = shutil.which(binary)
        if resolved:
            argv[0] = resolved
    return EngineCommand(argv=argv, log_path=command.log_path, pdf_path=command.pdf_path)


def build_tex_env(
    render_dir: Path,
    *,
    isolate_cache: bool,
    extra_path: Path | None = None,
    biber_path: Path | None = None,
) -> dict[str, str]:
    """Construct TeX cache environment variables (shared by all engines)."""
    if isolate_cache:
        tex_cache_root = (render_dir / ".texmf-cache").resolve()
    else:
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg_cache).expanduser() if xdg_cache else Path.home() / ".cache"
        tex_cache_root = (base / "texsmith").resolve()

    tex_cache_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()

    texmf_home = tex_cache_root / "texmf-home"
    texmf_var = tex_cache_root / "texmf-var"
    luatex_cache = tex_cache_root / "luatex-cache"

    texmf_cache = tex_cache_root / "texmf-cache"
    texmf_config = tex_cache_root / "texmf-config"
    xdg_cache = tex_cache_root / "xdg-cache"
    tectonic_cache = tex_cache_root / "tectonic-cache"

    for cache_path in (
        texmf_home,
        texmf_var,
        texmf_config,
        luatex_cache,
        texmf_cache,
        xdg_cache,
        tectonic_cache,
    ):
        cache_path.mkdir(parents=True, exist_ok=True)

    if extra_path:
        env["PATH"] = f"{extra_path}{os.pathsep}{env.get('PATH', '')}"

    env["TEXMFHOME"] = str(texmf_home)
    env["TEXMFVAR"] = str(texmf_var)
    env["TEXMFCONFIG"] = str(texmf_config)
    env["LUATEXCACHE"] = str(luatex_cache)
    env["LUAOTFLOAD_CACHE"] = str(luatex_cache)
    env["TEXMFCACHE"] = str(texmf_cache)
    env.setdefault("XDG_CACHE_HOME", str(xdg_cache))
    env["TECTONIC_CACHE_DIR"] = str(tectonic_cache)
    if biber_path:
        env["BIBER"] = str(biber_path)
    return env


def run_engine_command(
    command: EngineCommand,
    *,
    backend: EngineBackend,
    workdir: Path,
    env: Mapping[str, str],
    console: Console | None,
    verbosity: int = 0,
    classic_output: bool = False,
) -> EngineResult:
    """Execute the engine command, streaming logs when requested."""
    argv = command.argv
    log_path = command.log_path
    console = console or Console(file=io.StringIO())

    if classic_output:
        process = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            cwd=workdir,
            env=dict(env),
        )
        if process.stdout:
            console.print(process.stdout.rstrip())
        if process.stderr:
            console.print(process.stderr.rstrip())
        messages: list[LatexMessage] = []
        if process.returncode != 0:
            messages = parse_latex_log(log_path)
        return EngineResult(
            returncode=process.returncode,
            messages=messages,
            command=argv,
            log_path=log_path,
            pdf_path=command.pdf_path,
        )

    if backend == "latexmk":
        result: LatexStreamResult = run_latex_engine(
            argv,
            workdir=workdir,
            env=env,
            console=console,
            verbosity=verbosity,
        )
    else:
        result = run_tectonic_engine(
            argv,
            workdir=workdir,
            env=env,
            console=console,
        )
    messages = result.messages if result.returncode != 0 else result.messages or []
    if result.returncode != 0 and not messages:
        messages = parse_latex_log(log_path)
    return EngineResult(
        returncode=result.returncode,
        messages=messages,
        command=argv,
        log_path=log_path,
        pdf_path=command.pdf_path,
    )


__all__ = [
    "EngineChoice",
    "EngineCommand",
    "EngineFeatures",
    "EngineResult",
    "LatexLogParser",
    "LatexMessage",
    "LatexMessageSeverity",
    "LatexStreamResult",
    "build_engine_command",
    "build_tex_env",
    "compute_features",
    "ensure_command_paths",
    "missing_dependencies",
    "parse_latex_log",
    "resolve_engine",
    "run_engine_command",
]
