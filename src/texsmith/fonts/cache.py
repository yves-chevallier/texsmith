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
            zip_member="fonts/OpenMoji-black-glyf.ttf",
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
            if source.zip_member in archive.namelist():
                return archive.read(source.zip_member)

            lowered = [name for name in archive.namelist() if name.lower().endswith(".ttf")]
            preferred: str | None = None
            for candidate in lowered:
                candidate_lower = candidate.lower()
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


def ensure_font_cached(family: str, *, emitter: DiagnosticEmitter | None = None) -> Path | None:
    """
    Ensure the requested font family is cached locally.

    Returns the cached path on success, otherwise ``None``.
    """
    sources = _KNOWN_SOURCES.get(normalize_family(family))
    if not sources:
        return None

    target = font_cache_dir() / sources[0].filename
    if target.exists():
        return target

    for source in sources:
        payload = _download_payload(source, emitter)
        if payload is None:
            continue

        extracted = _extract_payload(source, payload, emitter)
        if extracted is None:
            continue

        try:
            _atomic_write(target, extracted)
        except Exception as exc:  # pragma: no cover - filesystem/runtime dependent
            _warn(emitter, f"Unable to cache font '{source.family}' at {target}: {exc}")
            continue
        return target
    return None


def cache_fonts_for_families(
    families: list[str] | set[str] | tuple[str, ...],
    *,
    emitter: DiagnosticEmitter | None = None,
) -> tuple[dict[str, Path], set[str]]:
    """Cache known downloadable fonts required by ``families``."""
    cached: dict[str, Path] = {}
    failures: set[str] = set()
    for family in families:
        result = ensure_font_cached(family, emitter=emitter)
        if result:
            cached[family] = result
        elif normalize_family(family) in _KNOWN_SOURCES:
            failures.add(family)
    return cached, failures


__all__ = ["cache_fonts_for_families", "ensure_font_cached", "font_cache_dir"]
