#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from typing import Iterable

from texsmith.fonts.cache import FontCache
from texsmith.fonts.coverage import NotoCoverage, NotoCoverageBuilder
from texsmith.fonts.logging import FontPipelineLogger


def _parse_codepoint(raw: str) -> int:
    candidate = raw.strip()
    if len(candidate) == 1:
        return ord(candidate)
    if candidate.lower().startswith("u+"):
        candidate = candidate[2:]
    if candidate.lower().startswith("0x"):
        candidate = candidate[2:]
    hex_only = all(ch in "0123456789abcdefABCDEF" for ch in candidate)
    if hex_only or candidate.isdigit():
        base = 16 if hex_only else 10
        return int(candidate, base)
    # Fallback: use the first character when a literal string was provided.
    return ord(candidate[0])


def _covers(meta: NotoCoverage, codepoint: int) -> bool:
    for start, end in meta.ranges:
        if start <= codepoint <= end:
            return True
    return False


def _format_ranges(ranges: Iterable[tuple[int, int]]) -> str:
    parts: list[str] = []
    for start, end in ranges:
        if start == end:
            parts.append(f"U+{start:04X}")
        else:
            parts.append(f"U+{start:04X}-U+{end:04X}")
    return ", ".join(parts)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="List Noto font entries covering a given codepoint."
    )
    parser.add_argument("glyph", help="Glyph (literal char, U+XXXX, or hex codepoint).")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable progress logging when rebuilding coverage data.",
    )
    args = parser.parse_args(argv)

    codepoint = _parse_codepoint(args.glyph)
    logger = FontPipelineLogger(verbose=args.verbose)
    builder = NotoCoverageBuilder(cache=FontCache(), logger=logger)

    cached = builder.load_cached()
    if cached:
        dataset, source = cached
        logger.notice("Using cached coverage data from %s", source)
    else:
        dataset = builder.build()
        source = builder.cache_path

    matches = [entry for entry in dataset if _covers(entry, codepoint)]
    literal = chr(codepoint) if codepoint <= sys.maxunicode else "?"
    print(f"Codepoint: U+{codepoint:04X} ({literal})")
    print(f"Coverage source: {source}")
    if not matches:
        print("No Noto coverage entries mention this codepoint.")
        return 1

    for entry in sorted(matches, key=lambda e: e.family):
        # ranges = _format_ranges(entry.ranges)
        styles = ", ".join(entry.styles) if entry.styles else "regular"
        print(f"- {entry.family}")
        print(
            f"  file_base={entry.file_base} dir_base={entry.dir_base} styles={styles}"
        )
        # print(f"  ranges: {ranges}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
