"""Concrete converter strategies with caching and error handling."""

from __future__ import annotations

import atexit
from collections.abc import Callable, Mapping, Sequence
import contextlib
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from io import BytesIO
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import threading
from threading import Lock, Thread
from typing import Any, ClassVar, TypeVar
from urllib.parse import unquote, urlparse
from urllib.request import urlopen
import warnings

from texsmith.core.conversion.debug import ensure_emitter, record_event
from texsmith.core.exceptions import TransformerExecutionError
from texsmith.core.user_dir import get_user_dir

from ..docker import DockerLimits, VolumeMount, run_container
from .base import CachedConversionStrategy
from .utils import normalise_pdf_version, points_to_mm


_EXPORT3_URL = "https://app.diagrams.net/export3.html"
_DEFAULT_MERMAID_CONFIG_PATH = (
    Path(__file__).resolve().parents[4]
    / "texsmith"
    / "templates"
    / "article"
    / "template"
    / "assets"
    / "mermaid-config.json"
)
_DEFAULT_MERMAID_CONFIG: dict[str, Any] = {}
if _DEFAULT_MERMAID_CONFIG_PATH.exists():
    try:
        _DEFAULT_MERMAID_CONFIG = json.loads(_DEFAULT_MERMAID_CONFIG_PATH.read_text("utf-8"))
    except Exception:
        _DEFAULT_MERMAID_CONFIG = {}


MERMAID_CLI_HINT_PATHS: tuple[Path, ...] = (Path("/snap/bin/mmdc"),)
DRAWIO_CLI_HINT_PATHS: tuple[Path, ...] = (Path("/snap/bin/drawio"),)

DPI_CSS = 96
DPI_TARGET = 72
SCALE = DPI_CSS / DPI_TARGET
_PLAYWRIGHT_APT_PACKAGES: tuple[str, ...] = (
    "libglib2.0-0",
    "libnspr4",
    "libnss3",
    "libatk1.0-0",
    "libatk-bridge2.0-0",
    "libcups2",
    "libxkbcommon0",
    "libatspi2.0-0",
    "libxcomposite1",
    "libxdamage1",
    "libxfixes3",
    "libxrandr2",
    "libgbm1",
    "libcairo2",
    "libpango-1.0-0",
    "libasound2",
)
_PLAYWRIGHT_BACKEND_HINT = (
    "If Playwright cannot run in this environment, re-run with "
    "--diagrams-backend local or --diagrams-backend docker."
)

_PLACEHOLDER_PDF = b"%PDF-1.4\n1 0 obj<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer<<>>\nstartxref\n9\n%%EOF\n"


def _emit_dependency_warning(emitter: Any, message: str) -> None:
    """Send a warning through the emitter or fall back to Python warnings."""
    handled = False
    if emitter is not None:
        try:
            emitter.warning(message)
            handled = True
        except Exception:
            handled = False
    if not handled:
        warnings.warn(message, stacklevel=3)


def _playwright_dependency_hint() -> str:
    packages = " ".join(_PLAYWRIGHT_APT_PACKAGES)
    return (
        "Install Playwright browser dependencies with `playwright install-deps` "
        f"(Debian/Ubuntu: `sudo apt-get install {packages}`)."
    )


def _cairo_dependency_hint() -> str:
    return (
        "CairoSVG requires the system cairo library (package: libcairo2). "
        "Install it via your package manager to enable SVG conversion."
    )


