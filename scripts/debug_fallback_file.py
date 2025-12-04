"""Inspect fallback mapping for a text file using the TeXSmith pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from texsmith.fonts.pipeline import FallbackManager, generate_ucharclasses_data


def class_hits(classes, codepoint: int) -> list[str]:
    hits: list[str] = []
    for cls in classes:
        if cls.start <= codepoint <= cls.end:
            group = cls.group or cls.name
            hits.append(f"{group}:{cls.name}")
    return hits


def fallback_hits(lookup, codepoint: int) -> list[str]:
    hits: list[str] = []
    for entry in lookup.index.ranges_for_codepoint(codepoint):
        group = entry.group or entry.name
        font = entry.font.get("name") if isinstance(entry.font, dict) else None
        hits.append(f"{group}:{entry.name}->{font}")
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug TeXSmith fallback mapping for a text file.")
    parser.add_argument("file", type=Path, help="Text/TeX file to inspect")
    parser.add_argument(
        "--strategy",
        choices=["by_class", "minimal_fonts"],
        default="minimal_fonts",
        help="Fallback planning strategy (default: minimal_fonts).",
    )
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"File not found: {args.file}")

    text = args.file.read_text(encoding="utf-8")
    classes = generate_ucharclasses_data()
    manager = FallbackManager()
    lookup = manager._ensure_lookup()

    unique_cps = sorted({ord(ch) for ch in text if ord(ch) > 0x20})

    print(f"# Fallback summary for {args.file}")
    plan = manager.scan_text(text, strategy=args.strategy)
    for entry in plan.summary:
        group = entry.get("group") or entry.get("class")
        font = entry.get("font", {}) if isinstance(entry.get("font"), dict) else {}
        font_name = font.get("name")
        ranges = ", ".join(entry.get("ranges", []))
        print(f"- {group}: font={font_name}, ranges={ranges}")

    print("\n# Per-codepoint mapping")
    for cp in unique_cps:
        ch = chr(cp)
        cls_hits = class_hits(classes, cp) or ["<none>"]
        fb_hits = fallback_hits(lookup, cp) or ["<none>"]
        print(f"0x{cp:04x} {ch!r}")
        print(f"  ucharclasses: {cls_hits}")
        print(f"  fallback:     {fb_hits}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# ruff: noqa: ANN001, SLF001, T201
