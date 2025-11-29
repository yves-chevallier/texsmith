import os
from pathlib import Path

import pytest

from texsmith.adapters.latex import engines as engine


def test_build_tex_env_prefers_bundled_biber(tmp_path: Path) -> None:
    extra_bin = tmp_path / "bin"
    biber_path = extra_bin / "biber"
    env = engine.build_tex_env(
        tmp_path,
        isolate_cache=True,
        extra_path=extra_bin,
        biber_path=biber_path,
    )

    assert env["PATH"].split(os.pathsep)[0] == str(extra_bin)
    assert env["BIBER"] == str(biber_path)


def test_missing_dependencies_allows_available_biber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    choice = engine.EngineChoice(backend="tectonic", latexmk_engine=None)
    features = engine.EngineFeatures(
        requires_shell_escape=False,
        bibliography=True,
        has_index=False,
        has_glossary=False,
    )
    monkeypatch.setattr(engine.shutil, "which", lambda _name: None)
    biber_path = tmp_path / "bin" / "biber"
    biber_path.parent.mkdir(parents=True, exist_ok=True)
    biber_path.write_text("", encoding="utf-8")

    missing = engine.missing_dependencies(
        choice,
        features,
        use_system_tectonic=False,
        available_binaries={"biber": biber_path},
    )

    assert missing == []
