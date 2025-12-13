"""Minimal TexSmith conversion on a temp markdown snippet.

Creates a temporary markdown file with a Mermaid diagram and runs the TexSmith
CLI to generate a PDF. Useful to isolate conversion-only issues.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


SNIPPET = """# Tiny Mermaid test

```mermaid
graph TD; A-->B;
```
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = Path(tmpdir) / "snippet.md"
        md_path.write_text(SNIPPET, encoding="utf-8")
        output_dir = Path(tmpdir) / "out"
        cmd = [
            "texsmith",
            str(md_path),
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
            capture_output=True,
            text=True,
            timeout=300,
        )
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
