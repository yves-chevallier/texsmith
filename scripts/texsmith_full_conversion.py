"""Run a full TexSmith conversion on the diagrams example (CLI path).

This script exists to reproduce CI issues deterministically. It invokes the
TexSmith CLI to render examples/diagrams/diagrams.md using the same arguments
as the Makefile (tectonic engine, build enabled, playwright backend).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = repo_root / "examples" / "build" / "ci-diagrams"
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "texsmith",
        "examples/diagrams/diagrams.md",
        "-tarticle",
        f"-o{output_dir}",
        "--build",
        "--engine=tectonic",
        "--diagrams-backend",
        "playwright",
        "--debug",
    ]
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
