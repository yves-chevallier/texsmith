#!/usr/bin/env python3
"""Extract unsupported font shapes from a LaTeX log file."""

from __future__ import annotations

import argparse
import pathlib
import re
from typing import Iterable, List, Optional, Tuple


WarningEntry = Tuple[Optional[int], str, Optional[str], str]


def parse_warnings(lines: Iterable[str]) -> List[WarningEntry]:
    """Parse LaTeX font warnings and return (line, missing, fallback, raw)."""
    entries: List[WarningEntry] = []
    lines_list = list(lines)
    i = 0
    prefix = "LaTeX Font Warning:"

    while i < len(lines_list):
        line = lines_list[i].rstrip()
        if not line.startswith(prefix):
            i += 1
            continue

        missing_shape = None
        m_missing = re.search(r"Font shape `([^']+)'", line)
        if m_missing:
            missing_shape = m_missing.group(1)

        fallback: Optional[str] = None
        src_line: Optional[int] = None

        if i + 1 < len(lines_list) and lines_list[i + 1].lstrip().startswith("(Font)"):
            follow = lines_list[i + 1].replace("(Font)", "", 1).strip()
            m_use = re.search(r"using `([^']+)' instead(?: on input line (\d+))?", follow)
            m_try = re.search(r"Font shape `([^']+)' tried instead on input line (\d+)", follow)
            m_line = re.search(r"on input line (\d+)", follow)

            if m_use:
                fallback = m_use.group(1)
                if m_use.group(2):
                    src_line = int(m_use.group(2))
            elif m_try:
                fallback = m_try.group(1)
                src_line = int(m_try.group(2))
            elif m_line:
                src_line = int(m_line.group(1))

            i += 1

        entries.append((src_line, missing_shape or "<unknown>", fallback, line))
        i += 1

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="List missing LaTeX font shapes.")
    parser.add_argument(
        "logfile",
        nargs="?",
        default="test.log",
        type=pathlib.Path,
        help="Path to a LaTeX log file (default: test.log)",
    )
    args = parser.parse_args()

    if not args.logfile.exists():
        raise SystemExit(f"Log file not found: {args.logfile}")

    entries = parse_warnings(args.logfile.read_text().splitlines())

    if not entries:
        print("No LaTeX font warnings found.")
        return

    seen = set()
    for src_line, missing, fallback, raw in entries:
        key = (src_line, missing, fallback)
        if key in seen:
            continue
        seen.add(key)
        location = f"line {src_line}" if src_line is not None else "line ?"
        replacement = f" -> {fallback}" if fallback else ""
        print(f"{location}: missing {missing}{replacement}")
        print(f"  {raw}")


if __name__ == "__main__":
    main()
