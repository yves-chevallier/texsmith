"""Cache and download bundled font assets."""

from __future__ import annotations

from dataclasses import dataclass
import io
import os
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, Any
import urllib.request
import zipfile
from urllib.parse import urlparse

from texsmith.fonts.cjk import CJK_FAMILY_SPECS, CJK_SCRIPT_ROWS
from texsmith.fonts.data import noto_dataset
from texsmith.fonts.utils import normalize_family


if TYPE_CHECKING:
    from texsmith.core.diagnostics import DiagnosticEmitter


_FONT_CACHE_DIR_ENV = "TEXSMITH_FONT_CACHE_DIR"
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "texsmith" / "fonts"


@dataclass(frozen=True, slots=True)
class FontSource:
    """Describe a downloadable font artefact."""

    family: str
    url: str
    filename: str
    zip_member: str | None = None
    style: str | None = None
    alt_members: tuple[str, ...] = ()


_KNOWN_SOURCES: dict[str, tuple[FontSource, ...]] = {
    normalize_family("Noto Color Emoji"): (
        FontSource(
            family="Noto Color Emoji",
            url="https://github.com/googlefonts/noto-emoji/raw/refs/heads/main/fonts/NotoColorEmoji.ttf",
            filename="NotoColorEmoji.ttf",
        ),
    ),
    normalize_family("OpenMoji Black"): (
        FontSource(
            family="OpenMoji Black",
            url="https://github.com/hfg-gmuend/openmoji/releases/download/16.0.0/openmoji-font.zip",
            filename="OpenMoji-black-glyf.ttf",
            zip_member="OpenMoji-black-glyf/OpenMoji-black-glyf.ttf",
            alt_members=("fonts/OpenMoji-black-glyf.ttf",),
        ),
    ),
    normalize_family("IBM Plex Mono"): (
        FontSource(
            family="IBM Plex Mono",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-Regular.otf",
            zip_member="plex/opentype/IBMPlexMono-Regular.otf",
            style="regular",
        ),
        FontSource(
            family="IBM Plex Mono",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-Bold.otf",
            zip_member="plex/opentype/IBMPlexMono-Bold.otf",
            style="bold",
        ),
        FontSource(
            family="IBM Plex Mono",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-Italic.otf",
            zip_member="plex/opentype/IBMPlexMono-Italic.otf",
            style="italic",
        ),
        FontSource(
            family="IBM Plex Mono",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-BoldItalic.otf",
            zip_member="plex/opentype/IBMPlexMono-BoldItalic.otf",
            style="bold italic",
        ),
        FontSource(
            family="IBM Plex Mono",
            url="https://mirrors.ctan.org/fonts/plex.zip",
            filename="IBMPlexMono-Medium.otf",
            zip_member="plex/opentype/IBMPlexMono-Medium.otf",
            style="medium",
        ),
    ),
}

_NOTO_FAMILY_STYLES: dict[str, set[str]] = {}
_NOTO_FAMILY_NAMES: dict[str, str] = {}
for script_id, title, regular, bold, italic, bold_italic in noto_dataset.SCRIPT_FALLBACKS:
    for style_key, family in (
        ("regular", regular),
        ("bold", bold),
        ("italic", italic),
        ("bolditalic", bold_italic),
    ):
        if not family:
            continue
        normalized = normalize_family(family)
        _NOTO_FAMILY_STYLES.setdefault(normalized, set()).add(style_key)
        _NOTO_FAMILY_NAMES.setdefault(normalized, family)

for row in CJK_SCRIPT_ROWS.values():
    _id, _title, regular, bold, italic, bold_italic = row
    for style_key, family in (
        ("regular", regular),
        ("bold", bold),
        ("italic", italic),
        ("bolditalic", bold_italic),
    ):
        if not family:
            continue
        normalized = normalize_family(family)
        _NOTO_FAMILY_STYLES.setdefault(normalized, set()).add(style_key)
        _NOTO_FAMILY_NAMES.setdefault(normalized, family)


def _register_cjk_sources() -> None:
    for family, spec in CJK_FAMILY_SPECS.items():
        norm = normalize_family(family)
        existing = list(_KNOWN_SOURCES.get(norm, ()))
        for weight in spec.get("weights", ("Regular",)):
            style_key = "regular" if weight.lower() == "regular" else "bold"
            filename = f"{family}-{weight}.otf"
            url = (
                "https://rawcdn.githack.com/notofonts/noto-cjk/main/"
                f"{spec['style_dir']}/OTF/{spec['region']}/{filename}"
            )
            existing.append(
                FontSource(
                    family=family,
                    url=url,
                    filename=filename,
                    style=style_key,
                )
            )
        _KNOWN_SOURCES[norm] = tuple(existing)


_register_cjk_sources()


