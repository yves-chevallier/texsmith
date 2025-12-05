#!/usr/bin/env python3
"""
Télécharge les polices nécessaires en fonction du fichier classes.json produit par get_classes.py.

Usage:
  python get_fonts.py classes.json --outdir=fonts/
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Dict, Tuple

HERE = pathlib.Path(__file__).parent

# Some Google Fonts family names don't match the actual file names hosted in noto-cjk.
# Map those "friendly" names to the real downloadable base names and their subdirectory.
CJK_ALIASES = {
    "NotoSansJP": ("NotoSansCJKjp", "Sans/OTF/Japanese/"),
    "NotoSansKR": ("NotoSansCJKkr", "Sans/OTF/Korean/"),
    "NotoSansSC": ("NotoSansCJKsc", "Sans/OTF/SimplifiedChinese/"),
    "NotoSansTC": ("NotoSansCJKtc", "Sans/OTF/TraditionalChinese/"),
    "NotoSansHK": ("NotoSansCJKhk", "Sans/OTF/TraditionalChineseHK/"),
}


STYLE_SUFFIXES = {
    "regular": "Regular",
    "italic": "Italic",
    "bold": "Bold",
    "bolditalic": "BoldItalic",
}


def font_base_name(name: str) -> str:
    """Supprime espaces et tirets pour obtenir la base fichier."""
    return "".join(ch for ch in name if ch.isalnum())


def download_with_fallback(filename: str, dest: pathlib.Path, dir_base: str | None) -> bool:
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)

    base = filename_base(filename)

    # Try noto-cjk aliases first when the friendly family name differs from the actual files.
    if base in CJK_ALIASES:
        real_base, rel_dir = CJK_ALIASES[base]
        real_filename = filename.replace(base, real_base, 1)
        cjk_url = f"https://raw.githubusercontent.com/notofonts/noto-cjk/main/{rel_dir}{real_filename}"
        if fetch(cjk_url, dest):
            return True

    # Essai 1 : CDN notofonts.github.io (structure unhinted/otf)
    dir_part = dir_base or filename_base(filename)
    cdn_url = f"https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io/fonts/{dir_part}/unhinted/otf/{filename}"
    if fetch(cdn_url, dest):
        return True
    # Essai 2 : raw sur notofonts.github.io
    raw_url = f"https://raw.githubusercontent.com/notofonts/notofonts.github.io/master/fonts/{dir_part}/unhinted/otf/{filename}"
    if fetch(raw_url, dest):
        return True
    # Essai 2b : raw avec full/otf
    raw_full_url = f"https://raw.githubusercontent.com/notofonts/notofonts.github.io/master/fonts/{dir_part}/full/otf/{filename}"
    if fetch(raw_full_url, dest):
        return True
    # Essai 3 : dépôt noto-cjk si CJK
    if "CJK" in filename:
        cjk_url = f"https://raw.githubusercontent.com/notofonts/noto-cjk/main/{guess_cjk_path(filename)}{filename}"
        if fetch(cjk_url, dest):
            return True
    return dest.exists()


def filename_base(filename: str) -> str:
    return filename.split("-")[0]


def guess_cjk_path(filename: str) -> str:
    base = filename_base(filename)
    if base in CJK_ALIASES:
        return CJK_ALIASES[base][1]

    # Fallback for already CJK-prefixed names
    lowered = base.lower()
    if "cjkjp" in lowered:
        return "Sans/OTF/Japanese/"
    if "cjkkr" in lowered:
        return "Sans/OTF/Korean/"
    if "cjksc" in lowered:
        return "Sans/OTF/SimplifiedChinese/"
    if "cjktc" in lowered:
        return "Sans/OTF/TraditionalChinese/"
    if "cjkhk" in lowered:
        return "Sans/OTF/TraditionalChineseHK/"
    return ""


def fetch(url: str, dest: pathlib.Path) -> bool:
    try:
        res = subprocess.run(["curl", "-L", "-f", "-o", str(dest), url], check=False, capture_output=True)
        if res.returncode != 0:
            return False
        # If download yielded an HTML or very small file, treat as failure
        if dest.exists() and dest.stat().st_size < 1024:
            dest.unlink(missing_ok=True)
            return False
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Télécharge les polices nécessaires.")
    parser.add_argument("classes_json", type=pathlib.Path, help="Fichier classes.json")
    parser.add_argument("--outdir", type=pathlib.Path, default=pathlib.Path("fonts"), help="Dossier de sortie")
    args = parser.parse_args()

    classes = json.loads(args.classes_json.read_text(encoding="utf-8"))

    # Prépare une liste dédupliquée de fichiers à récupérer
    tasks = []
    seen = set()
    for entry in classes:
        font = entry.get("font", {})
        name = font.get("name")
        ext = font.get("extension", ".otf")
        styles = font.get("styles", [])
        if not name or not styles:
            continue
        for style in styles:
            suffix = STYLE_SUFFIXES.get(style.lower(), style.title())
            filename = f"{name}-{suffix}{ext}"
            dest = args.outdir / filename
            key = (filename, dest)
            if key not in seen:
                dir_base = font.get("dir")
                tasks.append((filename, dest, style, ext, name, dir_base))
                seen.add(key)

    total = len(tasks)
    for idx, (filename, dest, style, ext, name, dir_base) in enumerate(tasks, start=1):
        prefix = f"[{idx}/{total}]"
        if dest.exists():
            print(f"{prefix} {filename} déjà présent")
            continue

        print(f"{prefix} Téléchargement de {filename}...")
        ok = download_with_fallback(filename, dest, dir_base)
        if ok:
            print(f"{prefix} {filename} OK")
            continue

        if name != "NotoSans":
            fallback_name = "NotoSans"
            fallback_file = f"{fallback_name}-{style.title()}{ext}"
            fallback_dest = args.outdir / fallback_file
            print(f"{prefix} {filename} introuvable, tentative fallback {fallback_file}...")
            ok = download_with_fallback(fallback_file, fallback_dest, None)
            if ok:
                print(f"{prefix} fallback {fallback_file} OK")
            else:
                print(f"{prefix} Échec téléchargement {filename} et fallback {fallback_file}", file=sys.stderr)
        else:
            print(f"{prefix} Échec téléchargement {filename}", file=sys.stderr)


if __name__ == "__main__":
    main()
