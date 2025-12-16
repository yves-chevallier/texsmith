from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace

from texsmith import latex_text, mermaid, missing_footnotes, multi_citations, rawlatex
from texsmith.core.fragments import inject_fragment_attributes
from texsmith.templates import snippet as snippet_template
from texsmith.ui.cli.commands import templates


class DummyTemplateInfo:
    def __init__(self, root: Path) -> None:
        self.name = "dummy"
        self.version = "0.1.0"
        self.entrypoint = "template.tex"
        self.engine = "lualatex"
        self.shell_escape = False
        self.texlive_year = 2023
        self.tlmgr_packages: list[str] = []
        self.override: list[str] = []
        self.attributes: dict[str, object] = {}
        self._root = root

    class _Slot:
        def __init__(self) -> None:
            self.base_level = 1
            self.depth = "section"
            self.offset = 0
            self.strip_heading = False

        def resolve_level(self, base: int) -> int:
            return base + (self.base_level or 0) + self.offset

    def resolve_slots(self) -> tuple[dict[str, object], str]:
        slot = self._Slot()
        slot.default = True  # type: ignore[attr-defined]
        return ({"mainmatter": slot}, "mainmatter")


class DummyTemplate:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.info = DummyTemplateInfo(root)

    def iter_assets(self):
        return []


def _stub_entry_points():
    class _EmptyEntries:
        def select(self, **_kwargs):
            return []

    return _EmptyEntries()


def test_template_listing_plain(monkeypatch, capsys, tmp_path):
    dummy_root = tmp_path / "dummy"
    dummy_root.mkdir()
    (dummy_root / "manifest.toml").write_text("", encoding="utf-8")

    monkeypatch.setattr(templates, "iter_builtin_templates", lambda: ["dummy"])
    monkeypatch.setattr(templates, "_discover_local_templates", lambda: [dummy_root])
    monkeypatch.setattr(templates, "load_template", lambda _name: DummyTemplate(dummy_root))
    monkeypatch.setattr(templates.metadata, "entry_points", _stub_entry_points)

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # type: ignore[override]
        if name.startswith("rich"):
            raise ImportError("force plain")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    templates.list_templates()
    captured = capsys.readouterr()
    assert "dummy" in captured.out


def test_show_template_info_fallback(monkeypatch, capsys, tmp_path):
    dummy_root = tmp_path / "dummy2"
    dummy_root.mkdir()
    (dummy_root / "manifest.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(templates, "load_template", lambda _ident: DummyTemplate(dummy_root))

    class _State:
        def __init__(self) -> None:
            self.console = SimpleNamespace(print=lambda *_, **__: None)

    monkeypatch.setattr(templates, "get_cli_state", lambda: _State())
    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # type: ignore[override]
        if name.startswith("rich"):
            raise ImportError("force plain")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    templates.show_template_info("dummy2")
    captured = capsys.readouterr()
    assert "Template: dummy2" in captured.out
    assert "tlmgr packages" in captured.out


def test_format_list_and_discovery(tmp_path):
    assert templates._format_list(["a", "b"]) == "a, b"
    assert templates._format_list([]) == "-"

    candidate = tmp_path / "tpl"
    candidate.mkdir()
    (candidate / "manifest.toml").write_text("", encoding="utf-8")
    assert templates._looks_like_template_root(candidate) is True


def test_snippet_template_normalises() -> None:
    tmpl = snippet_template.Template()
    overrides = {"callout_style": "minimal", "emoji": "symbola"}
    context = tmpl.prepare_context("body", overrides=overrides)
    inject_fragment_attributes(tmpl.info.fragments or [], context=context, overrides=overrides)
    assert context["callout_style"] == "minimal"
    assert context["emoji"] == "symbola"
    assert context["width"]


def test_extension_factories() -> None:
    assert rawlatex.makeExtension().__class__.__name__.endswith("Extension")
    assert latex_text.makeExtension().__class__.__name__.endswith("Extension")
    assert multi_citations.makeExtension().__class__.__name__.endswith("Extension")
    assert mermaid.makeExtension().__class__.__name__.endswith("Extension")
    ext = missing_footnotes.makeExtension()
    assert hasattr(ext, "extendMarkdown")
