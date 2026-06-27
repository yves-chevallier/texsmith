"""Developer utilities for local workflows."""

from __future__ import annotations

from collections.abc import Sequence
import subprocess
import sys


def main(argv: Sequence[str] | None = None) -> int:
    """Run repository checks (currently proxies to ruff)."""
    args = list(argv) if argv is not None else sys.argv[1:]
    result = subprocess.run(
        ["ruff", "check", *args],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
