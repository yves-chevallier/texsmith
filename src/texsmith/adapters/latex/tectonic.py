"""Bundled Tectonic (and helper) acquisition and selection helpers."""

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

from texsmith.core.user_dir import get_user_dir


TECTONIC_VERSION = "0.15.0"
BIBER_VERSION = "2.17"
MAKEGLOSSARIES_URL = "https://mirrors.ctan.org/macros/latex/contrib/glossaries.zip"
_BASE_URL = (
    "https://github.com/tectonic-typesetting/tectonic/releases/download/"
    f"tectonic%40{TECTONIC_VERSION}/tectonic-{TECTONIC_VERSION}-"
)
_BIBER_BASE_URL = (
    "https://sourceforge.net/projects/biblatex-biber/files/biblatex-biber/"
    f"{BIBER_VERSION}/binaries/"
)


class BundledToolError(RuntimeError):
    """Raised when a bundled tool cannot be prepared."""


class TectonicAcquisitionError(BundledToolError):
    """Raised when the bundled Tectonic binary cannot be prepared."""


class BiberAcquisitionError(BundledToolError):
    """Raised when the bundled Biber binary cannot be prepared."""


class MakeglossariesAcquisitionError(BundledToolError):
    """Raised when the makeglossaries helper cannot be prepared."""


@dataclass(slots=True)
class TectonicSelection:
    """Resolved Tectonic binary and its origin."""

    path: Path
    source: str  # "bundled" or "system"


