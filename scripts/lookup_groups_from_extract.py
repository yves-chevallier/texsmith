"""Lookup character groups from an extract file listing group ranges."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_extract(path: Path) -> list[tuple[str, int, int]]:
    groups: list[tuple[str, int, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        group = parts[0]
        for rng in parts[1:]:
            if "-" in rng:
                start_str, end_str = rng.split("-", 1)
            else:
                start_str = end_str = rng
            try:
                start = int(start_str, 16)
                end = int(end_str, 16)
            except ValueError:
                continue
            groups.append((group, start, end))
    return groups


def find_group(groups: list[tuple[str, int, int]], codepoint: int) -> list[str]:
    hits: list[str] = []
    for group, start, end in groups:
        if start <= codepoint <= end:
            hits.append(group)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find groups for given codepoints from extract.txt"
    )
    parser.add_argument(
        "input_file",
        type=Path,
        nargs="?",
        help="Optional file to scan for characters (prints groups for all chars)",
    )
    parser.add_argument(
        "--extract",
        type=Path,
        default=Path("extract.txt"),
        help="Path to extract file (defaults to extract.txt)",
    )
    parser.add_argument(
        "--codepoints",
        type=str,
        nargs="*",
        default=["0x8fd4", "0x0965", "0x5341"],
        help="Codepoints to lookup (hex, e.g., 0x8fd4)",
    )
    args = parser.parse_args()

    if not args.extract.exists():
        raise SystemExit(f"Extract file not found: {args.extract}")

    groups = parse_extract(args.extract)

    if args.input_file:
        if not args.input_file.exists():
            raise SystemExit(f"Input file not found: {args.input_file}")
        seen: set[int] = set()
        for ch in args.input_file.read_text(encoding="utf-8"):
            cp = ord(ch)
            if cp in seen or cp <= 0x20:
                continue
            seen.add(cp)
            hits = find_group(groups, cp)
            print(f"0x{cp:04x} {ch!r}: groups={hits or ['<none>']}")
    else:
        for cp_str in args.codepoints:
            try:
                cp = int(cp_str, 16)
            except ValueError:
                print(f"{cp_str}: invalid hex codepoint")
                continue
            hits = find_group(groups, cp)
            label = chr(cp) if cp <= 0x10FFFF else ""
            print(f"{cp_str} {label!r}: groups={hits or ['<none>']}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# ruff: noqa: T201