def _write_placeholder_pdf(target: Path) -> None:
    """Write a minimal placeholder PDF when conversion cannot proceed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_PLACEHOLDER_PDF)


def _wrap_playwright_error(exc: Exception, emitter: Any = None) -> TransformerExecutionError:
    """Return a structured error with guidance for missing Playwright deps."""
    base_message = str(exc).strip() or exc.__class__.__name__
    hint = f"{_playwright_dependency_hint()} {_PLAYWRIGHT_BACKEND_HINT}"
    _emit_dependency_warning(emitter, hint)
    message = f"Playwright backend failed: {base_message}. {hint}"
    return TransformerExecutionError(message)


def _resolve_cli(names: Sequence[str], hints: Sequence[Path]) -> tuple[str | None, bool]:
    """Return an executable path and whether it was discovered via $PATH."""
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved, True
    for candidate in hints:
        if candidate and candidate.exists():
            return str(candidate), False
    return None, False


def _warn_add_to_path(command: str, path: str) -> None:
    """Emit a guidance warning when a CLI was found outside $PATH."""
    message = (
        f"Found '{command}' at '{path}'. Add this directory to PATH so TeXSmith can "
        "detect it automatically."
    )
    warnings.warn(message, stacklevel=3)


def _script_fallback_command(command: Sequence[str]) -> list[str] | None:
    """Return a Windows-friendly command for script files without extensions."""
    if os.name != "nt" or not command:
        return None
    executable = Path(command[0])
    suffix = executable.suffix.lower()
    if suffix in {".exe", ".bat", ".cmd", ".com"}:
        return None
    if not executable.exists():
        return None
    interpreter: str | None = None
    try:
        first_line = executable.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except Exception:
        first_line = ""
    if first_line.startswith("#!"):
        shebang = first_line[2:].strip()
        try:
            parts = shlex.split(shebang)
        except ValueError:
            parts = [shebang]
        if parts and parts[0] == "/usr/bin/env" and len(parts) > 1:
            interpreter = parts[1]
        elif parts:
            interpreter = parts[0]
    if interpreter is None:
        interpreter = sys.executable
    if shutil.which(interpreter) is None and interpreter != sys.executable:
        interpreter = sys.executable
    return [interpreter, str(executable), *command[1:]]


def _run_cli(command: list[str], *, cwd: Path, description: str) -> None:
    """Execute a local CLI, raising a transformer error on failure."""

    def _execute(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            cwd=cwd,
        )

    invoked = command
    primary_error: OSError | None = None
    try:
        result = _execute(command)
    except OSError as exc:
        primary_error = exc
        fallback = _script_fallback_command(command)
        if fallback is None:
            raise TransformerExecutionError(f"Failed to execute {description}: {exc}") from exc
        invoked = fallback
        try:
            result = _execute(fallback)
        except OSError as fallback_exc:
            raise TransformerExecutionError(
                f"Failed to execute {description}: {fallback_exc}"
            ) from fallback_exc

    if result.returncode != 0:
        detail = (result.stderr or "").strip() or (result.stdout or "").strip()
        message = f"{description} exited with status {result.returncode}"
        if primary_error is not None and invoked is not command:
            message = f"{message} (initial failure: {primary_error})"
        if detail:
            message = f"{message}: {detail}"
        raise TransformerExecutionError(message)


def _compose_fallback_error(
    tool: str, primary: Exception, fallback: Exception
) -> TransformerExecutionError:
    """Combine CLI and Docker failures into a single diagnostic."""
    message = f"{tool} CLI failed: {primary}\nDocker fallback also failed: {fallback}"
    return TransformerExecutionError(message)


class SvgToPdfStrategy(CachedConversionStrategy):
    """Convert inline SVG payloads or files to PDF using CairoSVG."""

    def __init__(self) -> None:
        super().__init__("svg")

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        emitter = options.get("emitter")
        svg_text = _read_text(source)

        try:
            import cairosvg  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = (
                "cairosvg is required to convert SVG assets. "
                "Install 'cairosvg' or provide a custom converter."
            )
            raise TransformerExecutionError(msg) from exc

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"), write_to=str(target))
        except OSError as exc:
            hint = _cairo_dependency_hint()
            _emit_dependency_warning(emitter, hint)
            raise TransformerExecutionError(
                f"Failed to render SVG with CairoSVG: {exc}. {hint}"
            ) from exc
        except Exception as exc:
            raise TransformerExecutionError(f"Failed to render SVG with CairoSVG: {exc}") from exc
        normalise_pdf_version(target)
        return target


class ImageToPdfStrategy(CachedConversionStrategy):
    """Convert bitmap images to PDF using Pillow."""

    def __init__(self) -> None:
        super().__init__("image")

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        image_path = Path(source)
        if not image_path.exists():
            msg = f"Image file '{image_path}' does not exist"
            raise TransformerExecutionError(msg)

        try:
            from PIL import Image  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = (
                "Pillow is required to convert images. "
                "Install 'Pillow' or provide a custom converter."
            )
            raise TransformerExecutionError(msg) from exc

        with Image.open(image_path) as image:
            pdf_ready = image.convert("RGB")
            pdf_ready.save(target, "PDF")

        normalise_pdf_version(target)

        return target


class FetchImageStrategy(CachedConversionStrategy):
    """Fetch a remote image, normalise it to PDF, and cache the result."""

    _NATIVE_SUFFIXES: ClassVar[set[str]] = {".png", ".jpg", ".jpeg", ".pdf"}
    _MIMETYPE_SUFFIXES: ClassVar[dict[str, str]] = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/pjpeg": ".jpg",
        "image/svg+xml": ".svg",
        "text/svg": ".svg",
        "application/svg+xml": ".svg",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "application/pdf": ".pdf",
    }

    def __init__(self, timeout: float = 10.0) -> None:
        super().__init__("fetch-image")
        self.timeout = timeout

    def output_suffix(self, source: Any, options: dict[str, Any]) -> str:
        candidate = options.get("output_suffix")
        if isinstance(candidate, str) and candidate.strip():
            suffix = candidate.strip()
            return suffix if suffix.startswith(".") else f".{suffix.lstrip('.')}"
        return super().output_suffix(source, options)

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        emitter = ensure_emitter(options.get("emitter"))
        url = str(source)
        convert_requested = bool(options.get("convert", True))
        metadata: dict[str, str] | None = options.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            metadata = None
        manifest = options.get("manifest")
        manifest = manifest if isinstance(manifest, dict) else {}
        manifest_dirty = options.get("manifest_dirty")
        if not isinstance(manifest_dirty, dict):
            manifest_dirty = {"dirty": False}
        cache_entry = manifest.get(url)
        response: Any | None = None

        try:
            import requests  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = "requests is required to fetch remote images."
            raise TransformerExecutionError(msg) from exc

        user_agent = None
        candidate = options.get("user_agent")
        if isinstance(candidate, str) and candidate.strip():
            user_agent = candidate.strip()
        elif os.getenv("TEXSMITH_HTTP_USER_AGENT"):
            user_agent = os.environ["TEXSMITH_HTTP_USER_AGENT"].strip()
        else:
            try:
                version = importlib_metadata.version("texsmith")
            except importlib_metadata.PackageNotFoundError:
                version = "unknown"
            user_agent = f"texsmith/{version}"

        headers = {"User-Agent": user_agent}

        reuse_reason = None
        cached_path: Path | None = None
        if isinstance(cache_entry, dict):
            cached_path = self._existing_cached_path(cache_entry)
            wiki_title = self._wikimedia_title(url)
            if wiki_title and cached_path:
                wiki_meta = self._fetch_wikimedia_metadata(wiki_title, user_agent)
                if (
                    wiki_meta
                    and cache_entry.get("sha1")
                    and wiki_meta.get("sha1") == cache_entry.get("sha1")
                ):
                    reuse_reason = "wikimedia"
                    cache_entry.update(wiki_meta)
            if reuse_reason is None and cached_path:
                conditional_headers = self._conditional_headers(cache_entry)
                if conditional_headers:
                    try:
                        response = requests.get(
                            url, timeout=self.timeout, headers={**headers, **conditional_headers}
                        )
                    except requests.exceptions.RequestException:
                        response = None
                    if response is not None and response.status_code == 304:
                        reuse_reason = "etag"
                        cache_entry["etag"] = response.headers.get("ETag", cache_entry.get("etag"))
                        cache_entry["last_modified"] = response.headers.get(
                            "Last-Modified", cache_entry.get("last_modified")
                        )
                    elif response is not None and not response.ok:
                        response = None
        else:
            response = None

        if reuse_reason and cached_path:
            if metadata is not None and cache_entry:
                if cache_entry.get("content_type"):
                    metadata["content_type"] = str(cache_entry["content_type"])
                if cache_entry.get("suffix"):
                    metadata["suffix"] = str(cache_entry["suffix"])
            manifest[url] = self._build_manifest_entry(
                url,
                cache_entry or {},
                target_path=target,
                content_type=cache_entry.get("content_type"),
                suffix=cache_entry.get("suffix") or target.suffix or ".bin",
            )
            manifest_dirty["dirty"] = True
            self._copy_cached_artifact(cached_path, target)
            record_event(emitter, "asset_fetch_cached", {"url": url, "reason": reuse_reason})
            return target

        if response is None:
            try:
                response = requests.get(url, timeout=self.timeout, headers=headers)
            except requests.exceptions.RequestException as exc:  # pragma: no cover - network
                msg = f"Failed to fetch image '{url}': {exc}"
                raise TransformerExecutionError(msg) from exc

        status_code = getattr(response, "status_code", 200)
        if status_code == 304 and cached_path:
            reuse_reason = "etag"
            if metadata is not None and cache_entry:
                if cache_entry.get("content_type"):
                    metadata["content_type"] = str(cache_entry["content_type"])
                if cache_entry.get("suffix"):
                    metadata["suffix"] = str(cache_entry["suffix"])
            manifest[url] = self._build_manifest_entry(
                url,
                cache_entry or {},
                target_path=target,
                content_type=cache_entry.get("content_type"),
                suffix=cache_entry.get("suffix") or target.suffix or ".bin",
            )
            manifest_dirty["dirty"] = True
            self._copy_cached_artifact(cached_path, target)
            record_event(emitter, "asset_fetch_cached", {"url": url, "reason": reuse_reason})
            return target

        if not getattr(response, "ok", False):
            raise TransformerExecutionError(f"Failed to fetch image '{url}': HTTP {status_code}")

        content_type = response.headers.get("Content-Type", "")
        mimetype = content_type.split(";", 1)[0].strip().lower()
        suffix = self._suffix_from_request(url, mimetype)

        native_supported = self._can_emit_native(suffix)
        should_convert = not native_supported
        if convert_requested and suffix.lower() != ".pdf":
            should_convert = True
        final_suffix = ".pdf" if should_convert else suffix or ".pdf"

        wiki_meta: dict[str, Any] = {}
        wiki_title = self._wikimedia_title(url)
        if wiki_title:
            wiki_meta = self._fetch_wikimedia_metadata(wiki_title, user_agent) or {}

        if metadata is not None:
            metadata["content_type"] = mimetype
            metadata["suffix"] = final_suffix
        manifest_extra = {
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "sha1": wiki_meta.get("sha1"),
            "timestamp": wiki_meta.get("timestamp"),
            "size": self._safe_int(response.headers.get("Content-Length")) or wiki_meta.get("size"),
        }

        if not should_convert:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
            manifest[url] = self._build_manifest_entry(
                url,
                cache_entry or {},
                target_path=target,
                content_type=mimetype,
                suffix=final_suffix,
                extra=manifest_extra,
            )
            manifest_dirty["dirty"] = True
            return target

        if mimetype in ("image/svg+xml", "text/svg", "application/svg+xml"):
            try:
                import cairosvg  # type: ignore[import]
            except ImportError as exc:  # pragma: no cover - optional dependency
                msg = "cairosvg is required to convert remote SVG assets."
                raise TransformerExecutionError(msg) from exc
            try:
                cairosvg.svg2pdf(bytestring=response.content, write_to=str(target))
            except OSError as exc:
                hint = _cairo_dependency_hint()
                _emit_dependency_warning(emitter, hint)
                raise TransformerExecutionError(
                    f"Failed to convert remote SVG '{url}': {exc}. {hint}"
                ) from exc
            except Exception as exc:
                raise TransformerExecutionError(
                    f"Failed to convert remote SVG '{url}': {exc}"
                ) from exc
            normalise_pdf_version(target)
            return target

        try:
            from PIL import Image  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = "Pillow is required to normalise remote images."
            raise TransformerExecutionError(msg) from exc
        try:
            with Image.open(BytesIO(response.content)) as image:
                pdf_ready = image.convert("RGB")
                pdf_ready.save(target, "PDF")
        except Exception as exc:
            raise TransformerExecutionError(
                f"Failed to convert remote image '{url}': {exc}"
            ) from exc

        normalise_pdf_version(target)
        manifest[url] = self._build_manifest_entry(
            url,
            cache_entry or {},
            target_path=target,
            content_type=mimetype,
            suffix=final_suffix,
            extra=manifest_extra,
        )
        manifest_dirty["dirty"] = True

        return target

    def _suffix_from_request(self, url: str, mimetype: str) -> str:
        parsed = urlparse(url)
        suffix = Path(parsed.path or "").suffix.lower()
        if suffix:
            return suffix
        return self._MIMETYPE_SUFFIXES.get(mimetype, "")

    def _can_emit_native(self, suffix: str) -> bool:
        lowered = suffix.lower()
        if not lowered:
            return False
        return lowered in self._NATIVE_SUFFIXES

    def _existing_cached_path(self, entry: Mapping[str, Any]) -> Path | None:
        candidate = entry.get("path")
        if isinstance(candidate, str):
            path = Path(candidate)
            if path.exists():
                return path
        return None

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None

    def _conditional_headers(self, entry: Mapping[str, Any]) -> dict[str, str]:
        headers: dict[str, str] = {}
        etag = entry.get("etag")
        last_modified = entry.get("last_modified")
        if isinstance(etag, str) and etag.strip():
            headers["If-None-Match"] = etag.strip()
        if isinstance(last_modified, str) and last_modified.strip():
            headers["If-Modified-Since"] = last_modified.strip()
        return headers

    def _copy_cached_artifact(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() == target.resolve():
            return
        target.write_bytes(source.read_bytes())

    def _build_manifest_entry(
        self,
        url: str,
        base: Mapping[str, Any],
        *,
        target_path: Path,
        content_type: str | None,
        suffix: str,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = dict(base or {})
        entry.update(
            {
                "url": url,
                "path": str(target_path),
                "content_type": content_type,
                "suffix": suffix,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if extra:
            entry.update({k: v for k, v in extra.items() if v is not None})
        return entry

    def _wikimedia_title(self, url: str) -> str | None:
        parsed = urlparse(url)
        if "wikimedia.org" not in parsed.netloc and "wikipedia.org" not in parsed.netloc:
            return None
        name = Path(parsed.path).name
        if not name:
            return None
        return f"File:{unquote(name)}"

    def _fetch_wikimedia_metadata(self, title: str, user_agent: str) -> dict[str, Any] | None:
        try:
            import requests  # type: ignore[import]
        except Exception:
            return None
        params = {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "timestamp|sha1|size|url",
            "format": "json",
        }
        headers = {"User-Agent": user_agent}
        try:
            resp = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                params=params,
                headers=headers,
                timeout=5,
            )
        except requests.exceptions.RequestException:
            return None
        if not resp.ok:
            return None
        try:
            payload = resp.json()
        except Exception:
            return None
        try:
            page = next(iter(payload.get("query", {}).get("pages", {}).values()))
            info = page.get("imageinfo", [])
            if not info:
                return None
            entry = info[0]
            return {
                "sha1": entry.get("sha1"),
                "timestamp": entry.get("timestamp"),
                "size": entry.get("size"),
                "source_url": entry.get("url"),
            }
        except Exception:
            return None


class PdfMetadataStrategy:
    """Inspect PDF files and expose structural metadata."""

    def __call__(
        self,
        source: Path | str,
        *,
        output_dir: Path,
        **options: Any,
    ) -> dict[str, Any]:
        pdf_path = Path(source)
        if not pdf_path.exists():
            msg = f"PDF file '{pdf_path}' does not exist"
            raise TransformerExecutionError(msg)

        try:
            import pypdf  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = "pypdf is required to inspect PDF metadata."
            raise TransformerExecutionError(msg) from exc

        reader = pypdf.PdfReader(pdf_path)
        pages: list[dict[str, Any]] = []
        for page in reader.pages:
            media_box = page.mediabox
            pages.append(
                {
                    "width": points_to_mm(float(media_box.width)),
                    "height": points_to_mm(float(media_box.height)),
                }
            )
        return {"pages": pages}


class NotConfiguredStrategy:
    """Strategy used to signal that a converter must be provided by the host."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(
        self,
        source: Path | str,
        *,
        output_dir: Path,
        **_: Any,
    ):
        msg = (
            f"No converter configured for '{self.name}'. "
            f"Register a strategy via 'register_converter(\"{self.name}\", strategy)'."
        )
        raise TransformerExecutionError(msg)


