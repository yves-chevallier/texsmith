#!/usr/bin/env python3
"""Minimal CLI showcasing the counter extension built on texsmith."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_ROOT = PROJECT_ROOT / "examples"

for candidate in (EXAMPLES_ROOT, PROJECT_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from counter import main  # type: ignore  # noqa: E402


if __name__ == "__main__":  # pragma: no cover - convenience CLI
    main()