def font_cache_dir() -> Path:
    """Return the directory used to cache downloaded fonts."""
    override = os.environ.get(_FONT_CACHE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return _DEFAULT_CACHE_DIR


def _warn(emitter: DiagnosticEmitter | None, message: str) -> None:
    if emitter:
        try:
            emitter.warning(message)
        except Exception:
            return


def _open_url(url: str) -> Any:
    return urllib.request.urlopen(url, timeout=30)


def _download_payload(source: FontSource, emitter: DiagnosticEmitter | None) -> bytes | None:
    try:
        with _open_url(source.url) as response:
            return response.read()
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        _warn(
            emitter,
            f"Unable to download font '{source.family}' from {source.url}: {exc}",
        )
    return None


def _download_direct(
    url: str, family: str, style: str, emitter: DiagnosticEmitter | None
) -> bytes | None:
    try:
        with _open_url(url) as response:
            return response.read()
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        _warn(
            emitter,
            f"Unable to download font '{family}' ({style}) from {url}: {exc}",
        )
    return None


def _extract_payload(
    source: FontSource, payload: bytes, emitter: DiagnosticEmitter | None
) -> bytes | None:
    if not source.zip_member:
        return payload
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.namelist()
            if source.zip_member in members:
                return archive.read(source.zip_member)
            for alternate in source.alt_members:
                if alternate in members:
                    return archive.read(alternate)

            target_lower = source.filename.lower()
            lowered = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".ttf") or name.lower().endswith(".otf")
            ]
            preferred: str | None = None
            for candidate in lowered:
                candidate_lower = candidate.lower()
                if candidate_lower.endswith(target_lower):
                    preferred = candidate
                    break
                if "openmoji" in candidate_lower and "glyf" in candidate_lower:
                    preferred = candidate
                    break
            if not preferred:
                preferred = next(iter(lowered), None)
            if preferred:
                _warn(
                    emitter,
                    (
                        f"Expected '{source.zip_member}' in archive but found '{preferred}'. "
                        "Using the available font file instead."
                    ),
                )
                return archive.read(preferred)
            _warn(
                emitter,
                f"Failed to extract '{source.zip_member}' from downloaded archive: missing file.",
            )
            return None
    except Exception as exc:
        _warn(emitter, f"Failed to extract '{source.zip_member}' from downloaded archive: {exc}")
        return None


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _cache_noto_family(
    family: str, *, emitter: DiagnosticEmitter | None = None
) -> dict[str, Path] | None:
    normalized = normalize_family(family)
    styles = _NOTO_FAMILY_STYLES.get(normalized)
    if not styles:
        return None
    canonical = _NOTO_FAMILY_NAMES.get(normalized, family)
    cached: dict[str, Path] = {}
    cache_dir = font_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    for style in sorted(styles):
        style_key = "bold_italic" if style == "bolditalic" else style
        url = noto_dataset.build_cdn_url(canonical, style=style, build="full", flavor="otf")
        filename = Path(urlparse(url).path).name
        target = cache_dir / filename
        if not target.exists():
            payload = _download_direct(url, canonical, style_key, emitter)
            if payload is None:
                continue
            try:
                _atomic_write(target, payload)
            except Exception as exc:  # pragma: no cover - filesystem/runtime dependent
                _warn(emitter, f"Unable to cache font '{canonical}' ({style_key}) at {target}: {exc}")
                continue
        cached[style_key] = target
    if not cached:
        return None
    return cached


def ensure_font_cached(
    family: str, *, emitter: DiagnosticEmitter | None = None
) -> Path | dict[str, Path] | None:
    """
    Ensure the requested font family is cached locally.

    Returns the cached path (or style mapping for multi-face families) on success.
    """
    normalized = normalize_family(family)
    sources = _KNOWN_SOURCES.get(normalized)
    if not sources:
        noto_cached = _cache_noto_family(family, emitter=emitter)
        if noto_cached:
            return noto_cached
        return None

    cached: dict[str, Path] = {}
    payload_cache: dict[str, bytes] = {}

    for source in sources:
        target = font_cache_dir() / source.filename
        if target.exists():
            cached[source.style or source.filename] = target
            continue

        payload = payload_cache.get(source.url)
        if payload is None:
            payload = _download_payload(source, emitter)
            if payload is None:
                continue
            payload_cache[source.url] = payload

        extracted = _extract_payload(source, payload, emitter)
        if extracted is None:
            continue

        try:
            _atomic_write(target, extracted)
        except Exception as exc:  # pragma: no cover - filesystem/runtime dependent
            _warn(emitter, f"Unable to cache font '{source.family}' at {target}: {exc}")
            continue
        cached[source.style or source.filename] = target

    if not cached:
        return None
    if len(cached) == 1:
        return next(iter(cached.values()))
    return cached


def cache_fonts_for_families(
    families: list[str] | set[str] | tuple[str, ...],
    *,
    emitter: DiagnosticEmitter | None = None,
) -> tuple[dict[str, Path | dict[str, Path]], set[str]]:
    """Cache known downloadable fonts required by ``families``."""
    cached: dict[str, Path | dict[str, Path]] = {}
    failures: set[str] = set()
    for family in families:
        result = ensure_font_cached(family, emitter=emitter)
        if result:
            cached[family] = result
        else:
            normalized = normalize_family(family)
            if normalized in _KNOWN_SOURCES or normalized in _NOTO_FAMILY_STYLES:
                failures.add(family)
    return cached, failures


__all__ = ["cache_fonts_for_families", "ensure_font_cached", "font_cache_dir"]
