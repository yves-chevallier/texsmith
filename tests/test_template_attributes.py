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
    bs4_stub.NavigableString = str
    bs4_stub.Tag = object
    sys.modules["bs4"] = bs4_stub
    bs4_element_stub = types.ModuleType("bs4.element")
    bs4_element_stub.NavigableString = str
    bs4_element_stub.Tag = object
    bs4_element_stub.PageElement = object
    sys.modules["bs4.element"] = bs4_element_stub
    bs4_stub.element = bs4_element_stub

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

article_module = importlib.import_module("texsmith.templates.article")
ArticleTemplate = article_module.Template
book_module = importlib.import_module("texsmith.templates.book")
BookTemplate = book_module.Template
letter_module = importlib.import_module("texsmith.templates.letter")
LetterTemplate = letter_module.Template
TemplateManifest = importlib.import_module("texsmith.core.templates.manifest").TemplateManifest
from texsmith.core.fragments import inject_fragment_attributes  # noqa: E402


ARTICLE_ROOT = Path(article_module.__file__).resolve().parent
from texsmith.fragments.geometry.paper import inject_geometry_context  # noqa: E402
from texsmith.ui.cli.commands.render import _parse_template_attributes  # type: ignore  # noqa: E402


def test_attribute_resolver_merges_press_metadata() -> None:
    manifest = TemplateManifest.load(ARTICLE_ROOT / "template" / "manifest.toml")
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
    assert resolved["language"] == "french"
    assert "paper" not in resolved
    assert "orientation" not in resolved
    assert isinstance(resolved["authors"], list)
    assert resolved["authors"][0]["name"] == "Ada Lovelace"


def test_article_template_applies_computed_options() -> None:
    template = ArticleTemplate()
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
    inject_geometry_context(context, overrides)

    assert context["title"] == "Sample \\& Title"
    assert context["language"] == "french"
    assert context["documentclass_options"] == "[letterpaper,landscape,twoside]"
    assert "letterpaper" in context["geometry_options"]
    assert "landscape" in context["geometry_options"]
    assert "\\thanks{" in context["author"]
    assert "press" not in context


def test_article_template_supports_columns_option() -> None:
    template = ArticleTemplate()
    overrides = {
        "press": {
            "columns": 2,
            "paper": "letter",
            "orientation": "landscape",
        }
    }

    context = template.prepare_context("Body", overrides=overrides)
    inject_geometry_context(context, overrides)

    rendered = template.wrap_document("Body", overrides=overrides, context=context)

    assert "\\documentclass[letterpaper,landscape,twoside,twocolumn]{article}" in rendered


def test_article_template_accepts_preamble_override() -> None:
    template = ArticleTemplate()
    overrides = {"press": {"override": {"preamble": "\\usepackage{xcolor}"}}}

    context = template.prepare_context("", overrides=overrides)
    inject_geometry_context(context, overrides)

    assert "preamble" not in context


def test_article_template_geometry_overrides() -> None:
    template = ArticleTemplate()
    overrides = {"press": {"geometry": {"paperheight": "4cm", "showframe": True}}}

    context = template.prepare_context("", overrides=overrides)
    inject_geometry_context(context, overrides)

    assert "paperheight=40mm" in context["geometry_options"]
    assert "showframe" in context["geometry_options"]
    assert context["geometry_extra_options"] == "paperheight=40mm,showframe"


def test_article_template_normalises_callout_style() -> None:
    template = ArticleTemplate()
    overrides = {"press": {"callout_style": "CLASSIC"}}

    context = template.prepare_context("Body", overrides=overrides)
    inject_fragment_attributes(template.info.fragments or [], context=context, overrides=overrides)

    assert context["callout_style"] == "classic"


def test_letter_template_prefers_direct_format_override() -> None:
    template = LetterTemplate()
    overrides = {
        "press": {"format": "nf"},
        "format": "sn",
        "from_name": "Ada Lovelace",
        "to_name": "Charles Babbage",
    }

    context = template.prepare_context("Body", overrides=overrides)

    assert context["letter_standard"] == "sn-left"
    assert context["letter_standard_option"] == "SNleft"


def test_book_template_supports_columns_option() -> None:
    template = BookTemplate()
    overrides = {"press": {"columns": 2}}

    context = template.prepare_context("Body", overrides=overrides)
    inject_geometry_context(context, overrides)

    rendered = template.wrap_document("Body", overrides=overrides, context=context)

    assert "\\documentclass[twoside]{memoir}" in rendered
    assert "twocolumn" not in rendered


def test_parse_template_attributes_supports_nested_keys() -> None:
    result = _parse_template_attributes(
        ["margin=wide", "geometry.paperheight=4cm", "geometry.showframe=true"]
    )

    assert result["margin"] == "wide"
    assert isinstance(result["geometry"], dict)
    assert result["geometry"]["paperheight"] == "4cm"
    assert result["geometry"]["showframe"] is True
