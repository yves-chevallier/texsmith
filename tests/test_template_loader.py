import pathlib
from pathlib import Path

import pytest

from texsmith.core.templates.runtime import load_template_runtime


def _write_template(root: Path, name: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = "\n".join(
        [
            "[latex.template]",
            f'name = "{name}"',
            'version = "0.0.0"',
            'entrypoint = "template.tex"',
        ]
    )
    (root / "manifest.toml").write_text(manifest, encoding="utf-8")
    (root / "template.tex").write_text(r"\VAR{mainmatter}", encoding="utf-8")
    return root


def test_template_slug_resolves_from_nested_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    nested = Path("examples/diagrams")
    monkeypatch.chdir(nested)

    runtime = load_template_runtime("article")
    assert runtime.name == "article"


def test_template_slug_ignores_manifestless_directories(monkeypatch: pytest.MonkeyPatch) -> None:
    nested = Path("examples/letter")
    monkeypatch.chdir(nested)

    runtime = load_template_runtime("letter")
    assert runtime.instance.root != nested.resolve()
    assert runtime.name in {"letter", "formal-letter"}


def test_template_infers_templates_folder_when_path_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested = Path("examples/diagrams")
    monkeypatch.chdir(nested)

    runtime = load_template_runtime("../../src/texsmith/templates/letter")
    assert runtime.instance.root.name == "letter"


def test_builtin_precedence_over_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    local_root = _write_template(tmp_path / "article", "article")
    monkeypatch.chdir(tmp_path)

    runtime = load_template_runtime("article")
    assert runtime.instance is not None
    assert runtime.instance.root.resolve() != local_root.resolve()


def test_packaged_template_precedes_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    package_root = _write_template(site_dir / "texsmith_template_prio", "prio")
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(site_dir))

    local_root = _write_template(tmp_path / "prio", "prio")
    monkeypatch.chdir(tmp_path)

    runtime = load_template_runtime("prio")
    assert runtime.instance is not None
    assert runtime.instance.root.resolve() == package_root.resolve()
    assert runtime.instance.root.resolve() != local_root.resolve()


def test_home_template_used_when_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    template_root = _write_template(home_dir / ".texsmith" / "templates" / "homeonly", "homeonly")
    monkeypatch.setattr(pathlib.Path, "home", lambda: home_dir)
    monkeypatch.chdir(tmp_path)

    runtime = load_template_runtime("homeonly")
    assert runtime.instance is not None
    assert runtime.instance.root.resolve() == template_root.resolve()
