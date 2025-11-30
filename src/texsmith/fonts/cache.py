"""Cache and download font assets with metadata tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import TYPE_CHECKING, Any
import urllib.request
import zipfile

from texsmith.fonts.registry import FontSourceSpec, sources_for_family


if TYPE_CHECKING:
    from texsmith.core.diagnostics import DiagnosticEmitter


FONT_CACHE_DIR_ENV = "TEXSMITH_FONT_CACHE_DIR"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "texsmith" / "fonts"
CACHE_SCHEMA_VERSION = 2
CACHE_VERSION_PREFIX = f"v{CACHE_SCHEMA_VERSION}"
METADATA_FILENAME = "metadata.json"


def font_cache_dir() -> Path:
    """Return the directory used to cache downloaded fonts."""
    override = os.environ.get(FONT_CACHE_DIR_ENV)
    base_dir = Path(override).expanduser() if override else DEFAULT_CACHE_DIR
    cache_dir = base_dir / CACHE_VERSION_PREFIX
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _warn(emitter: DiagnosticEmitter | None, message: str) -> None:
    if emitter:
        emitter.warning(message)


def _open_url(url: str) -> Any:
    return urllib.request.urlopen(url, timeout=60)


def _download_url(url: str, emitter: DiagnosticEmitter | None) -> bytes | None:
    try:
        with _open_url(url) as response:
            return response.read()
    except Exception as exc:  # pragma: no cover - depends on network
        _warn(emitter, f"Unable to download font payload from {url}: {exc}")
        return None


def _extract_payload(spec: FontSourceSpec, payload: bytes, emitter: DiagnosticEmitter | None) -> bytes | None:
    if not spec.zip_member:
        return payload
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.namelist()
            if spec.zip_member in members:
                return archive.read(spec.zip_member)
            for alternate in spec.alt_members:
                if alternate in members:
                    return archive.read(alternate)
            # heuristics: fall back to file with same suffix
            target_lower = spec.filename.lower()
            candidates = [
                name
                for name in members
                if name.lower().endswith(".ttf") or name.lower().endswith(".otf")
            ]
            preferred: str | None = None
            for candidate in candidates:
                lower = candidate.lower()
                if lower.endswith(target_lower):
                    preferred = candidate
                    break
            if not preferred:
                preferred = candidates[0] if candidates else None
            if preferred:
                _warn(
                    emitter,
                    (
                        f"Expected '{spec.zip_member}' in archive but located '{preferred}'. "
                        "Using available font file."
                    ),
                )
                return archive.read(preferred)
            _warn(
                emitter,
                f"Failed to extract '{spec.zip_member}' from downloaded archive: missing file.",
            )
            return None
    except Exception as exc:
        _warn(emitter, f"Failed to unpack archive for '{spec.family}': {exc}")
        return None


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent) as tmp:
        tmp.write(payload)
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    _atomic_write_bytes(path, data)


@dataclass(slots=True)
class FontRecord:
    """Represent a cached font and its metadata."""

    spec: FontSourceSpec
    path: Path
    metadata: dict[str, Any]


def _metadata_path(cache_dir: Path) -> Path:
    return cache_dir / METADATA_FILENAME


def _load_metadata(cache_dir: Path, font_path: Path) -> dict[str, Any] | None:
    meta_path = _metadata_path(cache_dir)
    if not meta_path.exists() or not font_path.exists():
        return None
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if metadata.get("schema") != CACHE_SCHEMA_VERSION:
        return None
    return metadata


def _ensure_payload(
    spec: FontSourceSpec,
    *,
    emitter: DiagnosticEmitter | None,
    payload_cache: dict[str, bytes] | None,
) -> bytes | None:
    cache = payload_cache if payload_cache is not None else {}
    raw = cache.get(spec.url)
    if raw is None:
        raw = _download_url(spec.url, emitter)
        if raw is None:
            return None
        cache[spec.url] = raw
    extracted = _extract_payload(spec, raw, emitter)
    return extracted


def ensure_font(
    spec: FontSourceSpec,
    *,
    emitter: DiagnosticEmitter | None = None,
    payload_cache: dict[str, bytes] | None = None,
) -> FontRecord | None:
    """Ensure the given source spec is cached locally."""
    cache_dir = font_cache_dir() / spec.cache_key
    font_path = cache_dir / spec.filename
    metadata = _load_metadata(cache_dir, font_path)
    if metadata:
        return FontRecord(spec=spec, path=font_path, metadata=metadata)

    payload = _ensure_payload(spec, emitter=emitter, payload_cache=payload_cache)
    if payload is None:
        return None
    checksum = hashlib.sha256(payload).hexdigest()
    _atomic_write_bytes(font_path, payload)
    metadata = {
        "schema": CACHE_SCHEMA_VERSION,
        "family": spec.family,
        "style": spec.style,
        "file": font_path.name,
        "source": {
            "id": spec.id,
            "url": spec.url,
            "zip_member": spec.zip_member,
            "version": spec.version,
            "sha256": checksum,
        },
        "coverage": {
            "scripts": list(spec.scripts),
            "blocks": list(spec.blocks),
        },
        "retrieved_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    _atomic_write_json(_metadata_path(cache_dir), metadata)
    return FontRecord(spec=spec, path=font_path, metadata=metadata)


def materialize_font(
    record: FontRecord,
    *,
    build_dir: Path,
    prefer_symlink: bool = False,
) -> Path:
    """Copy or link a cached font into the build directory."""
    build_dir.mkdir(parents=True, exist_ok=True)
    target = build_dir / record.path.name
    if target.exists():
        return target
    if prefer_symlink:
        try:
            target.symlink_to(record.path)
            return target
        except OSError:
            target.unlink(missing_ok=True)
    shutil.copy2(record.path, target)
    return target


def ensure_font_cached(
    family: str,
    *,
    emitter: DiagnosticEmitter | None = None,
) -> dict[str, Path] | Path | None:
    """
    Compatibility helper mirroring the legacy cache API.

    Returns the cached path (or style mapping for multi-face families) on success.
    """
    specs = sources_for_family(family)
    if not specs:
        return None
    payload_cache: dict[str, bytes] = {}
    cached_paths: dict[str, Path] = {}
    for spec in specs:
        record = ensure_font(spec, emitter=emitter, payload_cache=payload_cache)
        if record is None:
            continue
        cached_paths[spec.style or spec.filename] = record.path
    if not cached_paths:
        return None
    if len(cached_paths) == 1:
        return next(iter(cached_paths.values()))
    return cached_paths


def cache_fonts_for_families(
    families: list[str] | set[str] | tuple[str, ...],
    *,
    emitter: DiagnosticEmitter | None = None,
) -> tuple[dict[str, Path | dict[str, Path]], set[str]]:
    """Cache downloadable fonts required by ``families`` using the new registry."""
    cached: dict[str, Path | dict[str, Path]] = {}
    failures: set[str] = set()
    payload_cache: dict[str, bytes] = {}
    for family in families:
        specs = sources_for_family(family)
        if not specs:
            continue
        family_entries: dict[str, Path] = {}
        for spec in specs:
            record = ensure_font(spec, emitter=emitter, payload_cache=payload_cache)
            if record:
                family_entries[spec.style or spec.filename] = record.path
        if family_entries:
            cached[family] = (
                next(iter(family_entries.values()))
                if len(family_entries) == 1
                else family_entries
            )
        else:
            failures.add(family)
    return cached, failures


__all__ = [
    "FontRecord",
    "cache_fonts_for_families",
    "ensure_font",
    "ensure_font_cached",
    "font_cache_dir",
    "materialize_font",
]
