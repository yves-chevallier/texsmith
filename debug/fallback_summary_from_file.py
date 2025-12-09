#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from pprint import pprint

from texsmith.fonts.logging import FontPipelineLogger
from texsmith.fonts.pipeline import FallbackManager
from texsmith.fonts.scripts import fallback_summary_to_usage


def _read_text(path: Path, encoding: str) -> str:
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        return path.read_text(encoding=encoding, errors="ignore")


def _append_token_codepoints(text: str) -> str:
    codepoints = []
    for match in re.finditer(r"U\+([0-9A-Fa-f]{2,6})", text):
        try:
            codepoints.append(int(match.group(1), 16))
        except ValueError:
            continue
    if not codepoints:
        return text
    return text + "".join(chr(cp) for cp in codepoints)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Build the fallback summary and script usage payload sent to ts-fonts."
    )
    parser.add_argument("path", type=Path, help="Path to the text file to scan.")
    parser.add_argument(
        "--encoding", default="utf-8", help="File encoding (default: utf-8)."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show logging while preparing fallback data.",
    )
    parser.add_argument(
        "--strategy",
        choices=["by_class", "minimal_fonts"],
        default="minimal_fonts",
        help="Fallback planning strategy (default: minimal_fonts).",
    )
    args = parser.parse_args(argv)

    text = _read_text(args.path, args.encoding)
    scan_text = _append_token_codepoints(text)

    logger = FontPipelineLogger(verbose=args.verbose)
    manager = FallbackManager(logger=logger)
    plan = manager.scan_text(scan_text, strategy=args.strategy)
    usage = fallback_summary_to_usage(plan)

    payload = {
        "strategy": plan.strategy,
        "fallback_summary": plan.summary,
        "fonts": plan.fonts,
        "uncovered": plan.uncovered,
        "script_usage": usage,
    }
    print(f"Scanned {args.path} ({len(scan_text)} chars)")
    pprint(payload, sort_dicts=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