def _read_text(source: Path | str) -> str:
    if isinstance(source, Path):
        return source.read_text("utf-8")
    if isinstance(source, str):
        candidate = Path(source)
        try:
            if candidate.exists():
                return candidate.read_text("utf-8")
        except OSError:
            return source
        return source
    return str(source)


def _texsmith_cache_root() -> Path:
    return get_user_dir().cache_dir(create=False)


T = TypeVar("T")


class _PlaywrightWorker:
    """Run Playwright sync API calls on an isolated thread."""

    @classmethod
    def run(cls, func: Callable[[], T]) -> T:
        result: list[T] = []
        error: list[BaseException] = []

        def target() -> None:
            try:
                result.append(func())
            except BaseException as exc:  # pragma: no cover - pass through
                error.append(exc)
            finally:
                with contextlib.suppress(Exception):
                    _PlaywrightManager._cleanup()  # noqa: SLF001

        thread = Thread(target=target, name="texsmith-playwright", daemon=True)
        thread.start()
        thread.join(timeout=120)
        if thread.is_alive():
            # Defensive: avoid hanging CI if Playwright download/launch stalls.
            raise TransformerExecutionError("Playwright worker timed out after 120s")

        if error:
            raise error[0]
        return result[0]


class _PlaywrightManager:
    """Keep a shared Playwright browser alive across conversions."""

    _playwright = None
    _browser = None
    _owner_thread_id: ClassVar[int | None] = None
    _lock: ClassVar[Lock] = Lock()
    _cleanup_registered = False

    @classmethod
    def ensure_browser(cls, *, emitter: Any = None) -> Any:
        with cls._lock:
            current_thread = threading.get_ident()
            # Always recreate per call to avoid cross-thread greenlet issues.
            cls._cleanup_unlocked()
            try:
                from playwright._impl._errors import Error as PlaywrightError
                from playwright.sync_api import sync_playwright
            except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
                raise TransformerExecutionError(
                    "Playwright backend requested but the 'playwright' package is not installed."
                ) from exc

            cache_root = _texsmith_cache_root() / "playwright"
            browser_cache = cache_root / "browsers"
            browser_cache.mkdir(parents=True, exist_ok=True)
            # Playwright reads PLAYWRIGHT_BROWSERS_PATH during startup, so set it before start().
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browser_cache))
            # Silence Node.js deprecation spew (e.g., url.parse) while staying compatible with Py3.10+.
            existing_node_opts = os.environ.get("NODE_OPTIONS", "")
            if "--no-deprecation" not in existing_node_opts:
                merged_opts = (existing_node_opts + " --no-deprecation").strip()
                os.environ["NODE_OPTIONS"] = merged_opts

            try:
                cls._playwright = sync_playwright().start()
            except PlaywrightError as exc:
                raise _wrap_playwright_error(exc, emitter) from exc

            try:
                cls._browser = cls._playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                msg = str(exc)
                if "Executable doesn't exist" in msg or "Failed to launch" in msg:
                    subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "chromium"],
                        env=os.environ,
                        check=True,
                    )
                    cls._browser = cls._playwright.chromium.launch(headless=True)
                else:
                    cls._playwright.stop()
                    cls._playwright = None
                    raise _wrap_playwright_error(exc, emitter) from exc
            cls._owner_thread_id = current_thread
            if not cls._cleanup_registered:
                atexit.register(cls._cleanup)
                cls._cleanup_registered = True
            return cls._browser

    @classmethod
    def _cleanup(cls) -> None:
        with cls._lock:
            cls._cleanup_unlocked()

    @classmethod
    def _cleanup_unlocked(cls) -> None:
        try:
            if cls._browser is not None:
                cls._browser.close()
        except Exception:
            pass
        try:
            if cls._playwright is not None:
                cls._playwright.stop()
        except Exception:
            pass
        cls._browser = None
        cls._playwright = None
        cls._owner_thread_id = None


