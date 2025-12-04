from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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


@dataclass(frozen=True)
class FontsConfig:
    family: str
    output_dir: Path

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> FontsConfig:
        fonts_section = context.get("fonts")
        if isinstance(fonts_section, Mapping):
            raw_family = fonts_section.get("family")
        else:
            raw_family = context.get("fonts_family")
        family = _normalise_family(raw_family)
        output_dir = _resolve_output_dir(context)
        return cls(family=family, output_dir=output_dir)

    def inject_into(self, context: dict[str, Any]) -> None:
        context["fonts_family"] = self.family
        fonts_section = context.get("fonts")
        merged = dict(fonts_section) if isinstance(fonts_section, Mapping) else {}
        merged["family"] = self.family
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
                "press.fonts.family",
                "fonts.family",
                "fonts_family",
                "press.font_family",
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
