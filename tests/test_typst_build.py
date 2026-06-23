"""Tests for Typst PDF compilation path selection.

``compile_typst`` must prefer the embedded ``typst`` Python package, fall back
to the system binary, and degrade gracefully (no exception, actionable message)
when neither is available. Selection is verified with monkeypatching so the
tests run regardless of what is installed on the machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.writers.typst import build


def test_typst_available_reflects_either_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build, "_package_available", lambda: False)
    monkeypatch.setattr(build, "_binary_path", lambda: None)
    assert build.typst_available() is False

    monkeypatch.setattr(build, "_package_available", lambda: True)
    assert build.typst_available() is True

    monkeypatch.setattr(build, "_package_available", lambda: False)
    monkeypatch.setattr(build, "_binary_path", lambda: "/usr/bin/typst")
    assert build.typst_available() is True


def test_prefers_package_over_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(build, "_package_available", lambda: True)
    monkeypatch.setattr(build, "_binary_path", lambda: "/usr/bin/typst")

    def fake_package(source: Path, pdf: Path) -> build.TypstBuildResult:
        calls.append("package")
        return build.TypstBuildResult(ok=True, pdf_path=pdf, message="pkg")

    def fake_binary(binary: str, source: Path, pdf: Path) -> build.TypstBuildResult:
        calls.append("binary")
        return build.TypstBuildResult(ok=True, pdf_path=pdf, message="bin")

    monkeypatch.setattr(build, "_compile_with_package", fake_package)
    monkeypatch.setattr(build, "_compile_with_binary", fake_binary)

    result = build.compile_typst(tmp_path / "doc.typ")

    assert calls == ["package"]
    assert result.ok is True
    assert result.pdf_path == tmp_path / "doc.pdf"


def test_falls_back_to_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(build, "_package_available", lambda: False)
    monkeypatch.setattr(build, "_binary_path", lambda: "/usr/bin/typst")

    def fake_binary(binary: str, source: Path, pdf: Path) -> build.TypstBuildResult:
        calls.append(binary)
        return build.TypstBuildResult(ok=True, pdf_path=pdf, message="bin")

    monkeypatch.setattr(build, "_compile_with_binary", fake_binary)

    result = build.compile_typst(tmp_path / "doc.typ", output=tmp_path / "out.pdf")

    assert calls == ["/usr/bin/typst"]
    assert result.ok is True
    assert result.pdf_path == tmp_path / "out.pdf"


def test_no_compiler_is_graceful(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(build, "_package_available", lambda: False)
    monkeypatch.setattr(build, "_binary_path", lambda: None)

    result = build.compile_typst(tmp_path / "doc.typ")

    assert result.ok is False
    assert result.pdf_path is None
    assert "texsmith[typst]" in result.message


@pytest.mark.skipif(not build._package_available(), reason="typst package not installed")
def test_package_compiles_real_pdf(tmp_path: Path) -> None:
    source = tmp_path / "doc.typ"
    source.write_text("= Hi\nThis is a test.\n", encoding="utf-8")

    result = build._compile_with_package(source, tmp_path / "doc.pdf")

    assert result.ok is True
    assert result.pdf_path is not None
    assert result.pdf_path.read_bytes().startswith(b"%PDF")
