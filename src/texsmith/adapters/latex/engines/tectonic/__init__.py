"""Runtime helpers for invoking the Tectonic engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import subprocess

from rich.console import Console

from ..latex import LatexStreamResult


def run_tectonic_engine(
    argv: Sequence[str],
    *,
    workdir: Path,
    env: Mapping[str, str],
    console: Console,
) -> LatexStreamResult:
    """Execute a tectonic command, streaming plain output."""
    with subprocess.Popen(
        argv,
        cwd=str(workdir),
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            console.print(line.rstrip())
        returncode = process.wait()

    return LatexStreamResult(returncode=returncode, messages=[])
