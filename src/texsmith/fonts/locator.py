"""Locate and copy font files required for LaTeX builds."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

import yaml

from texsmith.fonts.utils import normalize_family


def _subprocess_run_available() -> bool:
    run_fn = getattr(subprocess, "run", None)
    return callable(run_fn) and getattr(run_fn, "__module__", "") == "subprocess"


def subprocess_run_available() -> bool:
    """Public wrapper to detect when subprocess.run is available."""
    return _subprocess_run_available()


_REGULAR_STYLES = ("regular", "book", "normal", "roman")
_BOLD_STYLES = ("bold", "bold regular", "semibold", "demibold", "medium")
_ITALIC_STYLES = ("italic", "oblique")
_BOLD_ITALIC_STYLES = (
    "bold italic",
    "bolditalic",
    "bold oblique",
    "boldoblique",
    "semibold italic",
    "medium italic",
    "medium oblique",
)


def _style_key(value: str | None) -> str:
    return (value or "Regular").strip().casefold() or "regular"


def _guess_style_from_filename(path: Path) -> str:
    name = path.name.casefold()
    if "bold" in name and ("italic" in name or "oblique" in name):
        return "bold italic"
    if "bold" in name:
        return "bold"
    if "italic" in name or "oblique" in name:
        return "italic"
    return "regular"


@dataclass(frozen=True, slots=True)
class FontFiles:
    """Resolved file paths for a font family."""

    family: str
    regular: Path | None = None
    bold: Path | None = None
    italic: Path | None = None
    bold_italic: Path | None = None

    def any_files(self) -> bool:
        """Return True when at least one face is present."""
        return any([self.regular, self.bold, self.italic, self.bold_italic])

    def available(self) -> dict[str, Path]:
        """Return a mapping of the available face names to their paths."""
        entries = {
            "regular": self.regular,
            "bold": self.bold,
            "italic": self.italic,
            "bold_italic": self.bold_italic,
        }
        return {key: value for key, value in entries.items() if value is not None}

    def copy_into(self, destination: Path, *, cache: dict[Path, Path] | None = None) -> FontFiles:
        """Copy the font files into ``destination`` and return updated paths."""
        destination.mkdir(parents=True, exist_ok=True)

        def _copy(path: Path | None) -> Path | None:
            if path is None:
                return None
            resolved = path
            target = destination / resolved.name
            if cache is not None and resolved in cache:
                return cache[resolved]
            try:
                if not target.exists():
                    shutil.copy2(resolved, target)
            except OSError:
                return None
            if cache is not None:
                cache[resolved] = target
            return target

        return FontFiles(
            family=self.family,
            regular=_copy(self.regular),
            bold=_copy(self.bold),
            italic=_copy(self.italic),
            bold_italic=_copy(self.bold_italic),
        )

    def relative_to(self, base: Path) -> FontFiles:
        """Return a copy with paths relative to ``base`` when possible."""

        def _rel(path: Path | None) -> Path | None:
            if path is None:
                return None
            try:
                return path.relative_to(base)
            except ValueError:
                return path

        return FontFiles(
            family=self.family,
            regular=_rel(self.regular),
            bold=_rel(self.bold),
            italic=_rel(self.italic),
            bold_italic=_rel(self.bold_italic),
        )


class FontLocator:
    """Discover fonts from the system or a supplied ``fonts.yaml``."""

    _KPSE_FAMILIES: Mapping[str, Mapping[str, str]] = {
        "Latin Modern Roman": {
            "regular": "lmroman10-regular.otf",
            "bold": "lmroman10-bold.otf",
            "italic": "lmroman10-italic.otf",
            "bold_italic": "lmroman10-bolditalic.otf",
        },
        "Latin Modern Roman Caps": {
            "regular": "lmromancaps10-regular.otf",
        },
        "Latin Modern Sans": {
            "regular": "lmsans10-regular.otf",
            "bold": "lmsans10-bold.otf",
            "italic": "lmsans10-italic.otf",
            "bold_italic": "lmsans10-bolditalic.otf",
        },
        "Latin Modern Math": {
            "regular": "latinmodern-math.otf",
        },
        "NotoSansMath-Regular": {
            "regular": "NotoSansMath-Regular.otf",
        },
        "NotoSansSymbols2-Regular": {
            "regular": "NotoSansSymbols2-Regular.ttf",
        },
    }

    def __init__(
        self, *, fonts_yaml: Path | None = None, search_paths: Iterable[Path] | None = None
    ) -> None:
        self._fonts: dict[str, dict[str, Path]] = {}
        self._names: dict[str, set[str]] = {}

        if search_paths:
            for path in search_paths:
                self._register_directory(path)

        if fonts_yaml:
            self.register_from_fonts_yaml(fonts_yaml)

        self._load_from_fontconfig()
        self._register_known_tex_families()

    def _register_entry(self, family: str, style: str, path: Path) -> None:
        key = normalize_family(family)
        self._fonts.setdefault(key, {})[_style_key(style)] = path
        self._names.setdefault(key, set()).add(family)

    def _register_directory(self, path: Path) -> None:
        if not path.exists():
            return
        for file_path in path.rglob("*"):
            if file_path.suffix.lower() not in {".otf", ".ttf", ".ttc"}:
                continue
            style = _guess_style_from_filename(file_path)
            family = file_path.stem
            self._register_entry(family, style, file_path.resolve())

    def register_from_fonts_yaml(self, fonts_yaml: Path) -> None:
        """Register font files declared in a ``fonts.yaml`` descriptor."""
        try:
            data = yaml.safe_load(fonts_yaml.read_text(encoding="utf-8"))
        except Exception:
            return
        base_dir = fonts_yaml.parent
        for entry in data or []:
            family = entry.get("family")
            if not isinstance(family, str):
                continue
            for item in entry.get("files") or []:
                if not isinstance(item, str):
                    continue
                candidate = (base_dir / item).resolve()
                if not candidate.exists():
                    continue
                style = _guess_style_from_filename(candidate)
                self._register_entry(family, style, candidate)

    def _load_from_fontconfig(self) -> None:
        if shutil.which("fc-list") is None or os.environ.get("TEXSMITH_SKIP_FONT_CHECKS"):
            return
        if not _subprocess_run_available():
            return

        try:
            proc = subprocess.run(
                ["fc-list", "-f", "%{file}|%{family}|%{style}\n"],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return

        for line in proc.stdout.splitlines():
            parts = line.split("|")
            if len(parts) != 3:
                continue
            file_part, families_part, styles_part = parts
            path = Path(file_part).expanduser()
            if not path.exists():
                continue
            families = [fam.strip() for fam in families_part.split(",") if fam.strip()]
            styles = [sty.strip() for sty in styles_part.split(",") if sty.strip()]
            style_value = styles[0] if styles else "Regular"
            for family in families:
                self._register_entry(family, style_value, path)

    def _register_known_tex_families(self) -> None:
        """Use kpsewhich to discover TeXLive-provided font files."""
        for family, styles in self._KPSE_FAMILIES.items():
            for style, filename in styles.items():
                path = _find_with_kpsewhich(filename)
                if path is None:
                    continue
                self._register_entry(family, style, path)

    def available_families(self) -> set[str]:
        """Return the discovered family names (raw values as reported)."""
        names: set[str] = set()
        for bucket in self._names.values():
            names.update(bucket)
        return names

    def _known_styles_for(self, family: str) -> dict[str, Path]:
        """Return the discovered styles for a family, if any."""
        return self._fonts.get(normalize_family(family), {})

    def check_installed(self, required: Iterable[str]) -> tuple[set[str], set[str]]:
        """Return (present, missing) families from the provided names."""
        present: set[str] = set()
        missing: set[str] = set()
        for family in required:
            key = normalize_family(family)
            if key in self._fonts:
                present.add(family)
            else:
                missing.add(family)
        return present, missing

    def locate_family(self, family: str) -> FontFiles:
        """Return resolved files for the requested family, if available."""
        styles = self._fonts.get(normalize_family(family))
        if not styles:
            return FontFiles(family=family)

        def _pick(candidates: tuple[str, ...]) -> Path | None:
            for candidate in candidates:
                if candidate in styles:
                    return styles[candidate]
            return None

        return FontFiles(
            family=family,
            regular=_pick(_REGULAR_STYLES),
            bold=_pick(_BOLD_STYLES),
            italic=_pick(_ITALIC_STYLES),
            bold_italic=_pick(_BOLD_ITALIC_STYLES),
        )

    def copy_family(
        self, family: str, destination: Path, *, cache: dict[Path, Path] | None = None
    ) -> FontFiles:
        """Locate and copy the requested family into ``destination``."""
        located = self.locate_family(family)
        if not located.any_files():
            return located
        return located.copy_into(destination, cache=cache)

    def copy_families(
        self,
        families: Iterable[str],
        destination: Path,
    ) -> dict[str, FontFiles]:
        """Copy a list of font families into ``destination``."""
        copied: dict[str, FontFiles] = {}
        cache: dict[Path, Path] = {}
        for family in families:
            result = self.copy_family(family, destination, cache=cache)
            if result.any_files():
                copied[family] = result
        return copied


def _find_with_kpsewhich(filename: str) -> Path | None:
    """Attempt to locate a TeX Live font file via kpsewhich."""
    if shutil.which("kpsewhich") is None:
        return None
    if not _subprocess_run_available():
        return None
    try:
        proc = subprocess.run(
            ["kpsewhich", filename],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    candidate = Path(proc.stdout.strip())
    if candidate.exists():
        return candidate
    return None


__all__ = ["FontFiles", "FontLocator", "subprocess_run_available"]
