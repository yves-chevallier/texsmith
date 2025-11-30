#!/usr/bin/env python3
"""Build the compact Noto dataset from the official sources."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
import io
import json
from pathlib import Path
import pprint
import re
import sys
from urllib.request import urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "src" / "texsmith" / "fonts" / "data" / "noto_dataset.py"
CTAN_ZIP_URL = "https://mirrors.ctan.org/macros/xetex/latex/ucharclasses.zip"
NOTO_JSON_URL = "https://notofonts.github.io/noto.json"
UNICODE_BLOCKS_URL = "http://www.unicode.org/Public/UNIDATA/Blocks.txt"


def download_bytes(url: str) -> bytes:
    with urlopen(url) as response:
        return response.read()


def fetch_ucharclasses_text() -> str:
    data = download_bytes(CTAN_ZIP_URL)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return zf.read("ucharclasses/ucharclasses.sty").decode("utf-8")


def fetch_noto_metadata() -> dict[str, object]:
    data = download_bytes(NOTO_JSON_URL)
    return json.loads(data.decode("utf-8"))


def fetch_unicode_blocks() -> list[tuple[int, int, str]]:
    data = download_bytes(UNICODE_BLOCKS_URL)
    rows: list[tuple[int, int, str]] = []
    for raw_line in data.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        range_part, name = line.split(";")
        start_str, end_str = range_part.strip().split("..")
        start = int(start_str, 16)
        end = int(end_str, 16)
        rows.append((start, end, name.strip()))
    return rows


def tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[0-9A-Za-z]+", text.lower()) if token]


def camel_case_tokens(name: str) -> list[str]:
    parts = re.findall(r"[A-Z][^A-Z]*|[0-9]+", name)
    return [part.lower() for part in parts]


def parse_ucharclasses(text: str) -> list[tuple[str, int, int, list[str]]]:
    pattern = re.compile(
        r"""\\do\{(?P<name>[^}]+)\}\{"(?P<start>[0-9A-F]+)\}\{"(?P<end>[0-9A-F]+)\}""",
        re.IGNORECASE,
    )
    results: list[tuple[str, int, int, list[str]]] = []
    for match in pattern.finditer(text):
        name = match.group("name")
        start = int(match.group("start"), 16)
        end = int(match.group("end"), 16)
        results.append((name, start, end, camel_case_tokens(name)))
    return results


def build_aliases(script_id: str, title: str) -> list[list[str]]:
    aliases: list[list[str]] = []
    slug_parts = [part for part in re.split(r"[-_]", script_id.lower()) if part]
    if slug_parts:
        aliases.append(slug_parts)
        if len(slug_parts) == 1:
            aliases.append([slug_parts[0]])
    clean_title = title
    if clean_title.lower().startswith("noto "):
        clean_title = clean_title[5:]
    for segment in re.split(r"[,&/]", clean_title):
        tokens = [token for token in tokenize(segment) if token != "noto"]
        if tokens:
            aliases.append(tokens)
            if len(tokens) == 1:
                aliases.append(tokens)
    seen = set()
    unique_aliases: list[list[str]] = []
    for alias in aliases:
        key = tuple(alias)
        if alias and key not in seen:
            unique_aliases.append(alias)
            seen.add(key)
    return unique_aliases


def find_script_for_class(
    block_tokens: Sequence[str], aliases: dict[str, list[list[str]]]
) -> str | None:
    token_set = set(block_tokens)
    matches: list[tuple[int, str]] = []
    for script_id, patterns in aliases.items():
        for alias in patterns:
            alias_set = set(alias)
            if alias_set and alias_set <= token_set:
                matches.append((len(alias_set), script_id))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    return matches[0][1]


def choose_family(families: dict[str, object]) -> tuple[str, dict[str, object]] | None:
    if not families:
        return None

    def family_score(name: str) -> tuple[int, str]:
        lower = name.lower()
        if "sans" in lower:
            return (0, name)
        if "serif" in lower:
            return (1, name)
        return (2, name)

    best = min(families.keys(), key=family_score)
    return best, families[best]


def extract_style_from_path(path: str) -> str:
    filename = path.split("/")[-1]
    stem, _dot, _ext = filename.rpartition(".")
    family_dir = path.split("/")[1] if "/" in path else ""
    suffix = ""
    if family_dir and stem.startswith(family_dir):
        suffix = stem[len(family_dir) :]
    if not suffix and "-" in stem:
        suffix = stem.split("-", 1)[1]
    suffix = suffix.lstrip("-_")
    return suffix or "Regular"


def available_styles(family_data: dict[str, object]) -> dict[str, bool]:
    files: list[str] = []
    for entries in family_data.get("files", {}).values():
        files.extend(entries)
    availability = dict.fromkeys(("Regular", "Bold", "Italic", "BoldItalic"), False)
    for path in files:
        style = extract_style_from_path(path)
        if style in availability:
            availability[style] = True
    return availability


def build_dataset() -> dict[str, object]:
    uchar_text = fetch_ucharclasses_text()
    classes = parse_ucharclasses(uchar_text)
    noto_data = fetch_noto_metadata()
    unicode_block_rows = fetch_unicode_blocks()
    unicode_by_range = {(start, end): name for start, end, name in unicode_block_rows}
    alias_map = {
        script_id: build_aliases(script_id, info["title"]) for script_id, info in noto_data.items()
    }
    language_rows: list[tuple[str, int, int, str | None]] = []
    script_rows: dict[str, tuple[str, str, str | None, str | None, str | None, str | None]] = {}
    unicode_blocks: list[tuple[str, int, int, str | None]] = []
    block_display_names: dict[str, str] = {}
    script_block_map: dict[str, set[str]] = defaultdict(set)
    for name, start, end, tokens in classes:
        script_id = find_script_for_class(tokens, alias_map)
        language_rows.append((name, start, end, script_id))
        display_name = unicode_by_range.get((start, end))
        if display_name is None:
            parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|[0-9]+", name)
            display_name = " ".join(parts)
        block_display_names[name] = display_name
        unicode_blocks.append((display_name, start, end, script_id))
        if script_id:
            script_block_map[script_id].add(display_name)
        if script_id and script_id not in script_rows:
            script_info = noto_data[script_id]
            preferred = choose_family(script_info.get("families", {}))
            if preferred:
                family_name, family_data = preferred
                styles = available_styles(family_data)
            else:
                family_name = None
                styles = dict.fromkeys(("Regular", "Bold", "Italic", "BoldItalic"), False)
            script_rows[script_id] = (
                script_id,
                script_info["title"],
                family_name if styles["Regular"] else None,
                family_name if styles["Bold"] else None,
                family_name if styles["Italic"] else None,
                family_name if styles["BoldItalic"] else None,
            )
    language_rows.sort(key=lambda row: row[0])
    script_table = [script_rows[key] for key in sorted(script_rows)]
    for key in script_rows:
        script_block_map.setdefault(key, set())
    script_block_entries = {
        key: tuple(sorted(values)) for key, values in sorted(script_block_map.items())
    }
    return {
        "languages": language_rows,
        "scripts": script_table,
        "unicode_blocks": unicode_blocks,
        "block_display_names": block_display_names,
        "script_blocks": script_block_entries,
    }


def main() -> None:
    dataset = build_dataset()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        handle.write("# Auto-generated by generate_noto_dataset.py\n")
        handle.write("# Compact Unicode block to Noto script lookup tables.\n")
        handle.write("from array import array\n")
        handle.write("import re\n")
        handle.write("from typing import Iterable\n\n")
        handle.write("MAX_CODEPOINT = 0x110000\n\n")
        handle.write("LanguageRow = tuple[str, int, int, str | None]\n")
        handle.write(
            "ScriptRow = tuple[str, str, str | None, str | None, str | None, str | None]\n\n"
        )
        handle.write("LANGUAGE_RANGES = ")
        handle.write(pprint.pformat(dataset["languages"], sort_dicts=False))
        handle.write("\n\n")
        handle.write("SCRIPT_FALLBACKS = ")
        handle.write(pprint.pformat(dataset["scripts"], sort_dicts=False))
        handle.write("\n\n")
        handle.write("UNICODE_BLOCKS = ")
        handle.write(pprint.pformat(dataset["unicode_blocks"], sort_dicts=False))
        handle.write("\n\n")
        handle.write("BLOCK_DISPLAY_NAMES = ")
        handle.write(pprint.pformat(dataset["block_display_names"], sort_dicts=False))
        handle.write("\n\n")
        handle.write("SCRIPT_BLOCKS = ")
        handle.write(pprint.pformat(dataset["script_blocks"], sort_dicts=False))
        handle.write(
            "\n\n"
            "def build_lookup_tables(\n"
            "    language_rows: Iterable[LanguageRow],\n"
            "    script_rows: Iterable[ScriptRow],\n"
            ") -> tuple[\n"
            "    dict[str, tuple[int, int, ScriptRow | None]],\n"
            "    dict[str, ScriptRow],\n"
            "]:\n"
            '    """Return dictionaries for O(1) lookups by language or script id."""\n'
            "    script_map: dict[str, ScriptRow] = {row[0]: row for row in script_rows}\n"
            "    language_map: dict[str, tuple[int, int, ScriptRow | None]] = {}\n"
            "    for name, start, end, script_id in language_rows:\n"
            "        language_map[name] = (start, end, script_map.get(script_id))\n"
            "    return language_map, script_map\n\n"
            "def build_codepoint_table(\n"
            "    language_rows: Iterable[LanguageRow] = LANGUAGE_RANGES,\n"
            ") -> array:\n"
            "    table = array('H', [0]) * MAX_CODEPOINT\n"
            "    for idx, (_name, start, end, _script_id) in enumerate(language_rows, start=1):\n"
            "        upper = min(end, MAX_CODEPOINT - 1)\n"
            "        lower = max(0, start)\n"
            "        for codepoint in range(lower, upper + 1):\n"
            "            table[codepoint] = idx\n"
            "    return table\n\n"
            "_STYLE_SUFFIX = {\n"
            '    "regular": "Regular",\n'
            '    "bold": "Bold",\n'
            '    "italic": "Italic",\n'
            '    "bolditalic": "BoldItalic",\n'
            "}\n\n"
            "def build_cdn_url(\n"
            "    family_name: str,\n"
            '    style: str = "regular",\n'
            '    build: str = "full",\n'
            '    flavor: str = "otf",\n'
            ") -> str:\n"
            '    """Construct the CDN URL for a given Noto family and style."""\n'
            "    style_key = _STYLE_SUFFIX.get(style.lower(), style)\n"
            '    family_dir = re.sub(r"[^0-9A-Za-z]", "", family_name)\n'
            '    filename = f"{family_dir}-{style_key}.{flavor}"\n'
            "    return (\n"
            '        "https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io/fonts/"\n'
            '        f"{family_dir}/{build}/{flavor}/{filename}"\n'
            "    )\n"
        )
    sys.stdout.write(f"Wrote dataset with {len(dataset['languages'])} entries to {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
