"""Asset helpers shared across media and block handlers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
from urllib.parse import unquote, urlparse

from texsmith.adapters.transformers import (
    drawio2pdf,
    fetch_image,
    image2pdf,
    mermaid2pdf,
    svg2pdf,
)
from texsmith.adapters.transformers.strategies import _cairo_dependency_hint
from texsmith.core.context import RenderContext
from texsmith.core.conversion.debug import ensure_emitter, record_event


_NATIVE_IMAGE_SUFFIXES: set[str] = {".png", ".jpg", ".jpeg", ".pdf"}
_FORCED_CONVERSION_SUFFIXES: set[str] = {".svg", ".drawio"}
_CONVERSION_CACHE_DIR = ".converted"
_ASSET_MANIFEST = "remote-assets.json"
_PLACEHOLDER_PDF = b"%PDF-1.4\n1 0 obj<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer<<>>\nstartxref\n9\n%%EOF\n"


def store_local_image_asset(context: RenderContext, resolved: Path) -> Path:
    """Copy or convert a local asset and register it on the context."""
    asset_key = str(resolved)
    existing = context.assets.lookup(asset_key)
    if existing is not None:
        return existing

    suffix = resolved.suffix.lower()
    convert_requested = bool(context.runtime.get("convert_assets", False))
    needs_conversion = _requires_conversion(suffix, convert_requested)
    emitter = ensure_emitter(context.runtime.get("emitter"))

    if needs_conversion:
        record_event(
            emitter,
            "asset_convert",
            {
                "source": str(resolved),
                "suffix": suffix,
                "reason": "requested" if convert_requested else "forced",
            },
        )
        staged = _convert_local_asset(context, resolved, suffix)
        final_suffix = ".pdf"
    else:
        staged = resolved
        final_suffix = suffix or ".bin"

    record_event(
        emitter,
        "asset_local",
        {
            "source": str(resolved),
            "stored_suffix": final_suffix,
            "converted": needs_conversion,
        },
    )
    return _persist_asset(
        context,
        asset_key=asset_key,
        staged_path=staged,
        suffix=final_suffix,
        source_path=resolved,
    )


def store_remote_image_asset(context: RenderContext, url: str) -> Path:
    """Fetch a remote asset, mirror it locally, and register it."""
    existing = context.assets.lookup(url)
    if existing is not None:
        return existing

    convert_requested = bool(context.runtime.get("convert_assets", False))
    metadata: dict[str, str] = {}
    conversion_root = _conversion_cache_root(context)
    manifest_path = conversion_root / _ASSET_MANIFEST
    manifest, manifest_dirty = _load_asset_manifest(manifest_path)
    url_suffix = _suffix_from_url(url)
    suffix_hint = _normalise_suffix(url_suffix, default="") if url_suffix else ""
    emitter = ensure_emitter(context.runtime.get("emitter"))

    record_event(
        emitter,
        "asset_fetch",
        {
            "url": url,
            "convert": convert_requested,
            "suffix_hint": suffix_hint,
        },
    )
    fetch_options: dict[str, Any] = {
        "convert": convert_requested,
        "metadata": metadata,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "manifest_dirty": manifest_dirty,
        "emitter": emitter,
    }
    if convert_requested:
        fetch_options["output_suffix"] = ".pdf"
    elif suffix_hint:
        fetch_options["output_suffix"] = suffix_hint
    artefact = fetch_image(
        url,
        output_dir=conversion_root,
        **fetch_options,
    )

    recorded_suffix = metadata.get("suffix") if metadata else None
    if not recorded_suffix:
        detected_suffix = _detect_file_suffix(Path(artefact))
        if detected_suffix:
            recorded_suffix = detected_suffix
    if recorded_suffix:
        final_suffix = _normalise_suffix(recorded_suffix)
    else:
        final_suffix = Path(artefact).suffix or ".pdf"
    prefer_name = _extract_remote_name(url)

    record_event(
        emitter,
        "asset_fetch_complete",
        {
            "url": url,
            "stored_suffix": final_suffix,
            "converted": convert_requested or suffix_hint in _FORCED_CONVERSION_SUFFIXES,
        },
    )
    if manifest_dirty["dirty"]:
        _save_asset_manifest(manifest_path, manifest)
    return _persist_asset(
        context,
        asset_key=url,
        staged_path=artefact,
        suffix=final_suffix,
        source_path=None,
        prefer_name=prefer_name,
        force_hash=not bool(prefer_name),
    )


def _requires_conversion(suffix: str, convert_requested: bool) -> bool:
    lowered = suffix.lower()
    if lowered == ".pdf":
        return False
    if lowered in _FORCED_CONVERSION_SUFFIXES:
        return True
    if lowered not in _NATIVE_IMAGE_SUFFIXES:
        return True
    return convert_requested


def _write_placeholder_pdf(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_PLACEHOLDER_PDF)
    return target


def _convert_local_asset(context: RenderContext, source: Path, suffix: str) -> Path:
    conversion_root = _conversion_cache_root(context)
    emitter = ensure_emitter(context.runtime.get("emitter"))
    match suffix:
        case ".svg":
            record_event(emitter, "diagram_generate", {"source": str(source), "kind": "svg"})
            try:
                return svg2pdf(source, output_dir=conversion_root, emitter=emitter)
            except Exception as exc:
                emitter.warning(
                    f"Falling back to placeholder PDF for SVG '{source}': {exc}. "
                    f"{_cairo_dependency_hint()}"
                )
                placeholder = conversion_root / f"{source.stem}.pdf"
                return _write_placeholder_pdf(placeholder)
        case ".drawio":
            record_event(emitter, "diagram_generate", {"source": str(source), "kind": "drawio"})
            emit_info = getattr(emitter, "info", None)
            if callable(emit_info):
                emit_info(f"Converting draw.io diagram: {source}")
            backend = context.runtime.get("diagrams_backend")
            return drawio2pdf(source, output_dir=conversion_root, backend=backend, emitter=emitter)
        case ".mmd" | ".mermaid":
            record_event(emitter, "diagram_generate", {"source": str(source), "kind": "mermaid"})
            emit_info = getattr(emitter, "info", None)
            if callable(emit_info):
                emit_info(f"Converting Mermaid diagram: {source}")
            backend = context.runtime.get("diagrams_backend")
            mermaid_config = context.runtime.get("mermaid_config")
            return mermaid2pdf(
                source,
                output_dir=conversion_root,
                backend=backend,
                mermaid_config=mermaid_config,
                emitter=emitter,
            )
        case _:
            record_event(emitter, "asset_convert", {"source": str(source), "kind": "image"})
            return image2pdf(source, output_dir=conversion_root, emitter=emitter)


def _conversion_cache_root(context: RenderContext) -> Path:
    root = context.assets.output_root / _CONVERSION_CACHE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_asset_manifest(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): dict(v) for k, v in data.items()}, {"dirty": False}
        except Exception:
            pass
    return {}, {"dirty": False}


def _save_asset_manifest(path: Path, manifest: dict[str, dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _persist_asset(
    context: RenderContext,
    *,
    asset_key: str,
    staged_path: Path,
    suffix: str,
    source_path: Path | None = None,
    prefer_name: str | None = None,
    force_hash: bool = False,
) -> Path:
    target = _determine_target_path(
        context,
        asset_key=asset_key,
        suffix=suffix,
        source_path=source_path,
        prefer_name=prefer_name,
        force_hash=force_hash,
    )
    staged = Path(staged_path)
    if staged.resolve() != target.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    return context.assets.register(asset_key, target)


def _determine_target_path(
    context: RenderContext,
    *,
    asset_key: str,
    suffix: str,
    source_path: Path | None,
    prefer_name: str | None,
    force_hash: bool,
) -> Path:
    hash_policy = force_hash or bool(context.runtime.get("hash_assets", False))
    base = context.assets.output_root

    if not hash_policy:
        candidate = None
        if source_path is not None:
            candidate = _relative_path_for_asset(context, source_path)
        if candidate is None and prefer_name:
            candidate = Path(prefer_name)
        if candidate is None and source_path is not None:
            candidate = Path(source_path.name)
        if candidate is not None:
            adjusted = candidate.with_suffix(suffix)
            candidate_path = (base / adjusted).resolve()
            if not _candidate_conflicts(context, candidate_path, asset_key):
                return candidate_path

    digest = hashlib.sha256(asset_key.encode("utf-8")).hexdigest()
    filename = f"{digest}{suffix}"
    return (base / filename).resolve()


def _candidate_conflicts(context: RenderContext, candidate: Path, asset_key: str) -> bool:
    candidate_resolved = candidate.resolve()
    for existing_key, stored in context.assets.assets_map.items():
        stored_path = Path(stored).resolve()
        if stored_path == candidate_resolved:
            return existing_key != asset_key
    return False


def _relative_path_for_asset(context: RenderContext, source: Path) -> Path | None:
    project_dir = getattr(context.config, "project_dir", None)
    if project_dir:
        try:
            return source.relative_to(Path(project_dir))
        except ValueError:
            pass
    document_path = context.runtime.get("document_path")
    if document_path:
        try:
            return source.relative_to(Path(document_path).parent)
        except ValueError:
            pass
    source_dir = context.runtime.get("source_dir")
    if source_dir:
        try:
            return source.relative_to(Path(source_dir))
        except ValueError:
            pass
    return None


def _extract_remote_name(url: str) -> str | None:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path or "")).name
    return name or None


def _suffix_from_url(url: str) -> str:
    parsed = urlparse(url)
    return Path(parsed.path or "").suffix.lower()


def _normalise_suffix(value: str | None, default: str = ".bin") -> str:
    candidate = (value or "").strip()
    if not candidate:
        return default
    return candidate if candidate.startswith(".") else f".{candidate.lstrip('.')}"


def _detect_file_suffix(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return None
    if header.startswith(b"%PDF"):
        return ".pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"\x89PNG"):
        return ".png"
    if header.startswith(b"GIF8"):
        return ".gif"
    if header.startswith(b"BM"):
        return ".bmp"
    if header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    return None


__all__ = ["store_local_image_asset", "store_remote_image_asset"]
