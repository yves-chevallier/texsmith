from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types


if "bs4" not in sys.modules:
    bs4_stub = types.ModuleType("bs4")

    class _FeatureNotFoundError(Exception):
        """Lightweight stand-in used during tests without BeautifulSoup."""

        pass

    bs4_stub.BeautifulSoup = object
    bs4_stub.FeatureNotFound = _FeatureNotFoundError
    sys.modules["bs4"] = bs4_stub

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for entry in (PROJECT_ROOT, SRC_ROOT):
    str_entry = str(entry)
    if str_entry not in sys.path:
        sys.path.insert(0, str_entry)

if "texsmith" not in sys.modules:
    texsmith_stub = types.ModuleType("texsmith")
    texsmith_stub.__path__ = [str((SRC_ROOT / "texsmith").resolve())]
    sys.modules["texsmith"] = texsmith_stub

Template = importlib.import_module("templates.article").Template
TemplateManifest = importlib.import_module("texsmith.core.templates.manifest").TemplateManifest


def test_attribute_resolver_merges_press_metadata() -> None:
    manifest = TemplateManifest.load(Path("templates/article/template/manifest.toml"))
    info = manifest.latex.template

    overrides = {
        "press": {
            "title": "Hello & World",
            "subtitle": "Insights",
            "authors": [
                {"name": "Ada Lovelace", "affiliation": "Analytical Engine"},
                "Grace Hopper",
            ],
            "paper": "letter",
            "orientation": "landscape",
            "language": "fr",
        }
    }

    resolved = info.resolve_attributes(overrides)

    assert resolved["title"] == "Hello \\& World"
    assert resolved["paper"] == "letterpaper"
    assert resolved["orientation"] == "landscape"
    assert resolved["language"] == "french"
    assert isinstance(resolved["authors"], list)
    assert resolved["authors"][0]["name"] == "Ada Lovelace"


def test_article_template_applies_computed_options() -> None:
    template = Template()
    overrides = {
        "press": {
            "title": "Sample & Title",
            "authors": [
                {"name": "Ada Lovelace", "affiliation": "Analytical Engine"},
                "Grace Hopper",
            ],
            "paper": "letter",
            "orientation": "landscape",
            "language": "fr",
        }
    }

    context = template.prepare_context("Body", overrides=overrides)

    assert context["title"] == "Sample \\& Title"
    assert context["language"] == "french"
    assert context["documentclass_options"] == "[letterpaper,landscape]"
    assert "letterpaper" in context["geometry_options"]
    assert "landscape" in context["geometry_options"]
    assert "\\thanks{" in context["author"]
    assert "press" not in context
