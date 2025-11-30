from __future__ import annotations

from pathlib import Path

from texsmith.fonts import emoji


def test_resolve_black_default(monkeypatch, tmp_path):
    monkeypatch.setattr(
        emoji,
        "_materialize_family",
        lambda family, fonts_dir, emitter=None: tmp_path / "OpenMoji.ttf",
    )
    payload = emoji.resolve_emoji_preferences({}, engine="tectonic", fonts_dir=tmp_path)
    assert payload.mode == "black"
    assert payload.font_family == "OpenMoji Black"
    assert payload.font_path == tmp_path / "OpenMoji.ttf"
    assert not payload.color_enabled


def test_color_only_lualatex(monkeypatch, tmp_path):
    monkeypatch.setattr(
        emoji,
        "_materialize_family",
        lambda family, fonts_dir, emitter=None: tmp_path / "NotoColorEmoji.ttf",
    )
    ctx = {"emoji": "color"}
    payload = emoji.resolve_emoji_preferences(ctx, engine="lualatex", fonts_dir=tmp_path)
    assert payload.mode == "color"
    assert payload.color_enabled
    assert payload.font_family == "Noto Color Emoji"


def test_color_downgrades_when_engine_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        emoji,
        "_materialize_family",
        lambda family, fonts_dir, emitter=None: tmp_path / "OpenMoji.ttf",
    )
    payload = emoji.resolve_emoji_preferences({"emoji": "color"}, engine="xelatex", fonts_dir=tmp_path)
    assert payload.mode == "black"
    assert "Color emoji unsupported" in payload.warnings[0]


def test_artifact_mode_has_no_font(tmp_path):
    payload = emoji.resolve_emoji_preferences({"emoji": "artifact"}, engine="lualatex", fonts_dir=tmp_path)
    assert payload.mode == "artifact"
    assert payload.font_family is None
    assert payload.font_path is None
