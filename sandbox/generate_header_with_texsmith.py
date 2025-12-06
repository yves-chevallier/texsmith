#!/usr/bin/env python3
"""Generate a ucharclasses header using the TeXSmith font API."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from texsmith.fonts import FallbackManager, FontCache, FontPipelineLogger, UCharClassesBuilder


HERE = Path(__file__).parent
TEMPLATE_PATH = HERE / "latex_snippet.jinja"
FONTS_DIR = HERE / "fonts"


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


def parse_transition_macros(sty_path: Path) -> set[str]:
    content = sty_path.read_text(encoding="utf-8", errors="ignore")
    defined = set(re.findall(r"\\def\\setTransitionsFor([A-Za-z0-9]+)", content))
    groups = {
        f"setTransitionsFor{match}" for match in re.findall(r"\\doclass\{([A-Za-z0-9]+)\}", content)
    }
    return defined | groups


def render_header(entries: list[dict], *, available_macros: set[str]) -> str:
    from jinja2 import Environment, FileSystemLoader

    def is_latin_entry(entry: dict) -> bool:
        cls = (entry.get("class") or "").lower()
        group = (entry.get("group") or "").lower()
        return group == "latin" or cls.startswith("latin") or cls == "basiclatin"

    grouped: dict[str, dict] = {}

    def _prefer_new(group: str, existing: dict, candidate: dict) -> bool:
        """Decide if a candidate font is a better representative for a group."""
        has_bold_new = "bold" in candidate.get("styles", [])
        has_bold_old = "bold" in existing.get("styles", [])
        name_hits_group = group.lower() in (candidate.get("display_name") or "").lower()
        old_hits_group = group.lower() in (existing.get("display_name") or "").lower()
        if has_bold_new and not has_bold_old:
            return True
        if name_hits_group and not old_hits_group:
            return True
        return False

    for entry in entries:
        group = entry.get("group") or entry.get("class")
        font_meta = entry.get("font") or {}
        font_candidates = entry.get("fonts") or []
        font_name = font_meta.get("name") or (font_candidates[0] if font_candidates else None)
        if not font_name:
            continue
        base = font_base_name(font_name)
        ext = font_meta.get("extension", ".otf")
        candidate = {
            "display_name": font_name,
            "base": base,
            "extension": ext,
            "styles": [s.lower() for s in font_meta.get("styles", [])],
        }
        if group not in grouped or _prefer_new(group, grouped[group], candidate):
            grouped[group] = candidate

    fonts_for_template = []
    transitions: list[str] = []
    transition_classes: set[str] = set()  # package options to request
    group_to_cmd: dict[str, str] = {}
    for group, info in sorted(grouped.items()):
        if group.lower() == "latin":
            continue  # keep Latin on the main document font; no dedicated family.
        base = info["base"]
        ext = info["extension"]
        styles = info.get("styles", [])
        if not (FONTS_DIR / f"{base}-Regular{ext}").exists():
            # Gracefully fallback to the widely available NotoSans assets.
            base = "NotoSans"
            info["display_name"] = "NotoSans"
        wants_bold = "bold" in styles
        bold_present = wants_bold and style_available(base, "Bold", ext)
        cmd = sanitize_command(group)
        group_to_cmd[group] = cmd
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

    # Prefer group-level transitions when ucharclasses provides a helper macro.
    group_transitions_used: set[str] = set()
    for group, cmd in sorted(group_to_cmd.items()):
        macro = f"setTransitionsFor{group}"
        if macro not in available_macros:
            continue
        enter_cmd = "\\rmfamily" if group.lower() in {"latin", "diacritics"} else f"\\{cmd}"
        transitions.append(f"\\{macro}{{{enter_cmd}}}{{\\rmfamily}}%")
        transition_classes.add(group)
        group_transitions_used.add(group)

    # Transitions per class (fallback when no group macro is available).
    for entry in sorted(entries, key=lambda e: e.get("class", "")):
        cls = entry.get("class") or entry.get("group") or ""
        if not cls:
            continue
        group = entry.get("group") or cls
        if group in group_transitions_used:
            continue
        if group not in group_to_cmd:
            # Skip classes without a defined font (keep engine defaults).
            continue
        is_latin = is_latin_entry(entry)
        if is_latin:
            transitions.append(f"\\setTransitionsFor{{{cls}}}{{\\rmfamily}}{{\\rmfamily}}%")
            transition_classes.add(cls)
            continue
        cmd = group_to_cmd[group]
        transitions.append(f"\\setTransitionsFor{{{cls}}}{{\\{cmd}}}{{\\rmfamily}}%")
        transition_classes.add(cls)

    env = Environment(
        loader=FileSystemLoader(str(HERE)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(TEMPLATE_PATH.name)
    package_options = ",".join(sorted(transition_classes))
    rendered = template.render(
        package_options=package_options,
        fonts=fonts_for_template,
        transitions=transitions,
    )
    return rendered.strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère un header LaTeX avec les APIs TeXSmith.")
    parser.add_argument("input_tex", type=Path, help="Document LaTeX à analyser.")
    parser.add_argument(
        "-o", "--output", type=Path, default=HERE / "header.sty", help="Fichier de sortie."
    )
    parser.add_argument("--verbose", action="store_true", help="Affiche plus de détails.")
    args = parser.parse_args()

    logger = FontPipelineLogger(verbose=args.verbose)
    cache = FontCache()

    text = args.input_tex.read_text(encoding="utf-8")

    # Resolve fallback index lazily via the manager; it will build and cache if missing.
    summary = FallbackManager(cache=cache, logger=logger).scan_text(text)

    # Only need the sty path to discover available transition macros.
    sty_macros = parse_transition_macros(UCharClassesBuilder(cache=cache, logger=logger).sty_path())
    header = render_header(summary, available_macros=sty_macros)
    args.output.write_text(header, encoding="utf-8")
    logger.info(f"Header LaTeX écrit dans {args.output}")


if __name__ == "__main__":
    sys.exit(main())
