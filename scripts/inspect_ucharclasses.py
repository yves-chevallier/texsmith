"""Inspect parsed ucharclasses data via TeXSmith."""

from __future__ import annotations

import argparse
from pprint import pprint

from texsmith.fonts.ucharclasses import UCharClassesBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description="Pretty-print parsed ucharclasses data.")
    parser.add_argument(
        "--group",
        type=str,
        help="Filter by group name (case-insensitive).",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Filter by class name (case-insensitive).",
    )
    args = parser.parse_args()

    builder = UCharClassesBuilder()
    classes = builder.build()

    filtered = []
    for cls in classes:
        if args.group and (not cls.group or args.group.lower() != cls.group.lower()):
            continue
        if args.name and args.name.lower() != cls.name.lower():
            continue
        filtered.append(cls)

    pprint([c.to_dict() | {"group": c.group} for c in filtered] if filtered else classes[:10])


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# ruff: noqa: T203