class MermaidToPdfStrategy(CachedConversionStrategy):
    """Render Mermaid diagrams to PDF using the official CLI image."""

    def __init__(
        self,
        image: str = "minlag/mermaid-cli",
        *,
        default_theme: str = "neutral",
    ) -> None:
        super().__init__("mermaid")
        self.image = image
        self.default_theme = default_theme

    def output_suffix(self, source: Any, options: dict[str, Any]) -> str:
        fmt = str(options.get("format", "pdf") or "pdf").lower()
        return ".png" if fmt == "png" else ".pdf"

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        emitter = options.get("emitter")
        backend = str(options.get("backend") or options.get("diagrams_backend") or "auto").lower()
        format_opt = str(options.get("format", "pdf") or "pdf").lower()
        working_dir = cache_dir / "mermaid"
        working_dir.mkdir(parents=True, exist_ok=True)

        content = _read_text(source)
        input_name = options.get("input_name") or "diagram.mmd"
        output_ext = ".png" if format_opt == "png" else ".pdf"
        output_name = options.get("output_name") or f"diagram{output_ext}"
        theme = options.get("theme", self.default_theme)
        mermaid_config = options.get("mermaid_config")

        input_path = working_dir / input_name
        input_path.write_text(content, encoding="utf-8")

        extra_args: list[str] = []
        config_path = options.get("config_filename") or options.get("config_path")
        if config_path:
            config_data = Path(config_path).read_text("utf-8")
            config_file = working_dir / "mermaid-config.json"
            config_file.write_text(config_data, encoding="utf-8")
            extra_args.extend(["-c", config_file.name])
        if not config_path and _DEFAULT_MERMAID_CONFIG_PATH.exists():
            extra_args.extend(["-c", str(_DEFAULT_MERMAID_CONFIG_PATH)])

        if "backgroundColor" in options:
            extra_args.extend(["-b", str(options["backgroundColor"])])

        extra_args.extend(options.get("cli_args", []))

        produced = working_dir / output_name
        if produced.exists():
            produced.unlink()

        primary_error: TransformerExecutionError | None = None
        if backend in {"playwright", "auto"}:
            try:
                self._run_playwright(
                    content,
                    target=produced,
                    format_opt=format_opt,
                    theme=theme,
                    mermaid_config=mermaid_config,
                    emitter=emitter,
                )
            except TransformerExecutionError as exc:
                primary_error = exc
                if backend == "playwright":
                    raise

        cli_path, discovered_via_path = _resolve_cli(["mmdc"], MERMAID_CLI_HINT_PATHS)
        cli_error: TransformerExecutionError | None = None
        if backend in {"local", "auto"} and not produced.exists() and cli_path:
            if not discovered_via_path:
                _warn_add_to_path("mmdc", cli_path)
            try:
                self._run_local_cli(
                    cli_path,
                    working_dir=working_dir,
                    input_name=input_path.name,
                    output_name=output_name,
                    theme=theme,
                    extra_args=extra_args,
                    format_opt=format_opt,
                )
            except TransformerExecutionError as exc:
                cli_error = exc
                if backend == "local":
                    raise

        docker_error: TransformerExecutionError | None = None
        if backend in {"docker", "auto"} and not produced.exists():
            if shutil.which("docker") is None:
                docker_error = TransformerExecutionError("Docker is not available on this system.")
            else:
                docker_args = [
                    "-i",
                    input_path.name,
                    "-o",
                    output_name,
                ]
                if format_opt:
                    docker_args.extend(["-O", format_opt])
                docker_args.extend(["-t", str(theme)])
                docker_args.extend(extra_args)

                try:
                    run_container(
                        self.image,
                        args=docker_args,
                        mounts=[VolumeMount(working_dir, "/data")],
                        environment={"HOME": "/data/home"},
                        workdir="/data",
                        limits=DockerLimits(cpus=1.0, memory="1g", pids_limit=512),
                    )
                except TransformerExecutionError as exc:
                    docker_error = exc
                    if backend == "docker":
                        raise
                    if cli_error is not None:
                        raise _compose_fallback_error("Mermaid", cli_error, exc) from exc
                    if primary_error is not None:
                        raise _compose_fallback_error("Mermaid", primary_error, exc) from exc

        if not produced.exists():
            if cli_error and docker_error:
                raise _compose_fallback_error("Mermaid", cli_error, docker_error)
            if primary_error and cli_error:
                raise _compose_fallback_error("Mermaid", primary_error, cli_error)
            if primary_error and docker_error:
                raise _compose_fallback_error("Mermaid", primary_error, docker_error)
            if primary_error:
                raise primary_error
            raise TransformerExecutionError("Mermaid conversion did not produce the expected file.")

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, target)
        if target.suffix.lower() == ".pdf":
            normalise_pdf_version(target)
        return target

    def _run_local_cli(
        self,
        executable: str,
        *,
        working_dir: Path,
        input_name: str,
        output_name: str,
        theme: str,
        extra_args: list[str],
        format_opt: str,
    ) -> None:
        command = [
            executable,
            "-i",
            input_name,
            "-o",
            output_name,
        ]
        if format_opt:
            command.extend(["-O", format_opt])
        command.extend(["-t", str(theme)])
        command.extend(extra_args)
        _run_cli(command, cwd=working_dir, description="Mermaid CLI")

    def _run_playwright(
        self,
        content: str,
        *,
        target: Path,
        format_opt: str,
        theme: str,
        mermaid_config: Any,
        emitter: Any = None,
    ) -> None:
        def task() -> None:
            try:
                from playwright._impl._errors import Error as PlaywrightError
            except Exception:  # pragma: no cover - defensive import fallback
                PlaywrightError = Exception  # noqa: N806

            try:
                browser = _PlaywrightManager.ensure_browser(emitter=emitter)
                page = browser.new_page(viewport={"width": 2400, "height": 1800})
                page.set_content(
                    """<!doctype html>
<html><head><meta charset="utf-8" />
<script src="https://unpkg.com/mermaid@11/dist/mermaid.min.js"></script>
</head><body style="margin:0; background:white;"><div id="container"></div></body></html>""",
                    wait_until="load",
                )
                resolved_config: dict[str, Any] = {}

                if isinstance(mermaid_config, Mapping):
                    resolved_config = dict(mermaid_config)
                elif isinstance(mermaid_config, str):
                    cfg_path = Path(mermaid_config).expanduser()
                    if cfg_path.exists():
                        try:
                            resolved_config = json.loads(cfg_path.read_text("utf-8"))
                        except Exception:
                            resolved_config = {}

                if not resolved_config:
                    resolved_config = (
                        dict(_DEFAULT_MERMAID_CONFIG) if _DEFAULT_MERMAID_CONFIG else {}
                    )
                resolved_config.setdefault("startOnLoad", False)
                resolved_config.setdefault("theme", theme)
                page.evaluate("cfg => { window.mermaid.initialize(cfg); }", resolved_config)
                svg = page.evaluate(
                    """
async (code) => {
  const result = await window.mermaid.render("theGraph", code);
  const header = '<?xml version="1.0" encoding="UTF-8"?>\\n';
  return header + result.svg;
}
""",
                    content,
                )
                page.close()
                target.parent.mkdir(parents=True, exist_ok=True)
                if format_opt == "png":
                    self._svg_to_png(browser, svg, target)
                else:
                    self._svg_to_pdf(browser, svg, target)
            except PlaywrightError as exc:
                raise _wrap_playwright_error(exc, emitter) from exc
            except TransformerExecutionError:
                raise
            except Exception as exc:
                raise TransformerExecutionError(
                    f"Mermaid Playwright backend failed: {exc}"
                ) from exc

        _PlaywrightWorker.run(task)

    def _svg_to_pdf(self, browser: Any, svg: str, target: Path) -> None:
        page = browser.new_page()
        page.set_content(f"<html><body style='margin:0; display:inline-block'>{svg}</body></html>")
        locator = page.locator("svg")
        box = locator.bounding_box()
        width = math.ceil(box["width"]) if box else 800
        height = math.ceil(box["height"]) if box else 600

        scaled_width = math.ceil(width * SCALE)
        scaled_height = math.ceil(height * SCALE)

        page.set_viewport_size({"width": scaled_width, "height": scaled_height})
        page.pdf(
            path=str(target),
            print_background=True,
            width=f"{width}px",
            height=f"{height}px",
            page_ranges="1",
        )
        page.close()

    def _svg_to_png(self, browser: Any, svg: str, target: Path) -> None:
        page = browser.new_page(viewport={"width": 2400, "height": 1800})
        page.set_content(f"<html><body style='margin:0; display:inline-block'>{svg}</body></html>")
        locator = page.locator("svg")
        box = locator.bounding_box()
        screenshot_kwargs: dict[str, Any] = {"path": str(target)}
        if box:
            screenshot_kwargs["clip"] = {
                "x": box["x"],
                "y": box["y"],
                "width": box["width"],
                "height": box["height"],
            }
        page.screenshot(**screenshot_kwargs)
        page.close()


