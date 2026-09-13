"""Plugin rendering fenced snippet blocks into standalone PDF assets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import contextlib
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag

from texsmith.core.coerce import coerce_bool
from texsmith.core.sources import is_markdown


try:  # Optional dependency: only needed when generating snippet previews.
    from PIL import Image, ImageDraw
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
import yaml

from texsmith.adapters.html_utils import coerce_attribute, gather_classes
from texsmith.core.conversion import ConversionRequest
from texsmith.core.diagnostics import DiagnosticEmitter, ensure_emitter
from texsmith.core.documents import (
    Document,
    TitleStrategy,
    _resolve_title_strategy,
    front_matter_has_title,
)
from texsmith.core.exceptions import AssetMissingError, InvalidNodeError, LatexRenderingError
from texsmith.core.front_matter import split_front_matter
from texsmith.core.metadata import PressMetadataError, normalise_press_metadata
from texsmith.core.templates import TemplateError, TemplateRuntime, load_template_runtime
from texsmith.core.templates.session import TemplateSession
from texsmith.core.user_dir import get_user_dir


SNIPPET_DIR = "snippets"
#: The fence attributes a snippet reads besides its body (HTML ``data-*`` or info string).
FENCE_ATTRIBUTES = ("caption", "label", "width", "layout", "config")
_SNIPPET_PREFIX = "snippet-"
_SNIPPET_CACHE_NAMESPACE = "snippets"
_SNIPPET_CACHE_FILENAME = "metadata.json"
_SNIPPET_CACHE_VERSION = 3
_log = logging.getLogger(__name__)
_SNIPPET_DUMP_ENV = "TEXSMITH_SNIPPET_DUMP_DIR"


def _require_pillow() -> tuple[Any, Any]:
    if Image is None or ImageDraw is None:
        raise AssetMissingError(
            "Pillow is required to generate snippet previews. Install the 'pillow' package."
        )
    return Image, ImageDraw


@dataclass(slots=True)
class SnippetBlock:
    """Parsed representation of a snippet fence."""

    content: str | None
    front_matter: dict[str, Any]
    sources: list[Path]
    layout: tuple[int, int] | None
    preview_dogear: bool
    template_id: str | None
    cwd: Path | None
    caption: str | None
    label: str | None
    figure_width: str | None
    template_overrides: dict[str, Any]
    digest: str
    bibliography_files: list[Path]
    promote_title: bool
    drop_title: bool
    suppress_title_metadata: bool

    @property
    def asset_basename(self) -> str:
        return f"{_SNIPPET_PREFIX}{self.digest}"


@dataclass(slots=True)
class SnippetAssets:
    """The rendered pair of a snippet: the PDF (LaTeX) and its PNG preview (web, Typst)."""

    pdf: Path
    png: Path


_SNIPPET_RUNTIME: TemplateRuntime | None = None
_SNIPPET_CACHE: _SnippetCache | None = None


@dataclass(slots=True)
class _SnippetCache:
    """Disk-backed cache storing rendered snippet artefacts."""

    root: Path
    metadata_path: Path
    metadata: dict[str, Any]
    dirty: bool = False

    def lookup(self, digest: str, template_version: str | None) -> SnippetAssets | None:
        """Return cached assets when they exist and match the signature."""
        entries = self._entries()
        payload = entries.get(digest)
        if not isinstance(payload, dict):
            self.discard(digest)
            return None

        signature = payload.get("signature")
        if signature and signature != digest:
            self.discard(digest)
            return None

        recorded_version = payload.get("template_version")
        if template_version and recorded_version and recorded_version != template_version:
            self.discard(digest)
            return None

        pdf_name = payload.get("pdf") or asset_filename(digest, ".pdf")
        png_name = payload.get("png") or asset_filename(digest, ".png")
        pdf_path = (self.root / pdf_name).resolve()
        png_path = (self.root / png_name).resolve()
        if not pdf_path.exists() or not png_path.exists():
            self.discard(digest)
            return None

        return SnippetAssets(pdf=pdf_path, png=png_path)

    def store(
        self,
        digest: str,
        pdf_path: Path,
        png_path: Path,
        *,
        template_version: str | None,
        block: SnippetBlock | None = None,
        source_path: Path | None = None,
    ) -> None:
        """Persist compiled assets in the cache directory."""
        entries = self._entries()
        cached_pdf = (self.root / asset_filename(digest, ".pdf")).resolve()
        cached_png = (self.root / asset_filename(digest, ".png")).resolve()
        cached_pdf.parent.mkdir(parents=True, exist_ok=True)
        cached_md = (self.root / asset_filename(digest, ".md")).resolve()

        cached_md_path: Path | None = None
        if block is not None and block.content is not None:
            try:
                cached_md.write_text(block.content, encoding="utf-8")
                cached_md_path = cached_md
            except OSError:
                cached_md_path = None

        attributes: dict[str, Any] | None = None
        if block is not None:
            attributes = {
                "caption": block.caption,
                "label": block.label,
                "figure_width": block.figure_width,
                "layout": block.layout,
                "overrides": block.template_overrides,
                "cwd": str(block.cwd) if block.cwd else None,
            }

        linked_files: dict[str, str] = {
            "pdf": cached_pdf.name,
            "png": cached_png.name,
        }
        if cached_md_path is not None:
            linked_files["md"] = cached_md_path.name

        source_hint = str(source_path) if source_path is not None else None

        try:
            source_pdf = Path(pdf_path).resolve()
            source_png = Path(png_path).resolve()
            if source_pdf != cached_pdf:
                shutil.copy2(source_pdf, cached_pdf)
            if source_png != cached_png:
                shutil.copy2(source_png, cached_png)
        except OSError:
            return

        entries[digest] = {
            "signature": digest,
            "pdf": cached_pdf.name,
            "png": cached_png.name,
            "template_version": template_version,
            "files": linked_files,
            "attributes": attributes,
            "source": source_hint,
        }
        self.dirty = True

    def discard(self, digest: str) -> None:
        """Remove a cache entry when it becomes invalid."""
        entries = self._entries()
        if digest in entries:
            entries.pop(digest, None)
            self.dirty = True

    def flush(self) -> None:
        """Persist metadata to disk when modified."""
        if not self.dirty:
            return

        payload = {
            "version": _SNIPPET_CACHE_VERSION,
            "entries": self._entries(),
        }
        tmp_path = self.metadata_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp_path.replace(self.metadata_path)
            self.dirty = False
        except OSError:
            return

    def _entries(self) -> dict[str, Any]:
        entries = self.metadata.setdefault("entries", {})
        if not isinstance(entries, dict):
            entries = {}
            self.metadata["entries"] = entries
        return entries


def _resolve_runtime() -> TemplateRuntime:
    global _SNIPPET_RUNTIME
    if _SNIPPET_RUNTIME is None:
        _SNIPPET_RUNTIME = load_template_runtime("snippet")
    return _SNIPPET_RUNTIME


def _resolve_cache_root() -> Path | None:
    try:
        return get_user_dir().cache_dir(_SNIPPET_CACHE_NAMESPACE)
    except OSError:
        return None


def _load_cache_metadata(path: Path) -> dict[str, Any]:
    default = {"version": _SNIPPET_CACHE_VERSION, "entries": {}}
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    except OSError:
        return default

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return default

    if payload.get("version") != _SNIPPET_CACHE_VERSION:
        return default

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        payload["entries"] = {}
    return payload


def _resolve_cache() -> _SnippetCache | None:
    global _SNIPPET_CACHE
    if _SNIPPET_CACHE is not None:
        return _SNIPPET_CACHE

    root = _resolve_cache_root()
    if root is None:
        return None

    metadata_path = root / _SNIPPET_CACHE_FILENAME
    metadata = _load_cache_metadata(metadata_path)
    _SNIPPET_CACHE = _SnippetCache(root=root, metadata_path=metadata_path, metadata=metadata)
    return _SNIPPET_CACHE


def _resolve_caches() -> list[_SnippetCache]:
    """Return the user-level cache only."""
    cache = _resolve_cache()
    return [cache] if cache is not None else []


def _resolve_base_dir(block: SnippetBlock, host_path: Path | None) -> Path:
    """Resolve the effective base directory for snippet assets."""
    if block.cwd:
        base = block.cwd
        if not base.is_absolute() and host_path is not None:
            try:
                return (host_path.parent / base).resolve()
            except OSError:
                return host_path.parent
        try:
            return base.resolve()
        except OSError:
            pass

    if host_path is not None:
        return host_path.parent

    try:
        return Path.cwd()
    except OSError:
        return Path()


def _resolve_template_runtime(
    block: SnippetBlock, documents: list[Document], base_dir: Path
) -> TemplateRuntime:
    """Select the template runtime from front matter when provided."""
    template_id: str | None = block.template_id

    def _template_from_front_matter(front_matter: Mapping[str, Any]) -> str | None:
        payload = dict(front_matter)
        with contextlib.suppress(PressMetadataError):
            normalise_press_metadata(payload)
        raw = payload.get("template")
        if raw:
            return str(raw).strip()
        press_section = payload.get("press")
        if isinstance(press_section, Mapping):
            inner = press_section.get("template")
            if inner:
                return str(inner).strip()
        return None

    for document in documents:
        front_matter = document.front_matter
        if not isinstance(front_matter, Mapping):
            continue
        candidate = _template_from_front_matter(front_matter)
        if candidate:
            template_id = candidate
            break

    if not template_id:
        return _resolve_runtime()

    # Try resolving relative to the snippet cwd / host directory first.
    candidates: list[str] = []
    tpl_path = Path(template_id)
    if not tpl_path.is_absolute():
        candidates.append(str((base_dir / tpl_path).resolve()))
    candidates.append(template_id)

    last_exc: Exception | None = None
    for candidate in candidates:
        try:
            return load_template_runtime(candidate)
        except TemplateError as exc:
            last_exc = exc
            continue

    if last_exc is not None:
        raise last_exc

    return _resolve_runtime()


def _resolve_snippet_dump_dir() -> Path | None:
    value = os.environ.get(_SNIPPET_DUMP_ENV, "").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_filename(digest: str, suffix: str) -> str:
    """Return the deterministic filename for a snippet artefact."""
    return f"{_SNIPPET_PREFIX}{digest}{suffix}"


def _hash_payload(
    content: str,
    overrides: Mapping[str, Any],
    *,
    cwd: str | None = None,
    template_id: str | None = None,
    layout: tuple[int, int] | None = None,
    sources: list[Path] | None = None,
    promote_title: bool = True,
    drop_title: bool = False,
    suppress_title: bool = False,
    transparent_corner: bool = False,
    front_matter: Mapping[str, Any] | None = None,
) -> str:
    def _hash_file(path: Path) -> str:
        try:
            data = path.read_bytes()
        except OSError:
            return ""
        return hashlib.sha256(data).hexdigest()

    def _normalise(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, Mapping):
            return {str(k): _normalise(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_normalise(item) for item in value]
        return value

    payload = {
        "content": content,
        "overrides": _normalise(dict(overrides)),
        "cwd": cwd,
        "template": template_id,
        "layout": layout,
        "sources": [
            {"path": str(path), "sha256": _hash_file(path)} for path in list(sources or [])
        ],
        "promote_title": promote_title,
        "drop_title": drop_title,
        "suppress_title": suppress_title,
        "transparent_corner": transparent_corner,
    }
    if front_matter:
        # The keys forwarded to the document itself now reach the body tmark
        # parses, so a preview cached before they did must not be reused. Only
        # written when there are any, to leave every other digest where it was.
        payload["front_matter"] = _normalise(dict(front_matter))
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _coerce_bool_option(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    resolved = coerce_bool(value)
    return default if resolved is None else resolved


def _detect_language(element: Tag) -> str | None:
    """Return the declared language from the fenced block classes."""
    candidates = [element, element.find("pre"), element.find("code")]
    for candidate in candidates:
        if candidate is None:
            continue
        for cls in gather_classes(candidate.get("class")):
            if cls.startswith("language-"):
                return cls[len("language-") :]
            if cls in {"yaml", "yml", "md", "markdown"}:
                return cls
    return None


def _frame_dogear_enabled(overrides: Mapping[str, Any]) -> bool:
    """Detect whether the page frame dogear should be shown for a snippet preview."""

    def _coerce_frame(value: Any) -> tuple[bool, bool]:
        if value is None:
            return False, False
        if isinstance(value, Mapping):
            enabled = _coerce_bool_option(value.get("enabled"), True)
            mode = value.get("mode")
            dogear = _coerce_bool_option(value.get("dogear"), True)
            if isinstance(mode, str):
                token = mode.strip().lower()
                if token == "border":
                    dogear = False
                    enabled = True
                elif token in {"dogear", "fold"}:
                    dogear = True
                    enabled = True
            if not enabled:
                return False, False
            return True, dogear
        if isinstance(value, (bool, int, float)):
            flag = bool(value)
            return flag, flag
        if isinstance(value, str):
            token = value.strip().lower()
            if not token or token in {"false", "off", "no", "0", "none"}:
                return False, False
            if token == "border":
                return True, False
            if coerce_bool(token):
                return True, True
        return False, False

    press_section = overrides.get("press") if isinstance(overrides, Mapping) else None
    frame_value = overrides.get("frame")
    if frame_value is None and isinstance(press_section, Mapping):
        frame_value = press_section.get("frame")
    enabled, dogear = _coerce_frame(frame_value)
    if enabled and dogear:
        return True

    fragments_value = overrides.get("fragments")
    if fragments_value is None and isinstance(press_section, Mapping):
        fragments_value = press_section.get("fragments")
    return isinstance(fragments_value, list) and any(str(f) == "ts-frame" for f in fragments_value)


def _load_yaml_mapping(payload: str) -> dict[str, Any]:
    """Parse a YAML string into a mapping, enforcing a dictionary output."""
    if not payload.strip():
        return {}
    try:
        loaded = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        raise InvalidNodeError(f"Invalid YAML snippet payload: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise InvalidNodeError("Snippet configuration must be a YAML mapping.")
    return dict(loaded)


def _resolve_layout_value(value: Any) -> tuple[int, int] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return (int(value[0]), int(value[1]))
        except (ValueError, TypeError):
            return None
    if isinstance(value, str):
        return _parse_layout(value)
    return None


def _resolve_base_dir_value(value: str | Path | None, host_path: Path | None) -> Path | None:
    if value is None:
        return host_path.parent if host_path is not None else None
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate
    if host_path is not None:
        try:
            return (host_path.parent / candidate).resolve()
        except OSError:
            return host_path.parent / candidate
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def _resolve_sources(raw_sources: Any, base_dir: Path | None) -> list[Path]:
    if raw_sources is None:
        return []
    if not isinstance(raw_sources, list):
        raise InvalidNodeError("The 'sources' field must be a list of paths.")

    resolved: list[Path] = []
    for entry in raw_sources:
        if entry is None:
            continue
        candidate = Path(str(entry))
        if not candidate.is_absolute():
            if base_dir is None:
                raise InvalidNodeError("Relative snippet sources require a host document path.")
            candidate = base_dir / candidate
        with contextlib.suppress(OSError):
            candidate = candidate.resolve()
        if not candidate.exists():
            raise InvalidNodeError(f"Snippet source '{candidate}' does not exist.")
        resolved.append(candidate)
    return resolved


def _merge_press_section(overrides: dict[str, Any], fragments: Any) -> None:
    if fragments is None:
        return
    press_section = overrides.setdefault("press", {})
    if not isinstance(press_section, dict):
        overrides["press"] = {"fragments": fragments}
        return
    existing = press_section.get("fragments")
    if existing is None:
        press_section["fragments"] = fragments
    elif isinstance(existing, dict) and isinstance(fragments, Mapping):
        press_section["fragments"] = {**existing, **dict(fragments)}
    elif isinstance(existing, list) and isinstance(fragments, list):
        press_section["fragments"] = [*existing, *fragments]
    else:
        press_section["fragments"] = fragments


def _extract_snippet_block(element: Tag, host_path: Path | None = None) -> SnippetBlock | None:
    pre_element = element.find("pre")
    code_element = element.find("code")

    classes = set(gather_classes(element.get("class")))
    classes.update(gather_classes(pre_element.get("class") if pre_element else None))
    classes.update(gather_classes(code_element.get("class") if code_element else None))
    if "snippet" not in classes:
        return None

    if code_element is None:
        raise InvalidNodeError("Snippet block is missing an inner <code> element.")
    raw_content = code_element.get_text(strip=False)

    def _attr(name: str) -> Any:
        for candidate in (element, pre_element, code_element):
            if candidate is None:
                continue
            for key in (name, f"data-{name}"):
                value = candidate.get(key)
                if value is not None:
                    return value
        return None

    def _meta_attrs() -> dict[str, str]:
        raw_meta = _attr("meta") or _attr("data-meta")
        if not raw_meta or not isinstance(raw_meta, str):
            return {}
        result: dict[str, str] = {}
        import shlex

        try:
            tokens = shlex.split(raw_meta)
        except ValueError:
            tokens = raw_meta.split()
        for token in tokens:
            if "=" not in token:
                continue
            key, val = token.split("=", 1)
            result[key.strip()] = val.strip().strip('"').strip("'")
        return result

    return build_snippet_block(
        raw_content,
        language=_detect_language(element),
        attributes={name: _attr(name) for name in FENCE_ATTRIBUTES},
        meta=_meta_attrs(),
        host_path=host_path,
    )


def build_snippet_block(
    raw_content: str,
    *,
    language: str | None,
    attributes: Mapping[str, Any] | None = None,
    meta: Mapping[str, str] | None = None,
    host_path: Path | None = None,
) -> SnippetBlock | None:
    """Parse a snippet fence into a :class:`SnippetBlock`; the pure half of the fence handling.

    ``raw_content`` is the fence body, ``language`` its info-string language,
    ``attributes`` the :data:`FENCE_ATTRIBUTES` the host element carried
    (``caption``, ``label``, ``width``, ``layout``, ``config``) and ``meta``
    the parsed ``data-meta`` tokens of the HTML reader. The HTML path
    (:func:`_extract_snippet_block`) and the tmark ``snippet`` pass both end
    here. ``None`` when the fence has neither inline content nor sources.
    """
    attrs = dict(attributes or {})
    meta_attrs = dict(meta or {})
    caption = coerce_attribute(attrs.get("caption")) or None
    label = coerce_attribute(attrs.get("label")) or None
    figure_width = coerce_attribute(attrs.get("width")) or None
    layout_literal: Any = coerce_attribute(attrs.get("layout")) or None
    config_literal = coerce_attribute(attrs.get("config")) or None

    config_from_file: dict[str, Any] = {}
    if config_literal:
        config_path = Path(config_literal)
        if not config_path.is_absolute():
            if host_path is None:
                raise InvalidNodeError("Relative snippet configuration requires a host document.")
            config_path = (host_path.parent / config_path).resolve()
        try:
            config_payload = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise InvalidNodeError(
                f"Unable to read snippet configuration '{config_path}': {exc}"
            ) from exc
        config_from_file = _load_yaml_mapping(config_payload)

    config_from_body: dict[str, Any] = {}
    inline_content: str | None = None
    if language in {"yaml", "yml"}:
        config_from_body = _load_yaml_mapping(raw_content)
    else:
        metadata, body = split_front_matter(raw_content)
        config_from_body = dict(metadata or {})
        if body.strip():
            inline_content = body
        if not config_from_body and inline_content is not None:
            # Fallback: accept pure-YAML snippet bodies even when the language class is missing.
            try:
                parsed_yaml = _load_yaml_mapping(raw_content)
            except InvalidNodeError:
                parsed_yaml = None
            if isinstance(parsed_yaml, dict) and parsed_yaml:
                config_from_body = parsed_yaml
                inline_content = None

    merged_config: dict[str, Any] = {**config_from_file, **config_from_body}
    figure_width = (
        coerce_attribute(merged_config.pop("width", figure_width))
        or coerce_attribute(meta_attrs.get("width"))
        or figure_width
    )
    caption = coerce_attribute(merged_config.pop("caption", caption)) or caption
    label = coerce_attribute(merged_config.pop("label", label)) or label
    layout_literal = merged_config.pop("layout", layout_literal) or layout_literal
    template_id_raw = merged_config.pop("template", None)
    template_id = coerce_attribute(template_id_raw) or None
    cwd_value = merged_config.pop("cwd", None)
    drop_title_value = _coerce_bool_option(merged_config.pop("drop_title", False), False)
    promote_title_value = _coerce_bool_option(
        merged_config.pop("promote_title", None),
        True,
    )
    suppress_title_value = _coerce_bool_option(
        merged_config.pop("suppress_title_metadata", merged_config.pop("suppress_title", None)),
        False,
    )

    base_dir = _resolve_base_dir_value(cwd_value, host_path)
    sources = _resolve_sources(merged_config.pop("sources", None), base_dir)
    bibliography_files = [
        path for path in sources if path.suffix.lower() in {".bib", ".bibtex", ".ris"}
    ]
    if inline_content is None and not sources:
        return None

    fragments = merged_config.pop("fragments", None)
    press_overrides = merged_config.pop("press", None)
    press_template: str | None = None
    template_overrides: dict[str, Any] = dict(merged_config)
    if press_overrides is not None:
        if not isinstance(press_overrides, Mapping):
            raise InvalidNodeError("The 'press' section must be a mapping.")
        press_payload = dict(press_overrides)
        press_template = coerce_attribute(press_payload.pop("template", None)) or None
        template_overrides["press"] = press_payload
    _merge_press_section(template_overrides, fragments)
    template_overrides.setdefault("glossary_inline", True)

    document_front_matter = (
        _document_front_matter(merged_config, press_overrides) if inline_content is not None else {}
    )

    layout = _resolve_layout_value(layout_literal)
    preview_dogear = _frame_dogear_enabled(template_overrides)
    if template_id is None and press_template:
        template_id = press_template
    if inline_content is not None and not sources and template_id is None:
        template_id = "snippet"
        preview_dogear = True
    elif inline_content is None and sources and template_id is None:
        template_id = "article"
    digest = _hash_payload(
        inline_content or "",
        template_overrides,
        cwd=str(base_dir) if base_dir else None,
        template_id=template_id,
        layout=layout,
        sources=sources,
        promote_title=promote_title_value,
        drop_title=drop_title_value,
        suppress_title=suppress_title_value,
        transparent_corner=preview_dogear,
        front_matter=document_front_matter,
    )

    return SnippetBlock(
        content=inline_content,
        front_matter=document_front_matter,
        sources=sources,
        layout=layout,
        preview_dogear=preview_dogear,
        template_id=template_id,
        cwd=base_dir,
        caption=caption,
        label=label,
        figure_width=figure_width,
        template_overrides=template_overrides,
        digest=digest,
        bibliography_files=bibliography_files,
        promote_title=promote_title_value,
        drop_title=drop_title_value,
        suppress_title_metadata=suppress_title_value,
    )


def _build_document(
    block: SnippetBlock,
    *,
    host_dir: Path,
    host_name: str,
    emitter: DiagnosticEmitter,
) -> Document | None:
    if not block.content:
        return None
    return _build_document_from_markup(
        block.content,
        host_dir / f"{host_name}-{block.asset_basename}.md",
        base_dir=host_dir,
        promote_title=block.promote_title,
        drop_title=block.drop_title,
        suppress_title=block.suppress_title_metadata,
        front_matter=block.front_matter,
        emitter=emitter,
    )


def _document_front_matter(config: Mapping[str, Any], press: Any) -> dict[str, Any]:
    """The fence keys that belong to the previewed document, not to the preview.

    Everything a fence declares is read as snippet configuration, but
    ``bibliography`` describes the document's own sources: it has to travel to
    the nested build as front matter. Both spellings are taken — the
    deprecated top-level one and ``press.sources.bibliography`` — and each is
    forwarded as written, so tmark applies the same migration it applies to a
    standalone document.
    """
    forwarded: dict[str, Any] = {}
    legacy = config.get("bibliography")
    if legacy is not None:
        forwarded["bibliography"] = legacy
    sources = press.get("sources") if isinstance(press, Mapping) else None
    declared = sources.get("bibliography") if isinstance(sources, Mapping) else None
    if declared is not None:
        forwarded["press"] = {"sources": {"bibliography": declared}}
    return forwarded


def _front_matter_prelude(front_matter: Mapping[str, Any] | None) -> str:
    """The fence's document keys written back as the YAML block tmark parses.

    A fence's own YAML is peeled off before the block is built — most of it
    configures the preview, not the document — so the keys that do belong to
    the document (``bibliography``) reach :class:`Document` as a mapping
    handed aside. That mapping only ever fed the legacy front matter; the
    passes read the *typed* front matter of the IR, which exists solely
    because tmark parsed the block itself. Re-emitting the block ahead of the
    body is what makes ``press.sources.bibliography`` visible to the ``doi``
    pass, so a preview resolves the citation its standalone twin resolves.
    """
    if not front_matter:
        return ""
    try:
        body = yaml.safe_dump(dict(front_matter), sort_keys=False, allow_unicode=True).strip()
    except yaml.YAMLError:  # pragma: no cover - defensive: the mapping came from YAML
        return ""
    return f"---\n{body}\n---\n\n" if body else ""


def _build_document_from_markup(
    content: str,
    source_path: Path,
    *,
    base_dir: Path,
    promote_title: bool,
    drop_title: bool,
    suppress_title: bool,
    emitter: DiagnosticEmitter,
    front_matter: Mapping[str, Any] | None = None,
) -> Document:
    """Parse a fence's inline body as a document of its own.

    ``source_path`` names a file that does not exist — the fence lives inside
    the host document — but it sits in ``base_dir`` so includes and assets
    resolve against the host's directory, as they did when the snippet was a
    nested Markdown render.

    It registers in the run's file table like any other source: the fence is a
    file the build met, and a diagnostic raised inside it has to name it.
    """
    return Document.from_markdown_text(
        _front_matter_prelude(front_matter) + content,
        base_dir / source_path.name,
        promote_title=promote_title,
        strip_heading=drop_title,
        suppress_title=suppress_title,
        base_level=0,
        title_strategy=TitleStrategy.DROP if drop_title else None,
        numbered=False,
        front_matter_overrides=front_matter,
        emitter=emitter,
    )


def _build_document_from_yaml(
    content: str,
    source_path: Path,
    *,
    promote_title: bool,
    drop_title: bool,
    suppress_title: bool,
    emitter: DiagnosticEmitter,
) -> Document:
    """Create a Document using YAML front matter only (no body)."""
    docs: list[Mapping[str, Any]] = []
    try:
        for doc in yaml.safe_load_all(content):
            if isinstance(doc, Mapping):
                docs.append(doc)
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise InvalidNodeError(f"Invalid YAML snippet source '{source_path}': {exc}") from exc

    payload: Mapping[str, Any] = docs[0] if docs else {}
    if not isinstance(payload, Mapping):
        raise InvalidNodeError(
            f"Snippet source '{source_path}' must contain a YAML mapping, got {type(payload)}."
        )
    title_strategy = _resolve_title_strategy(
        explicit=TitleStrategy.DROP if drop_title else None,
        promote_title=promote_title,
        strip_heading=drop_title,
        has_declared_title=front_matter_has_title(payload),
    )
    # An empty body parsed by tmark, with the YAML as its front matter: the
    # render path needs an ``ir`` on every document, a data-only source
    # included (``render_ir_document`` refuses a document without one).
    return Document.from_markdown_text(
        "",
        source_path,
        promote_title=promote_title,
        strip_heading=drop_title,
        suppress_title=suppress_title,
        base_level=0,
        title_strategy=title_strategy,
        numbered=False,
        front_matter_overrides=payload,
        emitter=emitter,
    )


def _build_documents_from_sources(
    sources: list[Path],
    *,
    promote_title: bool,
    drop_title: bool,
    suppress_title: bool,
    emitter: DiagnosticEmitter,
) -> list[Document]:
    documents: list[Document] = []
    for path in sources:
        suffix = path.suffix.lower()
        if is_markdown(path):
            documents.append(
                Document.from_markdown(
                    path,
                    # A preview renders the same source the document does, and
                    # reads it the same way: there is one reader left.
                    base_level=0,
                    title_strategy=None,
                    promote_title=promote_title,
                    strip_heading=drop_title,
                    suppress_title=suppress_title,
                    numbered=False,
                    emitter=emitter,
                )
            )
            continue
        if suffix in {".yml", ".yaml"}:
            try:
                yaml_content = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise InvalidNodeError(f"Unable to read snippet source '{path}': {exc}") from exc
            documents.append(
                _build_document_from_yaml(
                    yaml_content,
                    path,
                    promote_title=promote_title,
                    drop_title=drop_title,
                    suppress_title=suppress_title,
                    emitter=emitter,
                )
            )
            continue
        raise InvalidNodeError(
            f"Unsupported snippet source '{path}'. Only Markdown or YAML inputs are allowed."
        )
    return documents


def _compile_pdf(render_result: Any) -> Path:
    from texsmith.adapters.latex.engines import (
        EngineResult,
        build_engine_command,
        build_tex_env,
        compute_features,
        ensure_command_paths,
        missing_dependencies,
        parse_latex_log,
        resolve_engine,
        run_engine_command,
    )
    from texsmith.adapters.latex.pyxindy import is_available as pyxindy_available
    from texsmith.adapters.latex.tectonic import (
        BiberAcquisitionError,
        MakeglossariesAcquisitionError,
        TectonicAcquisitionError,
        select_biber_binary,
        select_makeglossaries,
        select_tectonic_binary,
    )

    engine_choice = resolve_engine("tectonic", render_result.template_engine)
    template_context = getattr(render_result, "template_context", None) or getattr(
        render_result, "context", None
    )
    features = compute_features(
        requires_shell_escape=render_result.requires_shell_escape,
        bibliography=render_result.has_bibliography,
        document_state=render_result.document_state,
        template_context=template_context,
    )
    biber_binary: Path | None = None
    makeglossaries_binary: Path | None = None
    bundled_bin: Path | None = None
    try:
        selection = select_tectonic_binary(False, console=None)
        if features.bibliography:
            biber_binary = select_biber_binary(console=None)
            bundled_bin = biber_binary.parent
        if features.has_glossary and not pyxindy_available():
            glossaries = select_makeglossaries(console=None)
            makeglossaries_binary = glossaries.path
            if glossaries.source == "bundled":
                bundled_bin = bundled_bin or glossaries.path.parent
    except (TectonicAcquisitionError, BiberAcquisitionError, MakeglossariesAcquisitionError) as exc:
        raise AssetMissingError(str(exc)) from exc
    tectonic_binary = selection.path

    available_bins: dict[str, Path] = {}
    if biber_binary:
        available_bins["biber"] = biber_binary
    if makeglossaries_binary:
        available_bins["makeglossaries"] = makeglossaries_binary

    missing = missing_dependencies(
        engine_choice,
        features,
        use_system_tectonic=False,
        available_binaries=available_bins or None,
    )
    if missing:
        formatted = ", ".join(sorted(missing))
        raise AssetMissingError(f"Missing LaTeX tools for snippet rendering: {formatted}")

    command_plan = ensure_command_paths(
        build_engine_command(
            engine_choice,
            features,
            main_tex_path=render_result.main_tex_path,
            tectonic_binary=tectonic_binary,
        )
    )
    env = build_tex_env(
        render_result.main_tex_path.parent,
        isolate_cache=True,
        extra_path=bundled_bin,
        biber_path=biber_binary,
    )
    result: EngineResult = run_engine_command(
        command_plan,
        backend=engine_choice.backend,
        workdir=render_result.main_tex_path.parent,
        env=env,
        console=None,
        classic_output=True,
        features=features,
    )
    if result.returncode != 0:
        log_path = command_plan.log_path
        messages = result.messages or parse_latex_log(log_path)
        detail = messages[0].summary if messages else f"{engine_choice.label} failed"
        raise LatexRenderingError(f"Failed to compile snippet: {detail} (log: {log_path})")

    return command_plan.pdf_path


def _load_pymupdf() -> object:
    try:
        import pymupdf as fitz  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        try:
            import fitz  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise AssetMissingError(
                "PyMuPDF is required to generate snippet previews. Install the 'pymupdf' package."
            ) from exc

    if not hasattr(fitz, "open"):  # type: ignore[attr-defined]
        raise AssetMissingError(
            "A conflicting 'fitz' package is installed. Remove it and install 'pymupdf' instead."
        )

    return fitz  # type: ignore[return-value]


def _pdf_to_png_grid(
    pdf_path: Path,
    png_path: Path,
    *,
    layout: tuple[int, int] | None = None,
    transparent_corner: bool = False,
    spacing: int | None = None,
    decorate_page: Callable[[Image.Image], Image.Image] | None = None,
) -> None:
    fitz = _load_pymupdf()
    image_lib, _ = _require_pillow()

    with fitz.open(pdf_path) as document:
        page_count = document.page_count
        if page_count == 0:
            raise LatexRenderingError(f"Snippet PDF '{pdf_path}' did not produce any pages.")

        cols, rows = (1, 1)
        if layout:
            c, r = layout
            if c > 0:
                cols = c
            if r > 0:
                rows = r
        pages_needed = cols * rows
        if pages_needed <= 0:
            cols = 1
            rows = 1
            pages_needed = 1
        use_pages = min(page_count, pages_needed)

        images: list[Image.Image] = []
        for index in range(use_pages):
            page = document.load_page(index)
            pixmap = page.get_pixmap(dpi=220)
            mode = "RGBA" if pixmap.alpha else "RGB"
            images.append(image_lib.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples))

    if not images:
        raise LatexRenderingError(f"Snippet PDF '{pdf_path}' did not produce any pages.")

    page_w, page_h = images[0].size
    inferred_spacing = 0
    if spacing is None and cols * rows > 1:
        inferred_spacing = max(round(min(page_w, page_h) * 0.04), 18)
    elif spacing:
        inferred_spacing = max(spacing, 0)

    total_w = cols * page_w + inferred_spacing * (cols - 1)
    total_h = rows * page_h + inferred_spacing * (rows - 1)
    canvas = image_lib.new("RGBA", (total_w, total_h), (255, 255, 255, 0))

    for idx, img in enumerate(images):
        if transparent_corner:
            img = _apply_dogear_transparency(img)
        if decorate_page is not None:
            img = decorate_page(img)

        r = idx // cols
        c = idx % cols
        x = c * (page_w + inferred_spacing)
        y = r * (page_h + inferred_spacing)
        mask = img if "A" in img.getbands() else None
        canvas.paste(img, (x, y), mask=mask)

    canvas.save(png_path)


def _apply_dogear_transparency(image: Image.Image) -> Image.Image:
    _, image_draw = _require_pillow()
    rgba = image.convert("RGBA")
    width, height = rgba.size
    if width <= 0 or height <= 0:
        return rgba
    magenta = (255, 0, 255, 255)
    seed_x = width - 2 if width > 1 else 0
    seed_y = 1 if height > 1 else 0
    try:
        image_draw.floodfill(rgba, (seed_x, seed_y), magenta, thresh=8)
    except Exception:
        return rgba

    pixels = []
    for r, g, b, a in rgba.getdata():
        if r == 255 and g == 0 and b == 255:
            pixels.append((r, g, b, 0))
        else:
            pixels.append((r, g, b, a))
    rgba.putdata(pixels)
    return rgba


def _parse_layout(value: str | None) -> tuple[int, int] | None:
    """Parse layout string like '2x2', '3', or '1x3' into (cols, rows)."""
    if not value:
        return None
    raw = value.strip().lower()
    if not raw:
        return None
    if "x" in raw:
        parts = raw.split("x", 1)
        try:
            cols = int(parts[0])
            rows = int(parts[1])
        except ValueError:
            return None
        return (cols, rows)
    try:
        cols = int(raw)
    except ValueError:
        return None
    return (cols, 1)


def ensure_snippet_assets(
    block: SnippetBlock,
    *,
    output_dir: Path,
    source_path: Path | str | None = None,
    emitter: DiagnosticEmitter | None = None,
) -> SnippetAssets:
    """Render snippet assets into the provided directory when missing."""
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    pdf_path = destination / asset_filename(block.digest, ".pdf")
    png_path = destination / asset_filename(block.digest, ".png")

    host_path = Path(source_path) if source_path is not None else destination / "snippet.md"
    host_dir = _resolve_base_dir(block, host_path)
    host_name = host_path.stem or "snippet"

    active_emitter = ensure_emitter(emitter)
    documents: list[Document] = []
    inline_document = _build_document(
        block, host_dir=host_dir, host_name=host_name, emitter=active_emitter
    )
    if inline_document is not None:
        documents.append(inline_document)

    bibliography_files = list(block.bibliography_files)
    document_sources: list[Path] = []
    for path in block.sources:
        suffix = path.suffix.lower()
        if suffix in {".bib", ".bibtex", ".ris"}:
            if path not in bibliography_files:
                bibliography_files.append(path)
            continue
        document_sources.append(path)

    if document_sources:
        documents.extend(
            _build_documents_from_sources(
                document_sources,
                promote_title=block.promote_title,
                drop_title=block.drop_title,
                suppress_title=block.suppress_title_metadata,
                emitter=active_emitter,
            )
        )

    if not documents:
        raise InvalidNodeError("Snippet block is empty; provide inline content or sources.")

    runtime = _resolve_template_runtime(block, documents, host_dir)
    merged_overrides = _merge_fragment_defaults(block.template_overrides, runtime)
    merged_overrides.setdefault("glossary_inline", True)
    dogear_enabled = _frame_dogear_enabled(merged_overrides) or block.preview_dogear
    caches = _resolve_caches()
    template_version = None
    if caches:
        info = getattr(runtime.instance, "info", None)
        if info is not None:
            version = getattr(info, "version", None)
            template_version = str(version) if version is not None else None

    pdf_missing = not pdf_path.exists()
    png_missing = not png_path.exists()
    assets = SnippetAssets(pdf=pdf_path, png=png_path)

    def _flush_caches() -> None:
        for cache in caches:
            cache.flush()

    def _store_in_caches() -> None:
        if not caches:
            return
        for cache in caches:
            cache.store(
                block.digest,
                pdf_path,
                png_path,
                template_version=template_version,
                block=block,
                source_path=Path(source_path) if source_path is not None else None,
            )
        _flush_caches()

    if not pdf_missing and not png_missing:
        _store_in_caches()
        return assets

    if caches and (pdf_missing or png_missing):
        for cache in caches:
            cached_assets = cache.lookup(block.digest, template_version=template_version)
            if cached_assets is None:
                continue
            try:
                if pdf_missing:
                    shutil.copy2(cached_assets.pdf, pdf_path)
                    pdf_missing = False
                if png_missing:
                    shutil.copy2(cached_assets.png, png_path)
                    png_missing = False
            except OSError:
                cache.discard(block.digest)
                continue
            if not pdf_missing and not png_missing:
                _store_in_caches()
                return assets
        _flush_caches()

    if not pdf_missing and png_missing:
        _pdf_to_png_grid(
            pdf_path,
            png_path,
            layout=block.layout,
            transparent_corner=dogear_enabled,
            spacing=None if block.layout else 0,
        )
        png_missing = False
        _store_in_caches()
        return assets

    _announce_build(block, source_path, emitter)

    settings = ConversionRequest(
        copy_assets=True,
        convert_assets=False,
        hash_assets=False,
        manifest=False,
    )
    session = TemplateSession(runtime=runtime, settings=settings, emitter=emitter)
    for document in documents:
        session.add_document(document)
    if bibliography_files:
        session.add_bibliography(*bibliography_files)
    if merged_overrides:
        session.update_options(merged_overrides)

    work_dir = destination / f".build-{block.digest}"
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    debug_dir: Path | None = None
    try:
        render_result = session.render(work_dir)
        compiled_pdf = _compile_pdf(render_result)
        shutil.copy2(compiled_pdf, pdf_path)
    except Exception as exc:
        # Preserve the work directory for post-mortem inspection when compilation fails.
        try:
            cache_root = _resolve_cache_root() or Path(tempfile.gettempdir()) / "texsmith"
            debug_dir = (cache_root / "snippet-fail" / block.digest).resolve()
            if debug_dir.exists():
                shutil.rmtree(debug_dir, ignore_errors=True)
            shutil.copytree(work_dir, debug_dir, dirs_exist_ok=True)
        except Exception:
            debug_dir = None
        if debug_dir is not None:
            raise exc.__class__(f"{exc} (debug: {debug_dir})") from exc
        raise
    else:
        dump_dir = _resolve_snippet_dump_dir()
        if dump_dir is not None:
            target_dir = dump_dir / block.asset_basename
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            shutil.copytree(work_dir, target_dir, dirs_exist_ok=True)
        shutil.rmtree(work_dir, ignore_errors=True)

    total_cells = 1
    if block.layout:
        cols, rows = block.layout
        total_cells = max(cols, 1) * max(rows, 1)
    _pdf_to_png_grid(
        pdf_path,
        png_path,
        layout=block.layout,
        transparent_corner=dogear_enabled,
        spacing=None if total_cells > 1 else 0,
        decorate_page=None,
    )

    _store_in_caches()
    return assets


def _merge_fragment_defaults(
    overrides: Mapping[str, Any] | None, runtime: TemplateRuntime | None
) -> dict[str, Any]:
    """Ensure explicit fragment overrides keep template defaults such as ts-extra."""

    def _as_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, Mapping):
            return [str(key) for key in value]
        return [str(value)]

    if not overrides:
        return {}

    merged: dict[str, Any] = dict(overrides)
    press_section = merged.get("press") if isinstance(merged.get("press"), Mapping) else None

    provided = merged.get("fragments")
    if provided is None and isinstance(press_section, Mapping):
        provided = press_section.get("fragments")

    defaults = _as_list(runtime.extras.get("fragments") if runtime and runtime.extras else [])
    requested = _as_list(provided)

    if defaults or requested:
        merged_fragments = list(dict.fromkeys([*defaults, *requested]))
        merged["fragments"] = merged_fragments
        if isinstance(press_section, Mapping):
            updated_press = dict(press_section)
            updated_press["fragments"] = merged_fragments
            merged["press"] = updated_press

    return merged


def rewrite_html_snippets(
    html: str,
    resolver: Callable[[SnippetBlock], tuple[str, str]],
    *,
    source_path: Path | str | None = None,
) -> str:
    """Replace snippet fences in an HTML fragment with linked previews."""
    if "snippet" not in html:
        return html
    host_path = Path(source_path) if source_path is not None else None

    soup = BeautifulSoup(html, "html.parser")
    mutated = False
    for element in soup.find_all(["div", "pre"]):
        block = _extract_snippet_block(element, host_path=host_path)
        if block is None:
            continue
        pdf_url, png_url = resolver(block)
        anchor = soup.new_tag(
            "a",
            href=pdf_url,
            target="_blank",
            rel="noopener noreferrer",
        )
        image_attrs = {"src": png_url, "alt": block.caption or "Snippet", "class": ["ts-snippet"]}
        if block.figure_width:
            image_attrs["width"] = block.figure_width
        image = soup.new_tag("img", **image_attrs)
        anchor.append(image)
        element.replace_with(anchor)
        mutated = True

    return str(soup) if mutated else html


def _announce_build(
    block: SnippetBlock, host_path: Path | str | None, emitter: DiagnosticEmitter | None
) -> None:
    """Emit an informational message when a snippet is actually compiled."""
    source_hint = f" from {host_path}" if host_path else ""
    short_digest = block.digest[:10] + "..." if block.digest else block.asset_basename
    _log.info("texsmith: building snippet %s%s", short_digest, source_hint)
    if emitter is not None:
        try:
            emitter.event(
                "snippet_build",
                {
                    "digest": block.digest,
                    "source": str(host_path) if host_path else "",
                    "destination": block.asset_basename,
                },
            )
        except Exception:
            _log.debug("failed to emit snippet_build event", exc_info=True)


__all__ = [
    "FENCE_ATTRIBUTES",
    "SNIPPET_DIR",
    "SnippetAssets",
    "SnippetBlock",
    "asset_filename",
    "build_snippet_block",
    "ensure_snippet_assets",
    "rewrite_html_snippets",
]
