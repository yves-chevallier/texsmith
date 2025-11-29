"""Runtime helpers for latexmk builds."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from rich.console import Console

from .log import LatexStreamResult, stream_latexmk_output


def run_latex_engine(
    argv: Sequence[str],
    *,
    workdir: Path,
    env: Mapping[str, str],
    console: Console,
    verbosity: int = 0,
) -> LatexStreamResult:
    """Execute a latexmk command and stream structured output."""
    return stream_latexmk_output(
        argv,
        cwd=str(workdir),
        env=env,
        console=console,
        verbosity=verbosity,
    )
