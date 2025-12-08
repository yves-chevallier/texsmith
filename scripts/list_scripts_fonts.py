"""Print detected scripts and fallback fonts for a given markdown/tex file using TeXSmith."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from texsmith.fonts.pipeline import FallbackManager

# Import pretty print for better output formatting
import pprint


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print scripts and fallback fonts detected by TeXSmith."
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("examples/dialects/dialects.md"),
        help="Input text/markdown file to analyze (default: examples/dialects/dialects.md).",
    )
    args = parser.parse_args()

    if not args.path.exists():
        sys.stderr.write(f"Input file not found: {args.path}\n")
        sys.exit(1)

    text = args.path.read_text(encoding="utf-8")
    manager = FallbackManager()
    summary = manager.scan_text(text)

    pprint.pprint(summary)


if __name__ == "__main__":
    main()
