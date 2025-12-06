#!/usr/bin/env python3
"""
Construit un header LaTeX à partir d'un classes.json (produit par get_classes.py).

Usage:
  python generate_latex_header.py classes.json > header.sty
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Dict, List


HERE = pathlib.Path(__file__).parent
VENDOR_DIR = HERE / "_vendor"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

from jinja2 import Environment, FileSystemLoader  # type: ignore


FONTS_DIR = HERE / "fonts"
# Groups that have helper macros \setTransitionsFor<Group> defined by ucharclasses.sty.
GROUP_TRANSITION_MACROS = {
    "Arabics",
    "CanadianSyllabics",
    "CherokeeFull",
    "Chinese",
    "CJK",
    "Cyrillics",
    "Devanagari",
    "Diacritics",
    "EgyptianHieroglyphsFull",
    "EthiopicFull",
    "GeorgianFull",
    "Greek",
    "Japanese",
    "Korean",
    "Latin",
    "Mathematics",
    "MongolianFull",
    "MyanmarFull",
    "Phonetics",
    "Punctuation",
    "SundaneseFull",
    "Symbols",
    "SyriacFull",
    "VedicMarks",
    "Yi",
    "Other",
}


def sanitize_command(name: str) -> str:
    base = "".join(ch for ch in name if ch.isalnum())
    if not base:
        base = "script"
    return base[0].lower() + base[1:] + "font"


def font_base_name(font: str) -> str:
    return "".join(ch for ch in font if ch.isalnum())


def style_available(base: str, style: str, ext: str) -> bool:
    fname = FONTS_DIR / f"{base}-{style.title()}{ext}"
    return fname.exists()


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère un header LaTeX depuis classes.json")
    parser.add_argument("classes_json", type=pathlib.Path, help="classes.json")
    args = parser.parse_args()

    data: list[dict] = json.loads(args.classes_json.read_text(encoding="utf-8"))

    # Regroupe par groupe (Latin, Arabic, etc.) et garde la première fonte vue
    grouped: dict[str, dict] = {}
    for entry in data:
        group = entry.get("group") or entry.get("class")
        font_meta = entry.get("font") or {}
        font_candidates = entry.get("fonts") or []
        font_name = font_meta.get("name") or (font_candidates[0] if font_candidates else None)
        if not font_name:
            continue

        base = font_base_name(font_meta.get("name") or font_name)
        ext = font_meta.get("extension", ".otf")

        if group not in grouped:
            grouped[group] = {
                "display_name": font_name,
                "base": base,
                "extension": ext,
                "styles": [s.lower() for s in font_meta.get("styles", [])],
            }

    options = sorted(grouped.keys())

    fonts_for_template = []
    transitions = []
    for group, info in sorted(grouped.items()):
        base = info["base"]
        ext = info["extension"]
        styles = info.get("styles", [])
        wants_bold = "bold" in styles
        bold_present = wants_bold and style_available(base, "Bold", ext)
        cmd = sanitize_command(group)
        fonts_for_template.append(
            {
                "cmd": cmd,
                "extension": ext,
                "upright": f"{base}-Regular",
                "bold": f"{base}-Bold" if bold_present else None,
                "fake_bold": wants_bold and not bold_present,
                "display_name": info["display_name"],
            }
        )
        if group == "Latin":
            transitions.append("\\setTransitionsForLatin{\\rmfamily}{}%")
        elif group in GROUP_TRANSITION_MACROS:
            transitions.append(f"\\setTransitionsFor{group}{{\\{cmd}}}{{\\rmfamily}}%")
        else:
            transitions.append(f"\\setTransitionsFor{{{group}}}{{\\{cmd}}}{{\\rmfamily}}%")

    package_options = ",".join(options)

    env = Environment(
        loader=FileSystemLoader(str(HERE)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("latex_snippet.jinja")
    rendered = template.render(
        package_options=package_options,
        fonts=fonts_for_template,
        transitions=transitions,
    )

    sys.stdout.write(rendered.strip() + "\n")


if __name__ == "__main__":
    main()
