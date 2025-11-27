"""Bundled Tectonic acquisition and selection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import URLError
from urllib.request import urlopen
import zipfile

from rich.console import Console


TECTONIC_VERSION = "0.15.0"
_BASE_URL = (
    "https://github.com/tectonic-typesetting/tectonic/releases/download/"
    f"tectonic%40{TECTONIC_VERSION}/tectonic-{TECTONIC_VERSION}-"
)


class TectonicAcquisitionError(RuntimeError):
    """Raised when the bundled Tectonic binary cannot be prepared."""


@dataclass(slots=True)
class TectonicSelection:
    """Resolved Tectonic binary and its origin."""

    path: Path
    source: str  # "bundled" or "system"


def select_tectonic_binary(
    use_system: bool = False, *, console: Console | None = None
) -> TectonicSelection:
    """Return the Tectonic binary to invoke, downloading when needed."""
    if use_system:
        system_path = shutil.which("tectonic")
        if system_path is None:
            raise TectonicAcquisitionError(
                "Tectonic is not available on PATH (use --engine lualatex/xelatex "
                "or omit --system to download the bundled binary)."
            )
        return TectonicSelection(path=Path(system_path), source="system")

    bundled_path = _ensure_bundled_binary(console=console)
    return TectonicSelection(path=bundled_path, source="bundled")


def _ensure_bundled_binary(*, console: Console | None) -> Path:
    install_dir = Path.home() / ".texsmith" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)
    binary_name = "tectonic.exe" if _is_windows() else "tectonic"
    target = install_dir / binary_name

    if target.exists() and target.is_file():
        if _binary_matches_version(target):
            _log(console, f"Using bundled Tectonic at {target}")
            return target
        _log(console, f"Refreshing bundled Tectonic in {install_dir}")
        target.unlink(missing_ok=True)

    arch, archive_ext = _detect_architecture()
    url = f"{_BASE_URL}{arch}{archive_ext}"
    _log(console, f"Downloading Tectonic {TECTONIC_VERSION} for {arch}…")

    try:
        with tempfile.TemporaryDirectory(prefix="texsmith-tectonic-") as tmpdir:
            archive_path = Path(tmpdir) / f"tectonic{archive_ext}"
            _download_file(url, archive_path)
            extracted_root = Path(tmpdir) / "extracted"
            extracted_root.mkdir(parents=True, exist_ok=True)
            _extract_archive(archive_path, extracted_root)
            candidate = _find_binary(extracted_root, binary_name)
            _log(console, f"Installing bundled Tectonic into {install_dir}")
            shutil.move(str(candidate), target)
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except (OSError, URLError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise TectonicAcquisitionError(f"Unable to download bundled Tectonic: {exc}") from exc

    return target


def _download_file(url: str, destination: Path) -> None:
    with urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _extract_archive(archive_path: Path, destination: Path) -> None:
    suffixes = archive_path.suffixes
    if suffixes and suffixes[-1] == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(destination)
        return
    mode = "r:gz" if suffixes[-2:] == [".tar", ".gz"] or suffixes[-1:] == [".tgz"] else "r:*"
    with tarfile.open(archive_path, mode) as archive:
        archive.extractall(destination)


def _find_binary(root: Path, name: str) -> Path:
    for candidate in root.rglob(name):
        if candidate.is_file():
            return candidate
    raise TectonicAcquisitionError(f"Tectonic binary not found in archive contents for {root}")


def _binary_matches_version(binary: Path) -> bool:
    try:
        process = subprocess.run(
            [str(binary), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError:
        return False
    if process.returncode != 0:
        return False
    return TECTONIC_VERSION in (process.stdout or "") or TECTONIC_VERSION in (process.stderr or "")


def _detect_architecture() -> tuple[str, str]:
    """Return (triple, archive_ext) compatible with official Tectonic releases."""
    system = platform.system()
    machine = platform.machine().lower()

    is_musl = False
    if system == "Linux":
        try:
            output = subprocess.check_output(
                ["ldd", "--version"], stderr=subprocess.STDOUT, text=True
            )
            is_musl = "musl" in output.lower()
        except (OSError, subprocess.CalledProcessError):
            is_musl = False

    if system == "Darwin":
        ostype = "apple-darwin"
    elif system == "Windows":
        ostype = "pc-windows-gnu"
    elif system == "Linux":
        libc = "musl" if is_musl else "gnu"
        ostype = f"unknown-linux-{libc}"
    else:
        raise TectonicAcquisitionError(f"Unsupported platform: {system}")

    if machine in {"x86_64", "x86-64", "amd64", "x64"}:
        cputype = "x86_64"
    elif machine in {"i386", "i486", "i686", "i786", "x86"}:
        cputype = "i686"
    elif machine in {"aarch64", "arm64"}:
        cputype = "aarch64"
    elif machine in {"armv7l", "armv7"}:
        cputype = "armv7"
        if system == "Linux" and not is_musl:
            ostype = f"{ostype}eabihf"
    else:
        raise TectonicAcquisitionError(f"Unsupported CPU architecture: {machine}")

    ext = ".zip" if system == "Windows" else ".tar.gz"
    return f"{cputype}-{ostype}", ext


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _log(console: Console | None, message: str) -> None:
    if console is None:
        return
    console.log(f"[cyan]tectonic[/]: {message}")


__all__ = [
    "TECTONIC_VERSION",
    "TectonicAcquisitionError",
    "TectonicSelection",
    "select_tectonic_binary",
]
