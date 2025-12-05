#!/usr/bin/env python3
"""
Enrichit ucharclasses.json avec la police Noto la plus couvrante pour chaque bloc.
La sélection se fait en maximisant l'intersection entre le range de la classe
et les ranges de chaque famille dans noto_coverage_db.json.
"""
from __future__ import annotations

import json
import pathlib
from typing import Dict, List, Tuple

HERE = pathlib.Path(__file__).parent
UCHAR_PATH = HERE / "ucharclasses.json"
DB_PATH = HERE / "noto_coverage_db.json"


def sanitize_family(name: str) -> str:
    """Convertit un nom de famille en base de fichier (NotoSansCJKsc)."""
    return "".join(ch for ch in name if ch.isalnum())


def load_db() -> Dict[str, dict]:
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    output = {}
    for entry in db:
        family = entry["family"]
        output[family] = {
            "ranges": [(r[0], r[1]) for r in entry.get("ranges", [])],
            "styles": entry.get("otf_styles", []),
            "file_base": entry.get("file_base") or sanitize_family(family),
            "dir_base": entry.get("dir_base") or entry.get("file_base") or sanitize_family(family),
        }
    return output


def overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    lo = max(a_start, b_start)
    hi = min(a_end, b_end)
    return max(0, hi - lo + 1)


def pick_font(class_range: Tuple[int, int], db_ranges: Dict[str, dict]) -> dict | None:
    best = None
    best_score = 0
    for family, meta in db_ranges.items():
        ranges = meta.get("ranges", [])
        score = 0
        for r_start, r_end in ranges:
            score += overlap(class_range[0], class_range[1], r_start, r_end)
        if score > best_score:
            best_score = score
            best = {"family": family, **meta}
    return best


def main() -> None:
    classes = json.loads(UCHAR_PATH.read_text(encoding="utf-8"))
    db_ranges = load_db()

    for entry in classes:
        start = entry.get("start")
        end = entry.get("end")
        if start is None or end is None:
            continue
        font_name = pick_font((int(start), int(end)), db_ranges)
        if not font_name:
            # fallback heuristique: tenter NotoSans+ClassName
            fallback_name = sanitize_family(f"NotoSans{entry['name']}")
            styles = ["regular", "bold"]
            entry["font"] = {
                "name": fallback_name,
                "extension": ".otf",
                "styles": styles,
            }
        else:
            styles = font_name.get("styles") or ["regular", "bold"]
            entry["font"] = {
                "name": font_name.get("file_base") or sanitize_family(font_name["family"]),
                "extension": ".otf",
                "styles": styles,
                "dir": font_name.get("dir_base"),
            }

    UCHAR_PATH.write_text(json.dumps(classes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated fonts for {len(classes)} classes in {UCHAR_PATH}")


if __name__ == "__main__":
    main()
