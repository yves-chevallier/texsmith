from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.core.templates.manifest import TemplateError
from texsmith.fragments.bibliography import fragment as bibliography_fragment
from texsmith.fragments.callouts import fragment as callouts_fragment
from texsmith.fragments.code import fragment as code_fragment
from texsmith.fragments.fonts import fragment as fonts_fragment
from texsmith.fragments.geometry import fragment as geometry_fragment
from texsmith.fragments.glossary import fragment as glossary_fragment
from texsmith.fragments.index import fragment as index_fragment
from texsmith.fragments.typesetting import fragment as typesetting_fragment


def test_typesetting_fragment_defaults() -> None:
    context: dict[str, object] = {}

    config = typesetting_fragment.build_config(context)
    assert config.enabled() is False

    typesetting_fragment.inject(config, context)

    assert context["ts_typesetting_enabled"] is False
    assert context["ts_typesetting_indent_mode"] is None
    assert context["ts_typesetting_parskip"] is None
    assert context["ts_typesetting_leading_mode"] is None
    assert context["ts_typesetting_leading_value"] is None
    assert context["ts_typesetting_enable_lineno"] is False
    assert typesetting_fragment.should_render(config) is False


def test_typesetting_fragment_with_values() -> None:
    context: dict[str, object] = {
        "typesetting_paragraph": {"indent": True, "spacing": "1cm"},
        "typesetting_leading": "double",
        "typesetting_lineno": True,
    }

    config = typesetting_fragment.build_config(context)
    assert config.enabled() is True

    typesetting_fragment.inject(config, context)

    assert context["ts_typesetting_enabled"] is True
    assert context["ts_typesetting_indent_mode"] == "always"
    assert context["ts_typesetting_parskip"] == "1cm"
    assert context["ts_typesetting_leading_mode"] == "double"
    assert context["ts_typesetting_leading_value"] is None
    assert context["ts_typesetting_enable_lineno"] is True
    assert typesetting_fragment.should_render(config) is True


def test_code_fragment_detects_usage() -> None:
    context: dict[str, object] = {
        "code": {"engine": "minted", "style": "bw"},
        "mainmatter": "Some text \\begin{code}inline\\end{code}",
    }

    config = code_fragment.build_config(context)
    assert config.uses_code is True

    code_fragment.inject(config, context)

    assert context["ts_code_enabled"] is True
    assert context["ts_code_options"]["engine"] == "minted"
    assert code_fragment.should_render(config) is True


def test_callouts_fragment_renders_only_when_present() -> None:
    context_empty: dict[str, object] = {}
    config_empty = callouts_fragment.build_config(context_empty)
    assert callouts_fragment.should_render(config_empty) is False

    context_used: dict[str, object] = {
        "callout_style": "minimal",
        "mainmatter": "\\begin{callout}{Note}Content\\end{callout}",
    }
    config_used = callouts_fragment.build_config(context_used)
    callouts_fragment.inject(config_used, context_used)

    assert context_used["ts_callouts_style"] == "minimal"
    assert callouts_fragment.should_render(config_used) is True


def test_bibliography_fragment_flag() -> None:
    ctx_empty: dict[str, object] = {}
    cfg_empty = bibliography_fragment.build_config(ctx_empty)
    assert bibliography_fragment.should_render(cfg_empty) is False

    ctx_cited: dict[str, object] = {"citations": ["ref1"]}
    cfg_cited = bibliography_fragment.build_config(ctx_cited)
    bibliography_fragment.inject(cfg_cited, ctx_cited)
    assert ctx_cited["ts_bibliography_enabled"] is True
    assert bibliography_fragment.should_render(cfg_cited) is True


def test_glossary_fragment_flag() -> None:
    ctx_none: dict[str, object] = {}
    cfg_none = glossary_fragment.build_config(ctx_none)
    assert glossary_fragment.should_render(cfg_none) is False

    ctx_glossary: dict[str, object] = {"glossary": [{"term": "foo", "definition": "bar"}]}
    cfg_glossary = glossary_fragment.build_config(ctx_glossary)
    glossary_fragment.inject(cfg_glossary, ctx_glossary)
    assert ctx_glossary["ts_glossary_enabled"] is True
    assert glossary_fragment.should_render(cfg_glossary) is True

    ctx_acronyms: dict[str, object] = {"acronyms": [{"term": "AI", "definition": "artificial"}]}
    cfg_acronyms = glossary_fragment.build_config(ctx_acronyms)
    assert glossary_fragment.should_render(cfg_acronyms) is True


def test_index_fragment_flag() -> None:
    ctx_default: dict[str, object] = {}
    cfg_default = index_fragment.build_config(ctx_default)
    assert index_fragment.should_render(cfg_default) is False

    ctx_terms: dict[str, object] = {"index_terms": ["foo", "bar"]}
    cfg_terms = index_fragment.build_config(ctx_terms)
    index_fragment.inject(cfg_terms, ctx_terms)
    assert ctx_terms["ts_index_enabled"] is True
    assert index_fragment.should_render(cfg_terms) is True

    ctx_flag: dict[str, object] = {"has_index": True}
    cfg_flag = index_fragment.build_config(ctx_flag)
    assert index_fragment.should_render(cfg_flag) is True


def test_fonts_fragment_defaults(tmp_path: Path) -> None:
    ctx: dict[str, object] = {"output_dir": str(tmp_path)}
    cfg = fonts_fragment.build_config(ctx)
    fonts_fragment.inject(cfg, ctx)

    assert ctx["fonts_family"] == "lm"
    assert ctx["fonts"]["family"] == "lm"
    assert fonts_fragment.should_render(cfg) is True


@pytest.mark.filterwarnings("ignore:Unknown font family")
def test_fonts_fragment_falls_back_to_lm(tmp_path: Path) -> None:
    ctx: dict[str, object] = {"fonts_family": "unknown", "output_dir": str(tmp_path)}
    cfg = fonts_fragment.build_config(ctx)
    fonts_fragment.inject(cfg, ctx)

    assert ctx["fonts_family"] == "lm"
    assert ctx["fonts"]["family"] == "lm"


def test_geometry_fragment_injects_defaults() -> None:
    ctx: dict[str, object] = {}
    ctx.update(geometry_fragment.context_defaults)
    cfg = geometry_fragment.build_config(ctx)
    geometry_fragment.inject(cfg, ctx)

    # Defaults include A4 paper and geometry options injected
    assert ctx["paper"]["format"] == "a4"
    assert "a4paper" in ctx["geometry_options"]


def test_geometry_fragment_invalid_margin_raises() -> None:
    ctx: dict[str, object] = {"paper": {"format": "a4", "margin": "10qq"}}
    cfg = geometry_fragment.build_config(ctx)
    with pytest.raises(TemplateError):
        geometry_fragment.inject(cfg, ctx)


def test_typesetting_invalid_indent_raises() -> None:
    ctx: dict[str, object] = {"typesetting_paragraph": {"indent": "maybe"}}
    with pytest.raises(TemplateError):
        typesetting_fragment.build_config(ctx)


def test_typesetting_invalid_leading_raises() -> None:
    ctx: dict[str, object] = {"typesetting_leading": 0}
    with pytest.raises(TemplateError):
        typesetting_fragment.build_config(ctx)
