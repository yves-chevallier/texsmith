"""Concrete converter strategies with caching and error handling."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
from typing import Any
import warnings

from texsmith.core.exceptions import TransformerExecutionError

from ..docker import DockerLimits, VolumeMount, run_container
from .base import CachedConversionStrategy
from .utils import normalise_pdf_version, points_to_mm


MERMAID_CLI_HINT_PATHS: tuple[Path, ...] = (Path("/snap/bin/mmdc"),)
DRAWIO_CLI_HINT_PATHS: tuple[Path, ...] = (Path("/snap/bin/drawio"),)


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


def _run_cli(command: list[str], *, cwd: Path, description: str) -> None:
    """Execute a local CLI, raising a transformer error on failure."""
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except OSError as exc:
        raise TransformerExecutionError(f"Failed to execute {description}: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or "").strip() or (result.stdout or "").strip()
        message = f"{description} exited with status {result.returncode}"
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
        cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"), write_to=str(target))
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

    def __init__(self, timeout: float = 10.0) -> None:
        super().__init__("fetch-image")
        self.timeout = timeout

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        url = str(source)

        try:
            import requests  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = "requests is required to fetch remote images."
            raise TransformerExecutionError(msg) from exc

        try:
            response = requests.get(url, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:  # pragma: no cover - network
            msg = f"Failed to fetch image '{url}': {exc}"
            raise TransformerExecutionError(msg) from exc
        if not response.ok:
            raise TransformerExecutionError(
                f"Failed to fetch image '{url}': HTTP {response.status_code}"
            )

        content_type = response.headers.get("Content-Type", "")
        mimetype = content_type.split(";", 1)[0].strip().lower()

        if mimetype in ("image/svg+xml", "text/svg", "application/svg+xml"):
            try:
                import cairosvg  # type: ignore[import]
            except ImportError as exc:  # pragma: no cover - optional dependency
                msg = "cairosvg is required to convert remote SVG assets."
                raise TransformerExecutionError(msg) from exc

            cairosvg.svg2pdf(bytestring=response.content, write_to=str(target))
            normalise_pdf_version(target)
            return target

        try:
            from PIL import Image  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = "Pillow is required to normalise remote images."
            raise TransformerExecutionError(msg) from exc

        with Image.open(BytesIO(response.content)) as image:
            pdf_ready = image.convert("RGB")
            pdf_ready.save(target, "PDF")

        normalise_pdf_version(target)

        return target


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

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        working_dir = cache_dir / "mermaid"
        working_dir.mkdir(parents=True, exist_ok=True)

        content = _read_text(source)
        input_name = options.get("input_name") or "diagram.mmd"
        output_name = options.get("output_name") or "diagram.pdf"
        theme = options.get("theme", self.default_theme)

        input_path = working_dir / input_name
        input_path.write_text(content, encoding="utf-8")

        extra_args: list[str] = []
        config_path = options.get("config_filename") or options.get("config_path")
        if config_path:
            config_data = Path(config_path).read_text("utf-8")
            config_file = working_dir / "mermaid-config.json"
            config_file.write_text(config_data, encoding="utf-8")
            extra_args.extend(["-c", config_file.name])

        if "backgroundColor" in options:
            extra_args.extend(["-b", str(options["backgroundColor"])])

        extra_args.extend(options.get("cli_args", []))

        produced = working_dir / output_name
        if produced.exists():
            produced.unlink()

        cli_path, discovered_via_path = _resolve_cli(["mmdc"], MERMAID_CLI_HINT_PATHS)
        cli_error: TransformerExecutionError | None = None
        ran_local = False
        if cli_path:
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
                )
                ran_local = True
            except TransformerExecutionError as exc:
                cli_error = exc

        if not ran_local:
            docker_args = [
                "-i",
                input_path.name,
                "-o",
                output_name,
                "-f",
                "-t",
                str(theme),
            ]
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
                if cli_error is not None:
                    raise _compose_fallback_error("Mermaid", cli_error, exc) from exc
                raise
        elif not produced.exists():
            cli_error = cli_error or TransformerExecutionError(
                "Mermaid CLI did not produce the expected PDF artifact."
            )
            docker_args = [
                "-i",
                input_path.name,
                "-o",
                output_name,
                "-f",
                "-t",
                str(theme),
            ]
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
                raise _compose_fallback_error("Mermaid", cli_error, exc) from exc

        if not produced.exists():
            raise TransformerExecutionError(
                "Mermaid CLI did not produce the expected PDF artifact."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, target)
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
    ) -> None:
        command = [
            executable,
            "-i",
            input_name,
            "-o",
            output_name,
            "-f",
            "-t",
            str(theme),
        ]
        command.extend(extra_args)
        _run_cli(command, cwd=working_dir, description="Mermaid CLI")


class DrawioToPdfStrategy(CachedConversionStrategy):
    """Convert draw.io diagrams to PDF using the headless desktop image."""

    def __init__(
        self,
        image: str = "rlespinasse/drawio-desktop-headless",
    ) -> None:
        super().__init__("drawio")
        self.image = image

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        source_path = Path(source)
        if not source_path.exists():
            raise TransformerExecutionError(f"Draw.io file '{source_path}' does not exist.")

        working_dir = cache_dir / "drawio"
        working_dir.mkdir(parents=True, exist_ok=True)

        diagram_name = source_path.name
        working_source = working_dir / diagram_name
        shutil.copy2(source_path, working_source)

        output_name = options.get("output_name") or f"{working_source.stem}.pdf"
        produced = working_dir / output_name
        if produced.exists():
            produced.unlink()

        cli_path, discovered_via_path = _resolve_cli(["drawio", "draw.io"], DRAWIO_CLI_HINT_PATHS)
        cli_error: TransformerExecutionError | None = None
        ran_local = False
        if cli_path:
            if not discovered_via_path:
                _warn_add_to_path("drawio", cli_path)
            try:
                self._run_local_cli(
                    cli_path,
                    working_dir=working_dir,
                    source_name=working_source.name,
                    output_name=output_name,
                    options=options,
                )
                ran_local = True
            except TransformerExecutionError as exc:
                cli_error = exc

        if not ran_local:
            docker_args = [
                "--export",
                "--format",
                "pdf",
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
                    mounts=[VolumeMount(working_dir, "/data")],
                    environment={"HOME": "/data/home"},
                    workdir="/data",
                    use_host_user=False,
                    limits=DockerLimits(cpus=1.0, memory="1g", pids_limit=512),
                )
            except TransformerExecutionError as exc:
                if cli_error is not None:
                    raise _compose_fallback_error("draw.io", cli_error, exc) from exc
                raise
        elif not produced.exists():
            cli_error = cli_error or TransformerExecutionError(
                "draw.io CLI did not produce the expected PDF artifact."
            )
            docker_args = [
                "--export",
                "--format",
                "pdf",
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
                    mounts=[VolumeMount(working_dir, "/data")],
                    environment={"HOME": "/data/home"},
                    workdir="/data",
                    use_host_user=False,
                    limits=DockerLimits(cpus=1.0, memory="1g", pids_limit=512),
                )
            except TransformerExecutionError as exc:
                raise _compose_fallback_error("draw.io", cli_error, exc) from exc

        if not produced.exists():
            raise TransformerExecutionError(
                "draw.io CLI did not produce the expected PDF artifact."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, target)
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
        command = [
            executable,
            "--export",
            source_name,
            "--format",
            "pdf",
            "--output",
            output_name,
        ]

        if options.get("crop", False):
            command.append("--crop")

        dpi = options.get("dpi")
        if dpi:
            command.extend(["--quality", str(dpi)])

        _run_cli(command, cwd=working_dir, description="draw.io CLI")
