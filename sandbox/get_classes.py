#!/usr/bin/env python3
"""
Lit un texte (stdin ou fichier) et retourne un JSON décrivant les classes Unicode
rencontrées, avec leurs groupes ucharclasses et les polices candidates.

Usage:
  cat test.tex | python get_classes.py > classes.json
  python get_classes.py --file test.tex > classes.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from lookup import NotoLookup

HERE = pathlib.Path(__file__).parent
CLASSES_PATH = HERE / "ucharclasses.json"


def load_groups() -> dict:
    """Mappe class name -> meta (group, font) depuis ucharclasses.json."""
    if not CLASSES_PATH.exists():
        return {}
    data = json.loads(CLASSES_PATH.read_text(encoding="utf-8"))
    return {entry["name"]: entry for entry in data}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract ucharclasses used in a text.")
    parser.add_argument("--file", type=pathlib.Path, help="Texte à analyser (sinon stdin).")
    args = parser.parse_args()

    if args.file:
        text = args.file.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            parser.error("Provide text via --file ou stdin")
        text = sys.stdin.read()

    lookup = NotoLookup(
        db_path=str(HERE / "noto_coverage_db.json"),
        cache_path=str(HERE / "noto_lookup.pkl"),
        classes_path=str(CLASSES_PATH),
        verbose=False,
    )
    lookup.lookup(text)
    classes = lookup.get_classes()
    meta = load_groups()

    out = []
    for cls, data in classes.items():
        entry_meta = meta.get(cls, {})
        group = entry_meta.get("group", cls)
        font_info = entry_meta.get("font", {})
        fonts = [f for f in data.get("fonts", []) if f]
        if not fonts and font_info.get("name"):
            fonts = [font_info["name"]]
        out.append(
            {
                "class": cls,
                "group": group,
                "fonts": fonts,
                "font": font_info,
                "ranges": data.get("ranges", []),
            }
        )

    sys.stdout.write(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
