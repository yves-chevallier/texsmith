"""Asset helpers shared across media and block handlers."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
from urllib.parse import unquote, urlparse

from texsmith.adapters.transformers import drawio2pdf, fetch_image, image2pdf, svg2pdf
from texsmith.core.context import RenderContext


_NATIVE_IMAGE_SUFFIXES: set[str] = {".png", ".jpg", ".jpeg", ".pdf"}
_FORCED_CONVERSION_SUFFIXES: set[str] = {".svg", ".drawio"}
_CONVERSION_CACHE_DIR = ".converted"


def store_local_image_asset(context: RenderContext, resolved: Path) -> Path:
    """Copy or convert a local asset and register it on the context."""
    asset_key = str(resolved)
    existing = context.assets.lookup(asset_key)
    if existing is not None:
        return existing

    suffix = resolved.suffix.lower()
    convert_requested = bool(context.runtime.get("convert_assets", False))
    needs_conversion = _requires_conversion(suffix, convert_requested)

    if needs_conversion:
        staged = _convert_local_asset(context, resolved, suffix)
        final_suffix = ".pdf"
    else:
        staged = resolved
        final_suffix = suffix or ".bin"

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
    suffix_hint = _normalise_suffix(_suffix_from_url(url), default=".pdf")

    artefact = fetch_image(
        url,
        output_dir=conversion_root,
        convert=convert_requested,
        output_suffix=suffix_hint,
        metadata=metadata,
    )

    final_suffix = _normalise_suffix(metadata.get("suffix"), default=".pdf")
    prefer_name = _extract_remote_name(url)

    return _persist_asset(
        context,
        asset_key=url,
        staged_path=artefact,
        suffix=final_suffix,
        source_path=None,
        prefer_name=prefer_name,
        force_hash=not bool(prefer_name),
    )


# --------------------------------------------------------------------------- helpers


def _requires_conversion(suffix: str, convert_requested: bool) -> bool:
    lowered = suffix.lower()
    if lowered == ".pdf":
        return False
    if lowered in _FORCED_CONVERSION_SUFFIXES:
        return True
    if lowered not in _NATIVE_IMAGE_SUFFIXES:
        return True
    return convert_requested


def _convert_local_asset(context: RenderContext, source: Path, suffix: str) -> Path:
    conversion_root = _conversion_cache_root(context)
    match suffix:
        case ".svg":
            return svg2pdf(source, output_dir=conversion_root)
        case ".drawio":
            return drawio2pdf(source, output_dir=conversion_root)
        case _:
            return image2pdf(source, output_dir=conversion_root)


def _conversion_cache_root(context: RenderContext) -> Path:
    root = context.assets.output_root / _CONVERSION_CACHE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


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


__all__ = ["store_local_image_asset", "store_remote_image_asset"]
