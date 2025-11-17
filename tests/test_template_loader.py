from pathlib import Path

import pytest

from texsmith.core.templates.runtime import load_template_runtime


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

    runtime = load_template_runtime("../../template/nature")
    assert runtime.instance.root.name == "nature"
