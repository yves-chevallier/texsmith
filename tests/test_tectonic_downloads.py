"""Download helpers for bundled LaTeX tools."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import zipfile

from texsmith.adapters.latex import tectonic


def _build_fake_zip(target: Path, *, binary_name: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    binary_path = target.parent / "payload" / binary_name
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_text("#!/bin/sh\necho dummy\n", encoding="utf-8")
    with zipfile.ZipFile(target, "w") as archive:
        archive.write(binary_path, arcname=str(Path("bin") / binary_name))
    return target


def _stub_install_dir(monkeypatch, tmp_path: Path) -> Path:
    install_dir = tmp_path / "install"
    install_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tectonic, "_install_dir", lambda: install_dir)
    return install_dir


def test_select_biber_binary_downloads_and_extracts(monkeypatch, tmp_path: Path) -> None:
    install_dir = _stub_install_dir(monkeypatch, tmp_path)
    binary_name = "biber.exe" if sys.platform.startswith("win") else "biber"
    archive_path = _build_fake_zip(tmp_path / "biber.zip", binary_name=binary_name)

    monkeypatch.setattr(tectonic, "_detect_biber_archive", lambda: ("dummy-url", ".zip"))
    monkeypatch.setattr(
        tectonic, "_download_file", lambda _url, destination: shutil.copy(archive_path, destination)
    )

    path = tectonic.select_biber_binary(console=None)

    assert path == install_dir / binary_name
    assert path.exists()
    assert os.access(path, os.X_OK)


def test_select_makeglossaries_downloads_and_extracts(monkeypatch, tmp_path: Path) -> None:
    install_dir = _stub_install_dir(monkeypatch, tmp_path)
    archive_path = _build_fake_zip(tmp_path / "makeglossaries.zip", binary_name="makeglossaries")

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        tectonic, "_download_file", lambda _url, destination: shutil.copy(archive_path, destination)
    )

    path = tectonic.select_makeglossaries(console=None).path

    assert path == install_dir / "makeglossaries"
    assert path.exists()
    assert os.access(path, os.X_OK)
