"""Optional compilation of ``.typ`` sources to PDF via the ``typst`` binary.

This is a graceful, best-effort helper: if the ``typst`` executable is not on
``PATH`` it reports that compilation is unavailable rather than failing, so the
``.typ`` emission path never depends on a toolchain being installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass(slots=True)
class TypstBuildResult:
    """Outcome of a ``typst compile`` invocation."""

    ok: bool
    pdf_path: Path | None
    message: str


def typst_available() -> bool:
    """Whether the ``typst`` binary is on ``PATH``."""
    return shutil.which("typst") is not None


def compile_typst(source: Path, *, output: Path | None = None) -> TypstBuildResult:
    """Compile ``source`` (.typ) to PDF when the ``typst`` binary is present.

    Returns a :class:`TypstBuildResult`; never raises for a missing binary or a
    failed compilation (the caller decides how to surface the message).
    """
    binary = shutil.which("typst")
    if binary is None:
        return TypstBuildResult(
            ok=False,
            pdf_path=None,
            message="typst binary not found on PATH; .typ emitted but not compiled.",
        )
    pdf_path = output or source.with_suffix(".pdf")
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


__all__ = ["TypstBuildResult", "compile_typst", "typst_available"]
