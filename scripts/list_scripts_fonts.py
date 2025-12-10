"""Print detected scripts and fallback fonts for a given markdown/tex file using TeXSmith."""

from __future__ import annotations

import argparse
from pathlib import Path

# Import pretty print for better output formatting
import pprint
import sys

from texsmith.fonts.pipeline import FallbackManager
from texsmith.fonts.scripts import fallback_summary_to_usage


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
    parser.add_argument(
        "--strategy",
        choices=["by_class", "minimal_fonts"],
        default="minimal_fonts",
        help="Fallback planning strategy (default: minimal_fonts).",
    )
    args = parser.parse_args()

    if not args.path.exists():
        sys.stderr.write(f"Input file not found: {args.path}\n")
        sys.exit(1)

    text = args.path.read_text(encoding="utf-8")
    manager = FallbackManager()
    plan = manager.scan_text(text, strategy=args.strategy)

    pprint.pprint(
        {
            "strategy": plan.strategy,
            "fallback_summary": plan.summary,
            "fonts": plan.fonts,
            "uncovered": plan.uncovered,
            "script_usage": fallback_summary_to_usage(plan),
        }
    )


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# ruff: noqa: T203
