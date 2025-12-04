"""Font source registry describing downloadable families and coverage."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from texsmith.fonts.cjk import CJK_BLOCK_OVERRIDES, CJK_FAMILY_SPECS, CJK_SCRIPT_ROWS
from texsmith.fonts.data import noto_dataset
from texsmith.fonts.utils import normalize_family


def _slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        else:
            cleaned.append("-")
    slug = "".join(cleaned)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "font"


@dataclass(frozen=True, slots=True)
class FontSourceSpec:
    """Describe how to download a font file plus its known coverage."""

    id: str
    family: str
    style: str
    url: str
    filename: str
    version: str | None = None
    zip_member: str | None = None
    alt_members: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    blocks: tuple[str, ...] = ()

    @property
    def cache_key(self) -> str:
        slug = _slugify(f"{self.family}-{self.style}")
        fingerprint = _slugify(self.version or "latest")
        return f"{slug}-{fingerprint}"


def _build_noto_sources() -> dict[str, tuple[FontSourceSpec, ...]]:
    blocks_by_script = noto_dataset.SCRIPT_BLOCKS
    family_styles: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: {"scripts": set(), "blocks": set(), "family": ""})
    )
    for script_id, _title, regular, bold, italic, bold_italic in noto_dataset.SCRIPT_FALLBACKS:
        for style_key, family_name in (
            ("regular", regular),
            ("bold", bold),
            ("italic", italic),
            ("bolditalic", bold_italic),
        ):
            if not family_name:
                continue
            normalized = normalize_family(family_name)
            bundle = family_styles[normalized][style_key]
            bundle["family"] = family_name
            bundle["scripts"].add(script_id)
            bundle["blocks"].update(blocks_by_script.get(script_id, ()))

    noto_sources: dict[str, tuple[FontSourceSpec, ...]] = {}
    for normalized, style_map in family_styles.items():
        specs: list[FontSourceSpec] = []
        for style_key, payload in sorted(style_map.items()):
            family_name = payload["family"]
            url = noto_dataset.build_cdn_url(
                family_name, style=style_key, build="full", flavor="otf"
            )
            filename = Path(urlparse(url).path).name
            specs.append(
                FontSourceSpec(
                    id=f"noto:{_slugify(family_name)}:{style_key}",
                    family=family_name,
                    style=style_key,
                    url=url,
                    filename=filename,
                    version="cdn-latest",
                    scripts=tuple(sorted(payload["scripts"])),
                    blocks=tuple(sorted(payload["blocks"])),
                )
            )
        noto_sources[normalized] = tuple(specs)
    return noto_sources


def _build_cjk_sources() -> dict[str, tuple[FontSourceSpec, ...]]:
    block_display = noto_dataset.BLOCK_DISPLAY_NAMES
    cjk_block_names: dict[str, tuple[str, ...]] = defaultdict(tuple)
    temp_map: dict[str, set[str]] = defaultdict(set)
    for block_name, script_id in CJK_BLOCK_OVERRIDES.items():
        display = block_display.get(block_name, block_name)
        temp_map[script_id].add(display)
    cjk_block_names = {key: tuple(sorted(values)) for key, values in temp_map.items()}

    specs_by_family: dict[str, list[FontSourceSpec]] = defaultdict(list)
    for family_name, spec in CJK_FAMILY_SPECS.items():
        normalized = normalize_family(family_name)
        style_dir = spec["style_dir"]
        region = spec["region"]
        weights = spec.get("weights", ("Regular",))
        for weight in weights:
            filename = f"{family_name}-{weight}.otf"
            style_key = "regular" if weight.lower() == "regular" else "bold"
            url = (
                "https://rawcdn.githack.com/notofonts/noto-cjk/main/"
                f"{style_dir}/OTF/{region}/{filename}"
            )
            scripts = tuple(
                row_id
                for row_id, row in CJK_SCRIPT_ROWS.items()
                if row[2] == family_name or row[3] == family_name
            )
            blocks: tuple[str, ...] = ()
            if scripts:
                block_sets = [set(cjk_block_names.get(script, ())) for script in scripts]
                combined: set[str] = set().union(*block_sets) if block_sets else set()
                blocks = tuple(sorted(combined))
            specs_by_family[normalized].append(
                FontSourceSpec(
                    id=f"cjk:{_slugify(family_name)}:{weight.lower()}",
                    family=family_name,
                    style=style_key,
                    url=url,
                    filename=filename,
                    version=f"{style_dir.lower()}-{region.lower()}",
                    scripts=scripts,
                    blocks=blocks,
                )
            )

    return {family: tuple(entries) for family, entries in specs_by_family.items()}


def _build_static_sources() -> dict[str, tuple[FontSourceSpec, ...]]:
    emoji_blocks = (
        "Emoticons",
        "Miscellaneous Symbols",
        "Miscellaneous Symbols and Pictographs",
        "Supplemental Symbols and Pictographs",
        "Symbols and Pictographs Extended-A",
        "Transport and Map Symbols",
    )
    openmoji = FontSourceSpec(
        id="emoji:openmoji-black:16.0.0",
        family="OpenMoji Black",
        style="regular",
        url="https://github.com/hfg-gmuend/openmoji/releases/download/16.0.0/openmoji-font.zip",
        filename="OpenMoji-black-glyf.ttf",
        zip_member="OpenMoji-black-glyf/OpenMoji-black-glyf.ttf",
        alt_members=("fonts/OpenMoji-black-glyf.ttf",),
        version="16.0.0",
        scripts=("symbols",),
        blocks=emoji_blocks,
    )
    noto_color_emoji = FontSourceSpec(
        id="emoji:noto-color",
        family="Noto Color Emoji",
        style="regular",
        url="https://github.com/googlefonts/noto-emoji/raw/refs/heads/main/fonts/NotoColorEmoji.ttf",
        filename="NotoColorEmoji.ttf",
        version="main",
        scripts=("symbols",),
        blocks=emoji_blocks,
    )
    plex_specs = [
        FontSourceSpec(
            id="ctan:ibm-plex-mono:regular",
            family="IBM Plex Mono",
            style="regular",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-Regular.otf",
            zip_member="plex/opentype/IBMPlexMono-Regular.otf",
            version="ctan",
        ),
        FontSourceSpec(
            id="ctan:ibm-plex-mono:bold",
            family="IBM Plex Mono",
            style="bold",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-Bold.otf",
            zip_member="plex/opentype/IBMPlexMono-Bold.otf",
            version="ctan",
        ),
        FontSourceSpec(
            id="ctan:ibm-plex-mono:italic",
            family="IBM Plex Mono",
            style="italic",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-Italic.otf",
            zip_member="plex/opentype/IBMPlexMono-Italic.otf",
            version="ctan",
        ),
        FontSourceSpec(
            id="ctan:ibm-plex-mono:bolditalic",
            family="IBM Plex Mono",
            style="bolditalic",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-BoldItalic.otf",
            zip_member="plex/opentype/IBMPlexMono-BoldItalic.otf",
            version="ctan",
        ),
        FontSourceSpec(
            id="ctan:ibm-plex-mono:medium",
            family="IBM Plex Mono",
            style="medium",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-Medium.otf",
            zip_member="plex/opentype/IBMPlexMono-Medium.otf",
            version="ctan",
        ),
    ]

    sources: dict[str, tuple[FontSourceSpec, ...]] = {
        normalize_family("OpenMoji Black"): (openmoji,),
        normalize_family("Noto Color Emoji"): (noto_color_emoji,),
        normalize_family("IBM Plex Mono"): tuple(plex_specs),
    }
    return sources


_SOURCE_MAP: dict[str, tuple[FontSourceSpec, ...]] = {}
_SOURCE_MAP.update(_build_noto_sources())
_SOURCE_MAP.update(_build_cjk_sources())
_SOURCE_MAP.update(_build_static_sources())


def known_families() -> Iterable[str]:
    """Return all family names available in the registry."""
    return sorted({spec.family for specs in _SOURCE_MAP.values() for spec in specs})


def sources_for_family(family: str) -> tuple[FontSourceSpec, ...]:
    """Return download specs for the given font family."""
    normalized = normalize_family(family)
    return _SOURCE_MAP.get(normalized, ())


__all__ = ["FontSourceSpec", "known_families", "sources_for_family"]
