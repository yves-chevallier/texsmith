from __future__ import annotations

from pathlib import Path

from texsmith.core.user_dir import user_dir_context
from texsmith.fonts.cache import FontCache


def test_user_dir_respects_environment(monkeypatch, tmp_path: Path) -> None:
    env_home = tmp_path / "home-root"
    env_cache = tmp_path / "cache-root"
    monkeypatch.setenv("TEXSMITH_HOME", str(env_home))
    monkeypatch.setenv("TEXSMITH_CACHE_DIR", str(env_cache))

    with user_dir_context():
        cache = FontCache()
        assert cache.ensure() == env_home / "fonts"


def test_cache_root_defaults_under_custom_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TEXSMITH_CACHE_DIR", raising=False)
    custom_root = tmp_path / "custom-home"
    with user_dir_context(root=custom_root) as user_dir:
        assert user_dir.cache_root == custom_root / "cache"


def test_clear_cache_removes_namespaces(tmp_path: Path) -> None:
    with user_dir_context(root=tmp_path / "home", cache_root=tmp_path / "cache") as user_dir:
        fonts_dir = user_dir.data_dir("fonts")
        (fonts_dir / "stub.txt").write_text("ok", encoding="utf-8")

        snippets_dir = user_dir.cache_dir("snippets")
        (snippets_dir / "entry").write_text("ok", encoding="utf-8")

        removed = user_dir.clear_cache(["fonts", "snippets"])

        assert set(removed) == {fonts_dir, snippets_dir}
        assert not fonts_dir.exists()
        assert not snippets_dir.exists()
        assert user_dir.root.exists()
        assert user_dir.cache_root.exists()
