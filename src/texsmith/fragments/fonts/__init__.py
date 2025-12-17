from __future__ import annotations

from collections.abc import Mapping
import contextlib
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, ClassVar
import urllib.request
import warnings
import zipfile

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec, TemplateError
from texsmith.core.user_dir import get_user_dir
from texsmith.fonts.cache import FontCache
from texsmith.fonts.constants import style_suffix
from texsmith.fonts.downloader import NotoFontDownloader
from texsmith.fonts.logging import FontPipelineLogger


_FAMILY_CHOICES: dict[str, str] = {
    "lm": "lm",
    "lm-sans": "lm-sans",
    "bonum": "bonum",
    "libertinus": "libertinus",
    "pagella": "pagella",
    "termes": "termes",
    "schola": "schola",
    "heros": "heros",
    "heros-otf": "heros",
    "adventor": "adventor",
    "adventor-otf": "adventor",
    "cursor": "cursor",
    "cursor-otf": "cursor",
    "plex": "plex",
    "pennstander": "pennstander",
}

_CTAN_DEPENDENCIES: dict[str, dict[str, str]] = {
    "bonum": {
        "package": "bonum-otf",
        "url": "https://mirrors.ctan.org/fonts/bonum-otf.zip",
    },
    "pagella": {
        "package": "pagella-otf",
        "url": "https://mirrors.ctan.org/fonts/pagella-otf.zip",
    },
    "termes": {
        "package": "termes-otf",
        "url": "https://mirrors.ctan.org/fonts/termes-otf.zip",
    },
    "schola": {
        "package": "schola-otf",
        "url": "https://mirrors.ctan.org/fonts/schola-otf.zip",
    },
    "heros": {
        "package": "heros-otf",
        "url": "https://mirrors.ctan.org/fonts/heros-otf.zip",
    },
    "adventor": {
        "package": "adventor-otf",
        "url": "https://mirrors.ctan.org/fonts/tex-gyre.zip",
    },
    "cursor": {
        "package": "cursor-otf",
        "url": "https://mirrors.ctan.org/fonts/tex-gyre.zip",
    },
    "plex": {
        "package": "plex-otf",
        "url": "https://mirrors.ctan.org/fonts/plex-otf.zip",
    },
    "pennstander": {
        "package": "pennstander-otf",
        "url": "https://mirrors.ctan.org/fonts/pennstander-otf.zip",
    },
}

_PLEX_URL = "https://github.com/IBM/plex/releases/download/v6.0.0/TrueType.zip"
_OPENMOJI_URL = "https://github.com/hfg-gmuend/openmoji/releases/latest/download/openmoji-font.zip"
_OPENMOJI_FILE_CANDIDATES = {
    "OpenMoji-black-glyf.ttf",
    "OpenMoji-black-glyf/OpenMoji-black-glyf.ttf",
    "fonts/OpenMoji-black-glyf.ttf",
}
_NOTO_COLOR_EMOJI_URL = (
    "https://github.com/googlefonts/noto-emoji/raw/refs/heads/main/fonts/NotoColorEmoji.ttf"
)
_SKIP_GROUPS = {"latin", "common", "punctuation", "other"}
_FALLBACK_ALIASES: dict[str, dict[str, object]] = {
    # Prefer widely available Noto families when coverage picks display variants.
    "cyrillics": {"name": "NotoSans", "styles": ["regular", "bold"], "extension": ".otf"},
    "diacritics": {"name": "NotoSans", "styles": ["regular", "bold"], "extension": ".otf"},
    "devanagari": {
        "name": "NotoSansDevanagari",
        "styles": ["regular", "bold"],
        "extension": ".otf",
        "dir": "NotoSansDevanagari",
    },
    "chinese": {"name": "NotoSansSC", "styles": ["regular", "bold"], "extension": ".otf"},
    "symbols": {
        "name": "OpenMojiBlack",
        "styles": ["regular"],
        "extension": ".ttf",
    },
}


def _resolve_emoji_mode(context: Mapping[str, Any]) -> str:
    """Infer requested emoji mode from template or press settings."""
    candidates: list[Any] = []
    fonts_cfg = context.get("fonts")
    if isinstance(context.get("emoji"), str):
        candidates.append(context.get("emoji"))
    if isinstance(context.get("emoji_mode"), str):
        candidates.append(context.get("emoji_mode"))
    if isinstance(fonts_cfg, Mapping) and isinstance(fonts_cfg.get("emoji"), str):
        candidates.append(fonts_cfg.get("emoji"))
    for value in candidates:
        lowered = str(value).strip().lower()
        if lowered in {"artifact", "symbola", "color", "black", "twemoji"}:
            return lowered
    return "black"


