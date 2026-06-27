"""Optional compilation of ``.typ`` sources to PDF.

Compilation is a graceful, best-effort helper: it never raises because a
toolchain is missing, so the ``.typ`` emission path never depends on a compiler
being installed.

Two compilation paths are supported, tried in this order:

1. The system ``typst`` binary resolved via ``PATH``.
2. The ``typst`` PyPI package (``pip install texsmith[typst]``), which embeds
   the Rust compiler and needs nothing on ``PATH``.

The system binary is preferred because it is the explicitly-installed,
user-controlled toolchain: it tracks the ``mitex`` math package's supported
Typst versions, whereas the embedded package floats to the latest release
(``typst>=0.15``) which can drop symbols ``mitex`` still emits (e.g. ``diff``
for ``\\partial``). The embedded package remains a zero-PATH fallback.

If neither is available the result carries an actionable message.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
import shutil
import subprocess


_MISSING_MESSAGE = (
    "no typst compiler available; .typ emitted but not compiled. "
    "Install the embedded compiler with `pip install texsmith[typst]` "
    "or provide the `typst` binary on PATH."
)


@dataclass(slots=True)
class TypstBuildResult:
    """Outcome of a Typst compilation."""

    ok: bool
    pdf_path: Path | None
    message: str


def _package_available() -> bool:
    """Whether the embedded ``typst`` Python package is importable."""
    return find_spec("typst") is not None


def _binary_path() -> str | None:
    """Path to the system ``typst`` binary, if any."""
    return shutil.which("typst")


def typst_available() -> bool:
    """Whether a Typst compiler is available via either path."""
    return _package_available() or _binary_path() is not None


def _compile_with_package(source: Path, pdf_path: Path) -> TypstBuildResult:
    """Compile via the embedded ``typst`` Python package."""
    import typst

    try:
        typst.compile(str(source), output=str(pdf_path))
    except typst.TypstError as exc:
        return TypstBuildResult(ok=False, pdf_path=None, message=f"typst compile failed:\n{exc}")
    return TypstBuildResult(ok=True, pdf_path=pdf_path, message=f"Compiled {pdf_path}")


def _compile_with_binary(binary: str, source: Path, pdf_path: Path) -> TypstBuildResult:
    """Compile via the system ``typst`` binary."""
    try:
        proc = subprocess.run(
            [binary, "compile", str(source), str(pdf_path)],
            capture_output=True,
            text=True,
        )
    except OSError as exc:  # pragma: no cover - defensive
        return TypstBuildResult(ok=False, pdf_path=None, message=f"typst compile failed: {exc}")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return TypstBuildResult(ok=False, pdf_path=None, message=f"typst compile failed:\n{detail}")
    return TypstBuildResult(ok=True, pdf_path=pdf_path, message=f"Compiled {pdf_path}")


def compile_typst(source: Path, *, output: Path | None = None) -> TypstBuildResult:
    """Compile ``source`` (.typ) to PDF using the first available compiler.

    Prefers the system ``typst`` binary (the mitex-compatible, user-controlled
    toolchain) and falls back to the embedded ``typst`` package. Returns a
    :class:`TypstBuildResult`; never raises for a missing compiler or a failed
    compilation (the caller decides how to surface the message).
    """
    pdf_path = output or source.with_suffix(".pdf")
    binary = _binary_path()
    if binary is not None:
        return _compile_with_binary(binary, source, pdf_path)
    if _package_available():
        return _compile_with_package(source, pdf_path)
    return TypstBuildResult(ok=False, pdf_path=None, message=_MISSING_MESSAGE)


__all__ = ["TypstBuildResult", "compile_typst", "typst_available"]