class DrawioToPdfStrategy(CachedConversionStrategy):
    """Convert draw.io diagrams using selectable backends (playwright, local, docker)."""

    def __init__(
        self,
        image: str = "rlespinasse/drawio-desktop-headless",
    ) -> None:
        super().__init__("drawio")
        self.image = image
        self.export_url = _EXPORT3_URL

    def output_suffix(self, source: Any, options: dict[str, Any]) -> str:
        fmt = str(options.get("format", "pdf") or "pdf").lower()
        return ".png" if fmt == "png" else ".pdf"

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        emitter = options.get("emitter")
        backend = str(options.get("backend") or options.get("diagrams_backend") or "auto").lower()
        format_opt = str(options.get("format", "pdf") or "pdf").lower()
        theme = str(options.get("theme", "auto") or "auto")

        source_path = Path(source)
        if not source_path.exists():
            raise TransformerExecutionError(f"Draw.io file '{source_path}' does not exist.")

        working_dir = cache_dir / "drawio" / target.stem
        if working_dir.exists():
            shutil.rmtree(working_dir, ignore_errors=True)
        if working_dir.exists():
            working_dir = cache_dir / "drawio" / f"{target.stem}-{os.getpid()}"
        working_dir.mkdir(parents=True, exist_ok=True)
        home_dir = working_dir / "home"
        home_dir.mkdir(parents=True, exist_ok=True)

        diagram_name = source_path.name
        working_source = working_dir / diagram_name
        shutil.copy2(source_path, working_source)

        output_ext = ".png" if format_opt == "png" else ".pdf"
        output_name = options.get("output_name") or f"{working_source.stem}{output_ext}"
        produced = working_dir / output_name
        if produced.exists():
            produced.unlink()

        primary_error: TransformerExecutionError | None = None
        if backend in {"playwright", "auto"}:
            try:
                self._run_playwright(
                    working_source,
                    target=produced,
                    cache_dir=cache_dir,
                    format_opt=format_opt,
                    theme=theme,
                    emitter=emitter,
                )
            except TransformerExecutionError as exc:
                primary_error = exc
                if backend == "playwright":
                    raise
        cli_path, discovered_via_path = _resolve_cli(["drawio", "draw.io"], DRAWIO_CLI_HINT_PATHS)
        cli_error: TransformerExecutionError | None = None
        if backend in {"local", "auto"} and not produced.exists() and cli_path:
            if not discovered_via_path:
                _warn_add_to_path("drawio", cli_path)
            try:
                self._run_local_cli(
                    cli_path,
                    working_dir=working_dir,
                    source_name=working_source.name,
                    output_name=output_name,
                    options=options | {"format": format_opt},
                )
            except TransformerExecutionError as exc:
                cli_error = exc
                if backend == "local":
                    raise

        docker_error: TransformerExecutionError | None = None
        if backend in {"docker", "auto"} and not produced.exists():
            if shutil.which("docker") is None:
                docker_error = TransformerExecutionError("Docker is not available on this system.")
            else:
                mounts: list[VolumeMount] = [VolumeMount(working_dir, "/data")]
                passwd_path = Path("/etc/passwd")
                group_path = Path("/etc/group")
                if passwd_path.exists():
                    mounts.append(VolumeMount(passwd_path, "/etc/passwd", read_only=True))
                if group_path.exists():
                    mounts.append(VolumeMount(group_path, "/etc/group", read_only=True))
                docker_args = [
                    "--export",
                    "--format",
                    format_opt,
                    "--output",
                    ".",
                ]

                if options.get("crop", False):
                    docker_args.extend(["--crop"])

                dpi = options.get("dpi")
                if dpi:
                    docker_args.extend(["--quality", str(dpi)])

                docker_args.append(working_source.name)

                try:
                    run_container(
                        self.image,
                        args=docker_args,
                        mounts=mounts,
                        environment={
                            "HOME": "/data/home",
                            "XDG_CACHE_HOME": "/data/home/.cache",
                            "XDG_CONFIG_HOME": "/data/home/.config",
                        },
                        workdir="/data",
                        use_host_user=True,
                        limits=DockerLimits(cpus=1.0, memory="1g", pids_limit=512),
                    )
                except TransformerExecutionError as exc:
                    docker_error = exc
                    if backend == "docker":
                        raise
                    if cli_error is not None:
                        raise _compose_fallback_error("draw.io", cli_error, exc) from exc
                    if primary_error is not None:
                        raise _compose_fallback_error("draw.io", primary_error, exc) from exc

        if not produced.exists():
            if cli_error and docker_error:
                raise _compose_fallback_error("draw.io", cli_error, docker_error)
            if primary_error and cli_error:
                raise _compose_fallback_error("draw.io", primary_error, cli_error)
            if primary_error and docker_error:
                raise _compose_fallback_error("draw.io", primary_error, docker_error)
            if primary_error:
                raise primary_error
            raise TransformerExecutionError("draw.io conversion did not produce the expected file.")

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, target)
        if target.suffix.lower() == ".pdf":
            normalise_pdf_version(target)
        return target

    def _run_local_cli(
        self,
        executable: str,
        *,
        working_dir: Path,
        source_name: str,
        output_name: str,
        options: dict[str, Any],
    ) -> None:
        fmt = str(options.get("format", "pdf") or "pdf").lower()
        command = [
            executable,
            "--export",
            source_name,
            "--format",
            fmt,
            "--output",
            output_name,
        ]

        if options.get("crop", False):
            command.append("--crop")

        dpi = options.get("dpi")
        if dpi:
            command.extend(["--quality", str(dpi)])

        _run_cli(command, cwd=working_dir, description="draw.io CLI")

    def _run_playwright(
        self,
        source: Path,
        *,
        target: Path,
        cache_dir: Path,
        format_opt: str,
        theme: str,
        emitter: Any = None,
    ) -> None:
        def task() -> None:
            try:
                from playwright._impl._errors import Error as PlaywrightError
            except Exception:  # pragma: no cover - defensive import fallback
                PlaywrightError = Exception  # noqa: N806

            try:
                cache_root = _texsmith_cache_root() / "playwright"
                browser_cache = cache_root / "browsers"
                browser_cache.mkdir(parents=True, exist_ok=True)
                os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browser_cache))

                export_page = cache_root / "export3.html"
                export_url = None
                if not export_page.exists():
                    try:
                        with urlopen(self.export_url) as response:
                            export_page.write_bytes(response.read())
                    except Exception:
                        export_url = self.export_url

                xml = source.read_text(encoding="utf-8")
                browser = _PlaywrightManager.ensure_browser(emitter=emitter)
                page = browser.new_page(viewport={"width": 2400, "height": 1800})
                page.goto(export_page.as_uri() if export_url is None else export_url)
                page.wait_for_function("() => typeof window.render === 'function'", timeout=30_000)
                page.evaluate(
                    """
() => {
  const orig = window.render;
  window.render = function(data) {
    const g = orig.call(window, data);
    window.__lastGraph = g;
    window.__lastData = data;
    return g;
  };
}
"""
                )
                payload = {
                    "xml": xml,
                    "format": "svg",
                    "border": 0,
                    "scale": 1,
                    "w": 0,
                    "h": 0,
                    "extras": "{}",
                    "embedXml": "1",
                    "embedImages": "1",
                    "embedFonts": "1",
                    "shadows": "1",
                    "theme": theme,
                }
                page.evaluate("data => window.render(data)", payload)
                page.wait_for_selector("#LoadingComplete", state="attached", timeout=60_000)
                svg = page.evaluate(
                    """
() => {
  const graph = window.__lastGraph;
  const data = window.__lastData || {};
  const done = document.getElementById('LoadingComplete');
  const scale = done ? parseFloat(done.getAttribute('scale')) || graph.view.scale || 1 : graph.view.scale || 1;
  let bg = graph.background;
  if (bg === mxConstants.NONE) bg = null;

  const svgRoot = graph.getSvg(bg, scale, data.border || 0, false, null,
    true, null, null, null, null, null, data.theme || 'auto');

  if (data.embedXml === '1') {
    svgRoot.setAttribute('content', data.xml);
  }

  const header = (Graph.xmlDeclaration || '') + '\\n' +
    (Graph.svgDoctype || '') + '\\n' +
    (Graph.svgFileComment || '');
  return header + '\\n' + mxUtils.getXml(svgRoot);
}
"""
                )
                page.close()
                target.parent.mkdir(parents=True, exist_ok=True)
                if format_opt == "png":
                    self._svg_to_png(browser, svg, target)
                else:
                    self._svg_to_pdf(browser, svg, target)
            except PlaywrightError as exc:
                raise _wrap_playwright_error(exc, emitter) from exc
            except TransformerExecutionError:
                raise
            except Exception as exc:
                raise TransformerExecutionError(
                    f"draw.io Playwright backend failed: {exc}"
                ) from exc

        _PlaywrightWorker.run(task)

    def _svg_to_pdf(self, browser: Any, svg: str, target: Path) -> None:
        page = browser.new_page()
        page.set_content(f"<html><body style='margin:0; display:inline-block'>{svg}</body></html>")
        locator = page.locator("svg")
        box = locator.bounding_box()
        width = math.ceil(box["width"]) if box else 800
        height = math.ceil(box["height"]) if box else 600
        page.set_viewport_size({"width": width, "height": height})
        page.pdf(
            path=str(target),
            print_background=True,
            width=f"{width}px",
            height=f"{height}px",
            page_ranges="1",
        )
        page.close()

    def _svg_to_png(self, browser: Any, svg: str, target: Path) -> None:
        page = browser.new_page(viewport={"width": 2400, "height": 1800})
        page.set_content(f"<html><body style='margin:0; display:inline-block'>{svg}</body></html>")
        locator = page.locator("svg")
        box = locator.bounding_box()
        if box:
            page.screenshot(
                path=str(target),
                clip={
                    "x": box["x"],
                    "y": box["y"],
                    "width": box["width"],
                    "height": box["height"],
                },
            )
        else:
            page.screenshot(path=str(target))
        page.close()
