#!/usr/bin/env python3
"""
Parse ucharclasses.sty and emit a JSON file listing each class with its Unicode ranges.
Output format: [{"name": "...", "start": int, "end": int, "start_hex": "U+XXXX", "end_hex": "U+YYYY"}, ...]
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Iterable, List, Tuple

HERE = pathlib.Path(__file__).parent
STY_PATH = HERE / "ucharclasses.sty"
OUT_PATH = HERE / "ucharclasses.json"


DO_PATTERN = re.compile(r"""\\do\{([^}]+)\}\{"?([0-9A-Fa-f]+)\}\{"?([0-9A-Fa-f]+)\}""")
GROUP_PATTERN = re.compile(r"""\\def\\([A-Za-z0-9]+)Classes\{""")
DO_NAME_PATTERN = re.compile(r"""\\do\{([^}]+)\}""")


def iter_class_ranges(text: str) -> Iterable[Tuple[str, int, int]]:
    """Yield (name, start, end) tuples from the sty content."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        for match in DO_PATTERN.finditer(line):
            name, start_hex, end_hex = match.groups()
            yield name, int(start_hex, 16), int(end_hex, 16)


def build() -> List[dict]:
    raw = STY_PATH.read_text(encoding="utf-8")
    seen = {}
    for name, start, end in iter_class_ranges(raw):
        # Keep the first occurrence for a class name if duplicates appear.
        seen.setdefault(
            name,
            {
                "name": name,
                "start": start,
                "end": end,
                "start_hex": f"U+{start:04X}",
                "end_hex": f"U+{end:04X}",
            },
        )

    # Map classes to their group (Latin, Arabic, Japanese, ...)
    # Some classes belong to multiple groups (e.g., CJK + Japanese/Korean).
    # Prefer the most specific group using a simple priority table.
    group_priority = {"Japanese": 3, "Korean": 3, "Chinese": 3, "CJK": 1}
    current_group = None
    for line in raw.splitlines():
        stripped = line.strip()
        m = GROUP_PATTERN.match(stripped)
        if m:
            current_group = m.group(1)
            continue
        if current_group and stripped.startswith("}"):
            current_group = None
            continue
        # "OtherClasses" is a catch-all list, not a real group for transitions;
        # keep those classes ungrouped so they fall back to their own name.
        if current_group and current_group not in ("All", "Other"):
            priority = group_priority.get(current_group, 2)
            for match in DO_NAME_PATTERN.finditer(stripped):
                cls = match.group(1)
                if cls in seen and "group" not in seen[cls]:
                    seen[cls]["group"] = current_group
                    seen[cls]["_priority"] = priority
                elif cls in seen:
                    prev = seen[cls].get("_priority", 0)
                    if priority > prev:
                        seen[cls]["group"] = current_group
                        seen[cls]["_priority"] = priority

    data = []
    for entry in seen.values():
        entry.pop("_priority", None)
        data.append(entry)

    data = sorted(data, key=lambda d: d["start"])
    OUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


if __name__ == "__main__":
    data = build()
    print(f"Wrote {len(data)} classes to {OUT_PATH}")
