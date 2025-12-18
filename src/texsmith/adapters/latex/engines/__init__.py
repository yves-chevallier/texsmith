"""Pluggable LaTeX engine helpers (latexmk, Tectonic, log parsing)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import io
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Literal

from rich.console import Console

from texsmith.core.context import DocumentState
from texsmith.core.user_dir import get_user_dir

from ..latexmk import (
    LatexmkEngine,
    build_engine_command as build_pdflatex_command,
    latexmk_pdf_flag,
    normalise_engine_command,
    normalise_index_engine,
)
from ..pyxindy import (
    glossary_command_tokens as pyxindy_glossary_tokens,
    index_command_tokens as pyxindy_index_tokens,
    is_available as pyxindy_available,
)
from ..tectonic import select_makeglossaries
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


_TECTONIC_RERUN_TOKENS = (
    "rerun to get cross-references right",
    "rerun to get cross references right",
    "label(s) may have changed",
    "there were undefined references",
    "there were undefined citations",
    "package rerunfilecheck warning",
    "please rerun",
)


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
        if index_engine == "pyxindy":
            if not pyxindy_available():
                missing.append("pyxindy")
        else:
            _check("texindy" if index_engine == "texindy" else "makeindex")
    if features.has_glossary and not pyxindy_available():
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
        if tectonic_binary is None:
            binary = "tectonic"
        else:
            binary_path = Path(tectonic_binary)
            if not binary_path.drive and binary_path.anchor in {"/", "\\"}:
                binary = binary_path.as_posix()
            else:
                binary = os.fspath(binary_path)
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


def _looks_like_path(binary: str) -> bool:
    """Return True when ``binary`` already encodes a filesystem path."""
    if Path(binary).is_absolute():
        return True
    separators = [os.sep]
    if os.altsep:
        separators.append(os.altsep)
    return any(sep and sep in binary for sep in separators)


def ensure_command_paths(command: EngineCommand) -> EngineCommand:
    """Resolve the primary binary path for the generated command."""
    argv = list(command.argv)
    if argv:
        binary = str(argv[0])
        if not _looks_like_path(binary):
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
        tex_cache_root = get_user_dir().cache_dir("texmf")

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
    features: EngineFeatures | None = None,
    rerun_limit: int = 5,
) -> EngineResult:
    """Execute the engine command, streaming logs when requested."""
    argv = command.argv
    log_path = command.log_path
    console = console or Console(file=io.StringIO())

    if backend == "tectonic" and features is not None:
        return _run_tectonic_build(
            command,
            features,
            workdir=workdir,
            env=env,
            console=console,
            classic_output=classic_output,
            rerun_limit=rerun_limit,
        )

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
    return _stream_result_to_engine_result(result, command)


def _stream_result_to_engine_result(
    result: LatexStreamResult, command: EngineCommand
) -> EngineResult:
    log_path = command.log_path
    messages = result.messages if result.returncode != 0 else result.messages or []
    if result.returncode != 0 and not messages:
        messages = parse_latex_log(log_path)
    return EngineResult(
        returncode=result.returncode,
        messages=messages,
        command=command.argv,
        log_path=log_path,
        pdf_path=command.pdf_path,
    )


@dataclass(slots=True)
class _AuxiliaryToolRun:
    returncode: int
    stdout: str
    stderr: str


def _invoke_auxiliary_tool(
    label: str,
    argv: Sequence[str],
    *,
    workdir: Path,
    env: Mapping[str, str],
    console: Console,
) -> _AuxiliaryToolRun:
    console.print(f"[cyan]Running {label}…[/]")
    try:
        process = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            text=True,
            cwd=workdir,
            env=dict(env),
        )
        stdout = process.stdout or ""
        stderr = process.stderr or ""
    except OSError as exc:
        stdout = ""
        stderr = str(exc)
        console.print(stderr)
        return _AuxiliaryToolRun(returncode=1, stdout=stdout, stderr=stderr)

    if stdout:
        console.print(stdout.rstrip())
    if stderr:
        console.print(stderr.rstrip())
    return _AuxiliaryToolRun(
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _tool_failure_result(
    tool: str,
    run: _AuxiliaryToolRun,
    *,
    command: EngineCommand,
) -> EngineResult:
    summary = f"{tool} failed with status {run.returncode}"
    details = [segment for segment in (run.stdout.strip(), run.stderr.strip()) if segment]
    message = LatexMessage(
        severity=LatexMessageSeverity.ERROR,
        summary=summary,
        details=details,
    )
    return EngineResult(
        returncode=run.returncode or 1,
        messages=[message],
        command=command.argv,
        log_path=command.log_path,
        pdf_path=command.pdf_path,
    )


def _run_tectonic_build(
    command: EngineCommand,
    features: EngineFeatures,
    *,
    workdir: Path,
    env: Mapping[str, str],
    console: Console,
    classic_output: bool,
    rerun_limit: int,
) -> EngineResult:
    job_stem = command.log_path.with_suffix("").name
    index_engine = normalise_index_engine(features.index_engine) if features.has_index else None
    rerun_target = max(1, rerun_limit)
    ran_biber = False
    ran_index = False
    ran_glossary = False

    last_result: LatexStreamResult | None = None

    for pass_number in range(1, rerun_target + 1):
        result = _run_single_tectonic_pass(
            command,
            workdir=workdir,
            env=env,
            console=console,
            classic_output=classic_output,
        )
        last_result = result
        if result.returncode != 0:
            return _stream_result_to_engine_result(result, command)

        forced_rerun = False

        if features.bibliography and not ran_biber:
            ran, failure = _maybe_run_biber(
                job_stem,
                workdir=workdir,
                env=env,
                console=console,
                command=command,
            )
            if failure is not None:
                return failure
            if ran:
                ran_biber = True
                forced_rerun = True

        if features.has_index and not ran_index and index_engine:
            ran, failure = _maybe_run_index(
                job_stem,
                engine_name=index_engine,
                workdir=workdir,
                env=env,
                console=console,
                command=command,
            )
            if failure is not None:
                return failure
            if ran:
                ran_index = True
                forced_rerun = True

        if features.has_glossary and not ran_glossary:
            ran, failure = _maybe_run_glossaries(
                job_stem,
                workdir=workdir,
                env=env,
                console=console,
                command=command,
            )
            if failure is not None:
                return failure
            if ran:
                ran_glossary = True
                forced_rerun = True

        needs_rerun = forced_rerun or _log_requests_rerun(command.log_path)
        if not needs_rerun:
            break

        if pass_number == rerun_target:
            message = LatexMessage(
                severity=LatexMessageSeverity.ERROR,
                summary=f"Tectonic did not resolve references after {rerun_target} passes",
            )
            return EngineResult(
                returncode=1,
                messages=[message],
                command=command.argv,
                log_path=command.log_path,
                pdf_path=command.pdf_path,
            )

    assert last_result is not None
    return _stream_result_to_engine_result(last_result, command)


def _run_single_tectonic_pass(
    command: EngineCommand,
    *,
    workdir: Path,
    env: Mapping[str, str],
    console: Console,
    classic_output: bool,
) -> LatexStreamResult:
    if classic_output:
        process = subprocess.run(
            command.argv,
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
        return LatexStreamResult(returncode=process.returncode, messages=[])
    return run_tectonic_engine(
        command.argv,
        workdir=workdir,
        env=env,
        console=console,
    )


def _maybe_run_biber(
    job_stem: str,
    *,
    workdir: Path,
    env: Mapping[str, str],
    console: Console,
    command: EngineCommand,
) -> tuple[bool, EngineResult | None]:
    bcf_path = workdir / f"{job_stem}.bcf"
    if not bcf_path.exists():
        return False, None
    run = _invoke_auxiliary_tool(
        "biber",
        ["biber", job_stem],
        workdir=workdir,
        env=env,
        console=console,
    )
    if run.returncode != 0:
        return True, _tool_failure_result("biber", run, command=command)
    return True, None


def _maybe_run_index(
    job_stem: str,
    *,
    engine_name: str,
    workdir: Path,
    env: Mapping[str, str],
    console: Console,
    command: EngineCommand,
) -> tuple[bool, EngineResult | None]:
    index_path = workdir / f"{job_stem}.idx"
    if not index_path.exists():
        return False, None
    argv = [*_index_command_tokens(engine_name), index_path.name]
    run = _invoke_auxiliary_tool(
        argv[0],
        argv,
        workdir=workdir,
        env=env,
        console=console,
    )
    if run.returncode != 0:
        return True, _tool_failure_result(argv[0], run, command=command)
    return True, None


def _maybe_run_glossaries(
    job_stem: str,
    *,
    workdir: Path,
    env: Mapping[str, str],
    console: Console,
    command: EngineCommand,
) -> tuple[bool, EngineResult | None]:
    glo_path = workdir / f"{job_stem}.glo"
    acn_path = workdir / f"{job_stem}.acn"
    if not glo_path.exists() and not acn_path.exists():
        return False, None
    argv = [*_glossaries_command_tokens(), job_stem]
    run = _invoke_auxiliary_tool(
        argv[0],
        argv,
        workdir=workdir,
        env=env,
        console=console,
    )
    if run.returncode != 0:
        return True, _tool_failure_result(argv[0], run, command=command)
    return True, None


def _index_command_tokens(engine_name: str) -> list[str]:
    """Select an index command based on the requested engine."""
    if engine_name == "pyxindy":
        return pyxindy_index_tokens()
    if engine_name == "texindy":
        return ["texindy"]
    return [engine_name]


def _glossaries_command_tokens() -> list[str]:
    """Return the preferred makeglossaries command."""
    if pyxindy_available():
        return pyxindy_glossary_tokens()

    helper: Path | None = None
    try:
        helper = select_makeglossaries(console=None).path
    except Exception:
        helper = None

    if helper and helper.exists():
        return [str(helper)]
    return ["makeglossaries"]


def _log_requests_rerun(log_path: Path) -> bool:
    try:
        with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                lower = line.lower()
                if "rerunfilecheck" in lower:
                    continue
                if any(token in lower for token in _TECTONIC_RERUN_TOKENS):
                    return True
    except FileNotFoundError:
        return False
    return False


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
