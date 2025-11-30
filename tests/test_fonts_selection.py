from __future__ import annotations

from texsmith.fonts.selection import resolve_font_selection


def test_default_profile_resolution():
    selection = resolve_font_selection({})
    assert selection.profile == "default"
    assert selection.main == "Latin Modern Roman"
    assert selection.sans == "Latin Modern Sans"
    assert selection.mono == "FreeMono"


def test_named_profile_override():
    selection = resolve_font_selection({"fonts": "heros"})
    assert selection.profile == "heros"
    assert selection.sans == "TeX Gyre Heros"
    assert selection.small_caps is None


def test_font_overrides_merge():
    ctx = {
        "fonts": {
            "family": "sans",
            "overrides": {
                "mono": "JetBrains Mono",
                "math": "TeX Gyre Pagella Math",
            },
        },
    }
    selection = resolve_font_selection(ctx)
    assert selection.mono == "JetBrains Mono"
    assert selection.math == "TeX Gyre Pagella Math"


def test_family_dict_customisation():
    ctx = {
        "fonts": {
            "family": {
                "main": "EB Garamond",
                "sans": "Source Sans 3",
                "mono": "Fira Mono",
                "sc": "EB Garamond SC",
            }
        }
    }
    selection = resolve_font_selection(ctx)
    assert selection.main == "EB Garamond"
    assert selection.sans == "Source Sans 3"
    assert selection.mono == "Fira Mono"
    assert selection.small_caps == "EB Garamond SC"


def test_script_usage_produces_fallbacks():
    ctx: dict[str, object] = {}
    usage = [{"script_id": "arabic"}]
    selection = resolve_font_selection(ctx, script_usage=usage)
    assert "arabic" in selection.script_fallbacks
    assert selection.script_fallbacks["arabic"][0].startswith("Noto Sans")