def _normalise_family(raw_value: Any) -> str:
    if isinstance(raw_value, str):
        candidate = raw_value.strip().lower()
        if candidate:
            mapped = _FAMILY_CHOICES.get(candidate)
            if mapped:
                return mapped
            warnings.warn(f"Unknown font family '{raw_value}', falling back to 'lm'.", stacklevel=3)
    return "lm"


def _sty_available(sty_name: str) -> bool:
    kpse = shutil.which("kpsewhich")
    if not kpse:
        return False
    try:
        result = subprocess.run(
            [kpse, sty_name],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _download_archive(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    try:
        with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except OSError as exc:
        raise TemplateError(f"Failed to download '{url}': {exc}") from exc


def _extract_sty_from_archive(archive: Path, sty_name: str, target: Path) -> Path:
    with zipfile.ZipFile(archive) as zf:
        for entry in zf.infolist():
            if entry.is_dir():
                continue
            if Path(entry.filename).name != sty_name:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(entry) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            return target
    raise TemplateError(f"Could not locate '{sty_name}' inside '{archive.name}'.")


def _write_stub_package(package_name: str, family: str, target: Path) -> Path:
    fonts: dict[str, str] = {
        "bonum": "TeX Gyre Bonum",
        "pagella": "TeX Gyre Pagella",
        "termes": "TeX Gyre Termes",
        "schola": "TeX Gyre Schola",
        "heros": "TeX Gyre Heros",
        "adventor": "TeX Gyre Adventor",
        "cursor": "TeX Gyre Cursor",
        "plex": "IBM Plex Serif",
        "pennstander": "Latin Modern Roman",
    }
    font_name = fonts.get(family, family)
    lines = [
        f"\\ProvidesPackage{{{package_name}}}[Auto-generated stub]",
        "\\RequirePackage{fontspec}",
        f"\\setmainfont{{{font_name}}}",
    ]
    if family in {"heros", "adventor"}:
        lines.append(f"\\setsansfont{{{font_name}}}")
    if family == "cursor":
        lines.append(f"\\setmonofont{{{font_name}}}")
    if family in {"bonum", "pagella", "termes"}:
        lines.append(f"\\setmathfont{{{font_name} Math}}")
    if family == "pennstander":
        lines.append("\\setsansfont{Latin Modern Sans}")
        lines.append("\\setmonofont{Latin Modern Mono}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _ensure_noto_color_emoji(cache: FontCache) -> Path | None:
    """Download the Noto Color Emoji font (TTF) into the cache."""
    dest = cache.path("NotoColorEmoji.ttf")
    if dest.exists():
        return dest
    try:
        _download_archive(_NOTO_COLOR_EMOJI_URL, dest)
    except Exception as exc:  # pragma: no cover - network edge
        warnings.warn(f"Unable to download Noto Color Emoji font: {exc}", stacklevel=2)
        return None
    return dest if dest.exists() else None


def _ensure_openmoji_black(cache: FontCache) -> Path | None:
    """Download and extract the OpenMoji black glyph font into the cache."""
    dest = cache.path("OpenMoji-black-glyf.ttf")
    if dest.exists():
        return dest
    with cache.tempdir() as tmp_dir:
        archive = tmp_dir / "openmoji.zip"
        try:
            _download_archive(_OPENMOJI_URL, archive)
            with zipfile.ZipFile(archive) as zf:
                candidate = next(
                    (
                        name
                        for name in zf.namelist()
                        if name.lower().endswith("openmoji-black-glyf.ttf")
                        or name in _OPENMOJI_FILE_CANDIDATES
                    ),
                    None,
                )
                if candidate is None:
                    raise FileNotFoundError("OpenMoji black glyph font not found in archive.")  # noqa: TRY301
                extracted = zf.extract(candidate, tmp_dir)
                extracted_path = Path(extracted)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(extracted_path, dest)
                return dest
        except Exception as exc:  # pragma: no cover - network edge
            warnings.warn(f"Unable to download OpenMoji font: {exc}", stacklevel=2)
            return None
    return dest if dest.exists() else None


def _write_otf_package(
    *,
    package_name: str,
    family: str,
    target: Path,
    fonts_path: Path,
    font_prefix: str,
) -> Path:
    path_option = fonts_path.relative_to(target.parent).as_posix()
    fonts = {
        "regular": f"{font_prefix}-regular.otf",
        "bold": f"{font_prefix}-bold.otf",
        "italic": f"{font_prefix}-italic.otf",
        "bold_italic": f"{font_prefix}-bolditalic.otf",
    }
    lines = [
        f"\\ProvidesPackage{{{package_name}}}[Auto-generated OTF wrapper for {family}]",
        "\\RequirePackage{fontspec}",
        f"\\setmainfont{{{fonts['regular']}}}[%",
        f"  Path={path_option}/,%",
        "  Ligatures=TeX,%",
        f"  BoldFont={fonts['bold']},%",
        f"  ItalicFont={fonts['italic']},%",
        f"  BoldItalicFont={fonts['bold_italic']},%",
        "]%",
        f"\\setsansfont{{{fonts['regular']}}}[%",
        f"  Path={path_option}/,%",
        "  Ligatures=TeX,%",
        f"  BoldFont={fonts['bold']},%",
        f"  ItalicFont={fonts['italic']},%",
        f"  BoldItalicFont={fonts['bold_italic']},%",
        "]%",
        f"\\setmonofont{{{fonts['regular']}}}[%",
        f"  Path={path_option}/,%",
        f"  BoldFont={fonts['bold']},%",
        f"  ItalicFont={fonts['italic']},%",
        f"  BoldItalicFont={fonts['bold_italic']},%",
        "]%",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _ensure_plex_fonts(output_dir: Path) -> None:
    fonts_root = output_dir / "fonts" / "plex-otf"
    temp_dir = Path(tempfile.mkdtemp(prefix="texsmith-plex-"))
    archive_path = temp_dir / "TrueType.zip"

    try:
        _download_archive(_PLEX_URL, archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(temp_dir)
    except Exception as exc:  # pragma: no cover - network edge
        warnings.warn(f"Unable to fetch IBM Plex fonts: {exc}", stacklevel=2)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    wanted = {
        "IBMPlexSerif": [
            "IBMPlexSerif-Regular.ttf",
            "IBMPlexSerif-Bold.ttf",
            "IBMPlexSerif-Italic.ttf",
            "IBMPlexSerif-BoldItalic.ttf",
        ],
        "IBMPlexSans": [
            "IBMPlexSans-Regular.ttf",
            "IBMPlexSans-Bold.ttf",
            "IBMPlexSans-Italic.ttf",
            "IBMPlexSans-BoldItalic.ttf",
        ],
        "IBMPlexMono": [
            "IBMPlexMono-Regular.ttf",
            "IBMPlexMono-Bold.ttf",
            "IBMPlexMono-Italic.ttf",
            "IBMPlexMono-BoldItalic.ttf",
        ],
    }

    folder_map = {
        "IBMPlexSerif": "IBM-Plex-Serif",
        "IBMPlexSans": "IBM-Plex-Sans",
        "IBMPlexMono": "IBM-Plex-Mono",
    }

    for family_dir, files in wanted.items():
        folder = folder_map.get(family_dir, family_dir)
        for name in files:
            source = temp_dir / "TrueType" / folder / name
            if not source.exists():
                continue
            dest = fonts_root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)

    shutil.rmtree(temp_dir, ignore_errors=True)


def _ensure_ctan_sty(family: str, output_dir: Path) -> Path | None:
    dependency = _CTAN_DEPENDENCIES.get(family)
    if not dependency:
        return None

    # Pennstander archive is often unavailable on CTAN mirrors; fall back to a stub.
    if family == "pennstander":
        target = output_dir / "pennstander-otf.sty"
        return _write_stub_package("pennstander-otf", family, target)

    package_name = dependency["package"]
    sty_name = f"{package_name}.sty"

    output_dir.mkdir(parents=True, exist_ok=True)
    fonts_dir = output_dir / "fonts" / package_name
    target_path = output_dir / sty_name

    download_error: Exception | None = None
    temp_dir = Path(tempfile.mkdtemp(prefix=f"texsmith-{family}-"))
    archive_path = temp_dir / f"{package_name}.zip"

    try:
        _download_archive(dependency["url"], archive_path)
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(temp_dir)
    except Exception as exc:  # pragma: no cover - network/path edge cases
        download_error = exc

    sty_candidates = list(temp_dir.rglob(sty_name))
    if not sty_candidates:
        sty_candidates = list(temp_dir.rglob("*.sty"))

    if sty_candidates:
        source = sty_candidates[0]
        shutil.copy2(source, target_path)

        for file in temp_dir.rglob("*"):
            if file.is_dir():
                continue
            if file.suffix.lower() in {".otf", ".ttf"}:
                destination = fonts_dir / file.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, destination)
        if family == "plex":
            _ensure_plex_fonts(output_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return target_path

    if family in {"adventor", "cursor"}:
        fonts = list(temp_dir.rglob(f"**/texgyre{family}*-regular.otf"))
        if not fonts:
            fonts = list(temp_dir.rglob(f"**/{family}*-regular.otf"))
        if fonts:
            font_dir = fonts_dir
            font_dir.mkdir(parents=True, exist_ok=True)
            for file in temp_dir.rglob("*.otf"):
                shutil.copy2(file, font_dir / Path(file).name)

            prefix = fonts[0].stem.replace("-regular", "")
            _write_otf_package(
                package_name=package_name,
                family=family,
                target=target_path,
                fonts_path=font_dir,
                font_prefix=prefix,
            )
            shutil.rmtree(temp_dir, ignore_errors=True)
            return target_path

    shutil.rmtree(temp_dir, ignore_errors=True)

    stub_path = _write_stub_package(package_name, family, target_path)
    if download_error is not None:  # pragma: no cover - logging path
        warnings.warn(
            f"Unable to prepare CTAN package for font '{family}': {download_error}",
            stacklevel=2,
        )
    if family == "plex":
        _ensure_plex_fonts(output_dir)
    return stub_path


def _resolve_output_dir(context: Mapping[str, Any]) -> Path:
    for key in ("output_dir", "build_dir", "output_root"):
        raw_path = context.get(key)
        if raw_path:
            try:
                candidate = Path(str(raw_path)).expanduser().resolve()
            except OSError:
                continue
            return candidate
    return Path("build").resolve()


def _slugify(value: str) -> str:
    slug = "".join(ch for ch in value if ch.isalnum())
    if not slug:
        return "script"
    if slug[0].isdigit():
        slug = f"s{slug}"
    return slug.lower()


def _candidate_font_roots(output_dir: Path) -> list[Path]:
    roots: list[Path] = []
    roots.append((output_dir / "fonts").resolve())
    sandbox_fonts = Path(__file__).resolve().parents[4] / "sandbox" / "fonts"
    roots.append(sandbox_fonts)
    user_fonts = get_user_dir().data_dir("fonts", create=False)
    roots.append(user_fonts)
    with contextlib.suppress(Exception):
        cache = FontCache()
        roots.append(cache.root)
        roots.append(cache.path("fonts"))
    return roots


def _find_font_file(name: str, style: str, ext: str, roots: list[Path]) -> Path | None:
    filename = f"{name}-{style_suffix(style)}{ext}"
    for root in roots:
        candidate = root / filename
        if candidate.exists():
            return candidate
    return None


def _prepare_fallback_context(context: Mapping[str, Any], *, output_dir: Path) -> dict[str, Any]:
    """Build fallback metadata for the ts-fonts fragment."""
    fonts_section = context.get("fonts") if isinstance(context.get("fonts"), Mapping) else {}
    fallback_summary = (
        fonts_section.get("fallback_summary") if isinstance(fonts_section, Mapping) else []
    )
    script_usage = fonts_section.get("script_usage") if isinstance(fonts_section, Mapping) else []
    emoji_mode = _resolve_emoji_mode(context)

    def _entry_score(
        has_bold: bool, style_count: int, count: int | None, *, usage_match: bool = False
    ) -> tuple[int, int, int, int]:
        """Higher score wins: usage-aligned fonts first, then bold support, style breadth, usage count."""
        return (1 if usage_match else 0, 1 if has_bold else 0, style_count, count or 0)

    usage_index: dict[str, Mapping[str, Any]] = {}
    for entry in script_usage or []:
        if not isinstance(entry, Mapping):
            continue
        slug = str(entry.get("slug") or "").lower()
        group = str(entry.get("group") or "").lower()
        if slug:
            usage_index[slug] = entry
        if group:
            usage_index[group] = entry

    roots = _candidate_font_roots(output_dir)
    downloader = NotoFontDownloader(cache=FontCache(), logger=FontPipelineLogger())
    emoji_cache = downloader.cache
    roots.append(downloader.fonts_dir)

    entries_by_slug: dict[str, dict[str, Any]] = {}
    package_options: set[str] = set()
    slug_classes: dict[str, set[str]] = {}
    lua_regular: set[str] = set()
    lua_bold: set[str] = set()
    missing_commands: set[str] = set()
    package_options.add("Latin")

    for entry in fallback_summary or []:
        if not isinstance(entry, Mapping):
            continue
        group = entry.get("group") or entry.get("class")
        if not isinstance(group, str) or not group.strip():
            continue
        group_lower = group.lower()
        if group_lower in _SKIP_GROUPS:
            continue
        class_name = entry.get("class") or group
        slug_base = _slugify(group)
        slug_class = _slugify(class_name) if isinstance(class_name, str) else slug_base
        slug = slug_class if slug_class != slug_base else slug_base
        # Prefer the slug recorded in script usage to keep commands aligned with detectors.
        if slug_class != slug_base and (slug_base in usage_index or group_lower in usage_index):
            slug = slug_base
        usage = usage_index.get(slug) or usage_index.get(slug_base) or usage_index.get(group_lower)
        font_command = ""
        text_command = ""
        font_name = None
        usage_font = None
        if isinstance(usage, Mapping):
            font_command = str(usage.get("font_command") or "")
            text_command = str(usage.get("text_command") or "")
            font_name = usage.get("font_name") if isinstance(usage.get("font_name"), str) else None
            usage_font = font_name
        if not font_command:
            font_command = f"{slug}font"
        if not text_command:
            text_command = f"text{slug}"
        font_meta = entry.get("font") if isinstance(entry.get("font"), Mapping) else {}
        alias = _FALLBACK_ALIASES.get(group_lower)
        if isinstance(font_meta, Mapping):
            font_name = font_meta.get("name") or font_name
        if not font_name:
            continue
        styles = []
        if isinstance(font_meta, Mapping):
            styles = [str(style).lower() for style in font_meta.get("styles", []) if style]
        count = entry.get("count")
        ext = font_meta.get("extension") if isinstance(font_meta, Mapping) else ".otf"
        ext = ext if isinstance(ext, str) and ext.startswith(".") else ".otf"
        # Resolve emoji font preferences separately because they are not part of the Noto OTF set.
        emoji_path: Path | None = None
        if group_lower == "symbols" or "emoji" in font_name.lower():
            preferred_color = emoji_mode == "color"
            # Prefer OpenMoji (monochrome) for broader engine compatibility,
            # even when color is requested. Fall back to NotoColorEmoji only
            # when OpenMoji is unavailable.
            emoji_path = _ensure_openmoji_black(emoji_cache)
            font_name = "OpenMojiBlack" if emoji_path is not None else font_name
            if emoji_path is None and preferred_color:
                emoji_path = _ensure_noto_color_emoji(emoji_cache)
                if emoji_path is not None:
                    font_name = "NotoColorEmoji"
            if emoji_path is None or not emoji_path.exists():
                warnings.warn(
                    "Emoji font unavailable; using raw characters for emoji glyphs.",
                    stacklevel=2,
                )
                missing_commands.add("texsmithEmoji")
                continue
            styles = ["regular"]
            ext = ".ttf"
            slug = "emoji"
            font_command = "texsmithEmojiFont"
            text_command = "texsmithEmoji"
            usage_index.setdefault(
                "emoji",
                {
                    "slug": "emoji",
                    "font_command": font_command,
                    "text_command": text_command,
                    "font_name": font_name,
                },
            )
            usage = usage_index.get("emoji") or usage
        else:
            # Ensure required font files exist locally, downloading into the cache when missing.
            downloader.ensure(
                font_name=font_name,
                styles=styles or ["regular", "bold"],
                extension=ext,
                dir_base=font_meta.get("dir") if isinstance(font_meta, Mapping) else None,
            )

        destination_root = (output_dir / "fonts").resolve()
        destination_root.mkdir(parents=True, exist_ok=True)
        sources: dict[str, Path] = {}
        for style in styles or ["regular", "bold"]:
            if emoji_path is not None:
                src = emoji_path
            else:
                src = downloader.fonts_dir / f"{font_name}-{style_suffix(style)}{ext}"
            if src.exists():
                sources[style] = src
                dest = destination_root / src.name
                if not dest.exists():
                    shutil.copy2(src, dest)

        upright_file = sources.get("regular") or _find_font_file(font_name, "regular", ext, roots)
        bold_file = (
            sources.get("bold")
            if "bold" in styles
            else _find_font_file(font_name, "bold", ext, roots)
            if "bold" in styles
            else None
        )
        if upright_file is None:
            candidate = downloader.fonts_dir / f"{font_name}-{style_suffix('regular')}{ext}"
            if candidate.exists():
                upright_file = candidate
        if bold_file is None and "bold" in styles:
            candidate = downloader.fonts_dir / f"{font_name}-{style_suffix('bold')}{ext}"
            if candidate.exists():
                bold_file = candidate
        style_count = len(styles) if styles else 1
        if upright_file is None:
            alias = _FALLBACK_ALIASES.get(group_lower)
            if alias:
                alt_name = alias.get("name")
                alt_ext = alias.get("extension", ext)
                alt_styles = alias.get("styles", styles)
                if isinstance(alt_name, str):
                    alt_dir = alias.get("dir")
                    alt_ext = (
                        alt_ext if isinstance(alt_ext, str) and alt_ext.startswith(".") else ".otf"
                    )
                    alt_styles = (
                        [str(s).lower() for s in alt_styles]
                        if isinstance(alt_styles, (list, tuple, set))
                        else styles
                    )
                    downloader.ensure(
                        font_name=alt_name,
                        styles=alt_styles or styles or ["regular", "bold"],
                        extension=alt_ext,
                        dir_base=str(alt_dir) if isinstance(alt_dir, str) else None,
                    )
                    font_name = alt_name
                    ext = alt_ext
                    styles = alt_styles
                    upright_file = _find_font_file(font_name, "regular", ext, roots)
                    bold_file = (
                        _find_font_file(font_name, "bold", ext, roots) if "bold" in styles else None
                    )
                    if upright_file is None:
                        candidate = (
                            downloader.fonts_dir / f"{font_name}-{style_suffix('regular')}{ext}"
                        )
                        if candidate.exists():
                            upright_file = candidate
                    if bold_file is None and "bold" in styles:
                        candidate = (
                            downloader.fonts_dir / f"{font_name}-{style_suffix('bold')}{ext}"
                        )
                        if candidate.exists():
                            bold_file = candidate
                    style_count = len(styles) if styles else 1
        if upright_file is None:
            warnings.warn(
                f"Fallback font '{font_name}' not found on disk; skipping script '{group}'.",
                stacklevel=2,
            )
            missing_commands.add(text_command)
            continue

        dest_upright = destination_root / upright_file.name
        if not dest_upright.exists():
            shutil.copy2(upright_file, dest_upright)

        dest_bold: Path | None = None
        if bold_file is not None:
            dest_bold = destination_root / bold_file.name
            if not dest_bold.exists():
                shutil.copy2(bold_file, dest_bold)

        existing = entries_by_slug.get(slug)
        candidate_payload = {
            "group": group,
            "class": class_name,
            "slug": slug,
            "font_command": font_command,
            "text_command": text_command,
            "font_name": font_name,
            "count": count if isinstance(count, (int, float)) else None,
            "has_bold": bool(dest_bold),
            "upright": dest_upright.stem,
            "bold": dest_bold.stem if dest_bold else None,
            "extension": ext,
            "style_count": style_count,
        }
        usage_match = bool(usage_font) and font_name and usage_font.lower() == font_name.lower()
        candidate_score = _entry_score(
            bool(dest_bold), style_count, candidate_payload["count"], usage_match=usage_match
        )
        if existing is None:
            entries_by_slug[slug] = candidate_payload
        else:
            existing_count = existing.get("count", 0)
            combined_count = int(existing_count or 0) + (
                int(count) if isinstance(count, (int, float)) else 0
            )
            candidate_payload["count"] = combined_count if combined_count else None
            existing_usage_match = (
                bool(usage_font)
                and existing.get("font_name")
                and str(existing.get("font_name")).lower() == str(usage_font).lower()
            )
            existing_score = _entry_score(
                bool(existing.get("has_bold")),
                int(existing.get("style_count") or 1),
                existing.get("count"),
                usage_match=existing_usage_match,
            )
            if candidate_score > existing_score:
                entries_by_slug[slug] = candidate_payload
            else:
                if combined_count:
                    existing["count"] = combined_count
                if dest_bold is not None and not existing.get("has_bold"):
                    existing["has_bold"] = True
                    existing["bold"] = dest_bold.stem
                    existing["style_count"] = max(
                        int(existing.get("style_count") or 1), style_count
                    )
                    lua_bold.add(dest_bold.name)

        package_options.add(str(class_name))
        slug_classes.setdefault(slug, set()).add(str(class_name))
        entry_ref = entries_by_slug[slug]
        lua_regular.add(f"{entry_ref['upright']}{entry_ref['extension']}")
        if entry_ref.get("has_bold") and entry_ref.get("bold"):
            lua_bold.add(f"{entry_ref['bold']}{entry_ref['extension']}")
        else:
            lua_bold.add(f"{entry_ref['upright']}{entry_ref['extension']}")

    if slug_classes:
        package_options.update(
            cls_name for classes in slug_classes.values() for cls_name in classes
        )

    transitions: list[str] = []
    for slug, classes in sorted(slug_classes.items()):
        entry = entries_by_slug.get(slug)
        if not entry:
            continue
        font_command = entry.get("font_command")
        if not font_command:
            continue
        for class_name in sorted(classes):
            transitions.append(
                f"\\setTransitionsFor{{{class_name}}}{{\\{font_command}}}{{\\texsmithFallbackFamily}}"
            )

    return {
        "entries": sorted(
            entries_by_slug.values(),
            key=lambda e: e.get("group") or e.get("class") or "",
        ),
        "package_options": sorted(package_options),
        "transitions": transitions,
        "lua_regular": sorted(lua_regular),
        "lua_bold": sorted(lua_bold),
        "missing_commands": sorted(
            missing_commands
            | {
                str(entry.get("text_command") or f"text{entry.get('slug')}")
                for entry in usage_index.values()
                if entry.get("slug") and entry.get("slug") not in entries_by_slug
            }
        ),
    }


@dataclass(frozen=True)
class FontsConfig:
    family: str
    output_dir: Path
    fallback: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> FontsConfig:
        fonts_section = context.get("fonts")
        if isinstance(fonts_section, Mapping):
            raw_family = fonts_section.get("family")
        else:
            raw_family = context.get("fonts_family")
        family = _normalise_family(raw_family)
        output_dir = _resolve_output_dir(context)
        fallback = _prepare_fallback_context(context, output_dir=output_dir)
        return cls(family=family, output_dir=output_dir, fallback=fallback)

    def inject_into(self, context: dict[str, Any]) -> None:
        context["fonts_family"] = self.family
        fonts_section = context.get("fonts")
        merged = dict(fonts_section) if isinstance(fonts_section, Mapping) else {}
        merged["family"] = self.family
        if self.fallback and self.fallback.get("entries"):
            merged["fallback"] = self.fallback
        context["fonts"] = merged

        try:
            _ensure_ctan_sty(self.family, self.output_dir)
        except Exception as exc:  # pragma: no cover - network/path edge cases
            warnings.warn(
                f"Unable to prepare CTAN package for font '{self.family}': {exc}",
                stacklevel=2,
            )


class FontsFragment(BaseFragment[FontsConfig]):
    name: ClassVar[str] = "ts-fonts"
    description: ClassVar[str] = "Font selection driven by fonts.family."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-fonts.jinja.sty"),
            kind="package",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, TemplateAttributeSpec]] = {
        "fonts_family": TemplateAttributeSpec(
            default="lm",
            type="string",
            allow_empty=False,
            choices=sorted(set(_FAMILY_CHOICES.keys())),
            sources=[
                "fonts.family",
                "fonts_family",
                "font_family",
            ],
        )
    }
    config_cls: ClassVar[type[FontsConfig]] = FontsConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-fonts.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> FontsConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: FontsConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: FontsConfig) -> bool:
        _ = config
        return True


fragment = FontsFragment()

__all__ = ["FontsConfig", "FontsFragment", "fragment"]
