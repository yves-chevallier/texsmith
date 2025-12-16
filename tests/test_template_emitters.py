from __future__ import annotations

from pathlib import Path

from texsmith.core.templates.base import WrappableTemplate


def _make_template(tmp_path: Path) -> WrappableTemplate:
    manifest = tmp_path / "manifest.toml"
    (tmp_path / "main.tex").write_text("content", encoding="utf-8")
    manifest.write_text(
        """
[latex.template]
name = "demo"
version = "0.0.0"
entrypoint = "main.tex"

[latex.template.emit]
foo = "bar"
        """,
        encoding="utf-8",
    )
    return WrappableTemplate(tmp_path)


def test_template_emitters_seed_context(tmp_path: Path) -> None:
    template = _make_template(tmp_path)

    context = template.prepare_context("body")

    assert context["foo"] == "bar"


def test_template_emitters_do_not_override_overrides(tmp_path: Path) -> None:
    template = _make_template(tmp_path)

    overrides = {"foo": "override"}
    context = template.prepare_context("body", overrides=overrides)

    assert context["foo"] == "override"
