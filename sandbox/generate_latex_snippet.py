#!/usr/bin/env python3
"""
Analyse un texte, détermine les scripts rencontrés (via NotoLookup + ucharclasses.json)
et génère un extrait LaTeX prêt à l'emploi en utilisant le template Jinja
`latex_snippet.jinja`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Dict, List

from build_ucharclasses_json import build as build_ucharclasses
from lookup import NotoLookup

HERE = pathlib.Path(__file__).parent
TEMPLATE_PATH = HERE / "latex_snippet.jinja"


def sanitize_command(script_name: str) -> str:
    """Crée un nom de commande TeX simple à partir du nom de classe."""
    base = "".join(ch for ch in script_name if ch.isalnum())
    if not base:
        base = "Script"
    return base[0].lower() + base[1:] + "font"


def font_file_base(font_name: str) -> str:
    """Convertit un nom de famille (ex: 'Noto Sans Devanagari') en base de fichier (NotoSansDevanagari)."""
    return "".join(ch for ch in font_name if ch.isalnum())


def pick_available_font(fonts: List[str]) -> tuple[str, str] | tuple[None, None]:
    """Renvoie (font_name, file_base) pour la première font dont le fichier Regular existe dans ../fonts."""
    fonts_dir = (HERE / ".." / "fonts").resolve()
    for font in fonts:
        base = font_file_base(font)
        if (fonts_dir / f"{base}-Regular.otf").exists():
            return font, base
    return None, None


def merge_blocks(classes: Dict[str, dict]) -> tuple[str, str, List[str]]:
    font_blocks: List[str] = []
    transition_blocks: List[str] = []
    # Load class->group mapping from ucharclasses.json
    meta = json.loads((HERE / "ucharclasses.json").read_text(encoding="utf-8"))
    class_to_group = {entry["name"]: entry.get("group", entry["name"]) for entry in meta}

    grouped = {}
    for cls, data in classes.items():
        group = class_to_group.get(cls, cls)
        entry = grouped.setdefault(group, {"fonts": set(), "classes": []})
        entry["fonts"].update(data["fonts"])
        entry["classes"].append(cls)

    for group in sorted(grouped):
        data = grouped[group]
        if not data["fonts"]:
            continue
        font, file_base = pick_available_font(sorted(data["fonts"]))
        if not font:
            continue
        cmd = sanitize_command(group)
        font_block = (
            f"\\newfontfamily\\{cmd}[\n"
            f"  Path = fonts/,\n"
            f"  Extension = .otf,\n"
            f"  UprightFont = {file_base}-Regular,\n"
            f"  BoldFont = {file_base}-Bold,\n"
            f"  Scale = MatchLowercase\n"
            f"]{{{font}}}"
        )
        font_blocks.append(font_block)
        transition_blocks.append(f"\\setTransitionsFor{{{group}}}{{\\{cmd}}}{{\\rmfamily}}%")

    return "\n\n".join(font_blocks), "\n".join(transition_blocks), sorted(grouped)


def render_snippet(text: str) -> str:
    # Assure que le JSON des classes existe
    uchar_json = HERE / "ucharclasses.json"
    if not uchar_json.exists():
        build_ucharclasses()

    lookup = NotoLookup(
        db_path=str(HERE / "noto_coverage_db.json"),
        cache_path=str(HERE / "noto_lookup.pkl"),
        classes_path=str(uchar_json),
        verbose=False,
    )
    lookup.lookup(text)
    classes = lookup.get_classes()
    meta = json.loads((HERE / "ucharclasses.json").read_text(encoding="utf-8"))
    package_options = ",".join(
        sorted({entry.get("group", entry["name"]) for entry in meta if entry["name"] in classes})
    ) if classes else "Latin"
    font_blocks, transition_blocks, groups = merge_blocks(classes)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    opts = ",".join(groups) if groups else "Latin"
    snippet = (
        template.replace("{{ package_options }}", opts)
        .replace("{{ font_blocks }}", font_blocks)
        .replace("{{ transition_blocks }}", transition_blocks)
    )
    return snippet


def main():
    parser = argparse.ArgumentParser(description="Génère un extrait LaTeX (ucharclasses).")
    parser.add_argument(
        "text",
        nargs="?",
        help="Texte à analyser. Si absent, le contenu du fichier indiqué par --file ou stdin est utilisé.",
    )
    parser.add_argument("--file", type=pathlib.Path, help="Fichier texte à analyser.")
    args = parser.parse_args()

    if args.text is None:
        if args.file and args.file.exists():
            text = args.file.read_text(encoding="utf-8")
        elif not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            parser.error("Fournir un texte, un fichier avec --file ou du texte via stdin")
    else:
        text = args.text

    print(render_snippet(text))


if __name__ == "__main__":
    main()
