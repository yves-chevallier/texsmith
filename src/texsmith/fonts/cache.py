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

from texsmith.fonts.utils import normalize_family


if TYPE_CHECKING:
    from texsmith.core.diagnostics import DiagnosticEmitter


_FONT_CACHE_DIR_ENV = "TEXSMITH_FONT_CACHE_DIR"
_DEFAULT_CACHE_DIR = Path.home() / ".texsmith" / "fonts"


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


def ensure_font_cached(
    family: str, *, emitter: DiagnosticEmitter | None = None
) -> Path | dict[str, Path] | None:
    """
    Ensure the requested font family is cached locally.

    Returns the cached path (or style mapping for multi-face families) on success.
    """
    sources = _KNOWN_SOURCES.get(normalize_family(family))
    if not sources:
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
        elif normalize_family(family) in _KNOWN_SOURCES:
            failures.add(family)
    return cached, failures


__all__ = ["cache_fonts_for_families", "ensure_font_cached", "font_cache_dir"]