@dataclass(slots=True)
class HelperSelection:
    """Resolved auxiliary tool selection (system or bundled)."""

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
    install_dir = _install_dir()
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
            install_dir.mkdir(parents=True, exist_ok=True)
            source_dir = candidate.parent
            if _is_windows():
                # Windows builds ship DLL sidecars; copy them alongside the binary.
                for item in source_dir.iterdir():
                    destination = install_dir / item.name
                    if destination.exists():
                        if destination.is_dir():
                            shutil.rmtree(destination)
                        else:
                            destination.unlink()
                    if item.is_dir():
                        shutil.copytree(item, destination)
                    else:
                        shutil.copy2(item, destination)
                target = install_dir / binary_name
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            else:
                shutil.move(str(candidate), target)
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except (OSError, URLError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise TectonicAcquisitionError(f"Unable to download bundled Tectonic: {exc}") from exc

    return target


def select_biber_binary(*, console: Console | None = None) -> Path:
    """Return the bundled Biber binary, downloading when needed."""
    install_dir = _install_dir()
    binary_name = "biber.exe" if _is_windows() else "biber"
    target = install_dir / binary_name

    if target.exists() and target.is_file():
        if _binary_matches_version(target, expected=BIBER_VERSION):
            _log(console, f"Using bundled Biber at {target}", tool="biber")
            return target
        _log(console, f"Refreshing bundled Biber in {install_dir}", tool="biber")
        target.unlink(missing_ok=True)

    archive_url, archive_ext = _detect_biber_archive()
    _log(console, f"Downloading Biber {BIBER_VERSION} ({archive_url})…", tool="biber")

    try:
        with tempfile.TemporaryDirectory(prefix="texsmith-biber-") as tmpdir:
            archive_path = Path(tmpdir) / f"biber{archive_ext}"
            _download_file(archive_url, archive_path)
            extracted_root = Path(tmpdir) / "extracted"
            extracted_root.mkdir(parents=True, exist_ok=True)
            _extract_archive(archive_path, extracted_root)
            candidate = _find_binary(extracted_root, binary_name, error_cls=BiberAcquisitionError)
            _log(console, f"Installing bundled Biber into {install_dir}", tool="biber")
            shutil.move(str(candidate), target)
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except (OSError, URLError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise BiberAcquisitionError(f"Unable to download bundled Biber: {exc}") from exc

    return target


def select_makeglossaries(*, console: Console | None = None) -> HelperSelection:
    """Return a makeglossaries command, downloading the Perl helper if absent."""
    existing = shutil.which("makeglossaries")
    if existing:
        return HelperSelection(path=Path(existing), source="system")
    bundled = _ensure_makeglossaries(console=console)
    return HelperSelection(path=bundled, source="bundled")


def _ensure_makeglossaries(*, console: Console | None) -> Path:
    install_dir = _install_dir()
    target = install_dir / "makeglossaries"

    if target.exists() and target.is_file():
        _log(console, f"Using bundled makeglossaries at {target}", tool="makeglossaries")
        return target

    _log(console, f"Downloading makeglossaries helper into {install_dir}", tool="makeglossaries")

    try:
        with tempfile.TemporaryDirectory(prefix="texsmith-makeglossaries-") as tmpdir:
            archive_path = Path(tmpdir) / "glossaries.zip"
            _download_file(MAKEGLOSSARIES_URL, archive_path)
            extracted_root = Path(tmpdir) / "extracted"
            extracted_root.mkdir(parents=True, exist_ok=True)
            _extract_archive(archive_path, extracted_root)
            candidate = _find_binary(
                extracted_root, "makeglossaries", error_cls=MakeglossariesAcquisitionError
            )
            shutil.move(str(candidate), target)
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except (OSError, URLError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise MakeglossariesAcquisitionError(
            f"Unable to download makeglossaries helper: {exc}"
        ) from exc

    return target


def _install_dir() -> Path:
    return get_user_dir().data_dir("bin")


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
        try:
            archive.extractall(destination, filter="data")
        except TypeError:  # Python < 3.12 compatibility (no filter kw)
            archive.extractall(destination)


def _find_binary(
    root: Path, name: str, *, error_cls: type[BundledToolError] = TectonicAcquisitionError
) -> Path:
    for candidate in root.rglob(name):
        if candidate.is_file():
            return candidate
    raise error_cls(f"{name} binary not found in archive contents for {root}")


def _binary_matches_version(binary: Path, *, expected: str = TECTONIC_VERSION) -> bool:
    return _probe_version(binary, expected=expected)


def _probe_version(binary: Path, *, expected: str) -> bool:
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
    output = (process.stdout or "") + (process.stderr or "")
    return expected in output


def _detect_architecture() -> tuple[str, str]:
    """Return (triple, archive_ext) compatible with official Tectonic releases."""
    system, machine, is_musl = _platform_details()

    if system == "Darwin":
        ostype = "apple-darwin"
    elif system == "Windows":
        ostype = "pc-windows-msvc"
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


def _detect_biber_archive() -> tuple[str, str]:
    """Return (url, archive_ext) for the appropriate Biber release."""
    system, machine, is_musl = _platform_details()

    if system == "Linux":
        platform_dir = "Linux-musl" if is_musl else "Linux"
        libc_suffix = "-musl" if is_musl else ""
        if machine in {"x86_64", "x86-64", "amd64", "x64"}:
            filename = f"biber-linux_x86_64{libc_suffix}.tar.gz"
        elif machine in {"aarch64", "arm64"}:
            filename = f"biber-linux_aarch64{libc_suffix}.tar.gz"
        elif machine in {"i386", "i486", "i686", "i786", "x86"}:
            filename = f"biber-linux_i386{libc_suffix}.tar.gz"
        else:
            raise BiberAcquisitionError(f"Unsupported CPU architecture for Biber: {machine}")
        return f"{_BIBER_BASE_URL}{platform_dir}/{filename}", ".tar.gz"

    if system == "Darwin":
        if machine in {"aarch64", "arm64"}:
            filename = "biber-darwin_arm64.tar.gz"
        elif machine in {"x86_64", "x86-64", "amd64", "x64"}:
            filename = "biber-darwin_x86_64.tar.gz"
        else:
            raise BiberAcquisitionError(f"Unsupported CPU architecture for Biber: {machine}")
        return f"{_BIBER_BASE_URL}Darwin/{filename}", ".tar.gz"

    if system == "Windows":
        filename = (
            "biber-MSWIN64.zip" if machine in {"x86_64", "amd64", "x64"} else "biber-MSWIN32.zip"
        )
        return f"{_BIBER_BASE_URL}Windows/{filename}", ".zip"

    raise BiberAcquisitionError(f"Unsupported platform for bundled Biber: {system}")


def _platform_details() -> tuple[str, str, bool]:
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

    return system, machine, is_musl


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _log(console: Console | None, message: str, *, tool: str = "tectonic") -> None:
    if console is None:
        return
    console.log(f"[cyan]{tool}[/]: {message}")


__all__ = [
    "BIBER_VERSION",
    "TECTONIC_VERSION",
    "BiberAcquisitionError",
    "BundledToolError",
    "HelperSelection",
    "MakeglossariesAcquisitionError",
    "TectonicAcquisitionError",
    "TectonicSelection",
    "select_biber_binary",
    "select_makeglossaries",
    "select_tectonic_binary",
]
