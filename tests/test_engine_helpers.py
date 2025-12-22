import os
from pathlib import Path

import pytest

from texsmith.adapters.latex import engines as engine, pyxindy


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


def test_run_engine_command_invokes_aux_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = engine.EngineCommand(
        argv=["tectonic", "main.tex"],
        log_path=tmp_path / "main.log",
        pdf_path=tmp_path / "main.pdf",
    )
    features = engine.EngineFeatures(
        requires_shell_escape=False,
        bibliography=True,
        has_index=True,
        has_glossary=True,
    )
    passes = {"count": 0}

    def fake_run(
        argv: list[str], *, workdir: Path, env: dict[str, str], console: object
    ) -> engine.LatexStreamResult:
        passes["count"] += 1
        if passes["count"] == 1:
            for suffix in ("bcf", "idx", "glo"):
                (workdir / f"main.{suffix}").write_text("", encoding="utf-8")
            log_text = (
                "LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.\n"
            )
        else:
            log_text = "Document stable.\n"
        command.log_path.write_text(log_text, encoding="utf-8")
        return engine.LatexStreamResult(returncode=0, messages=[])

    tool_calls: list[list[str]] = []

    class _Result:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    def fake_subprocess(argv: list[str], **_: object) -> _Result:
        tool_calls.append(list(argv))
        return _Result()

    monkeypatch.setattr(engine, "run_tectonic_engine", fake_run)
    monkeypatch.setattr(engine.subprocess, "run", fake_subprocess)
    monkeypatch.setattr(engine.shutil, "which", lambda name: f"/usr/bin/{name}")

    result = engine.run_engine_command(
        command,
        backend="tectonic",
        workdir=tmp_path,
        env={},
        console=None,
        features=features,
    )

    assert result.returncode == 0
    assert passes["count"] == 2
    expected_index = "makeindex-py" if engine.pyxindy_available() else "texindy"
    normalized = [[Path(call[0]).name, *call[1:]] for call in tool_calls]
    assert normalized[0] == ["biber", "main"]
    assert normalized[1][0] == expected_index
    assert normalized[1][-1] == "main.idx"
    if expected_index == "makeindex-py":
        assert "--input-encoding=utf-8" in normalized[1]
        assert "--output-encoding=utf-8" in normalized[1]
    expected_glossaries = "makeglossaries-py" if engine.pyxindy_available() else "makeglossaries"
    assert normalized[2] == [expected_glossaries, "main"]


def test_pyxindy_index_tokens_use_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine.shutil, "which", lambda name: f"/usr/bin/{name}")
    tokens = engine.pyxindy_index_tokens()
    assert tokens[0].endswith("makeindex-py")
    assert "--input-encoding=utf-8" in tokens
    assert "--output-encoding=utf-8" in tokens


def test_pyxindy_sanitize_xdy_rewrites_empty_close(tmp_path: Path) -> None:
    xdy_path = tmp_path / "demo.xdy"
    xdy_path.write_text(
        '(markup-locref :open "x" :close "" :attr "pageglsnumberformat")',
        encoding="utf-8",
    )

    assert pyxindy.sanitize_xdy(xdy_path) is True
    assert ':close ""' not in xdy_path.read_text(encoding="utf-8")


def test_pyxindy_sanitize_glossary_output_fixes_entries(tmp_path: Path) -> None:
    acr_path = tmp_path / "demo.acr"
    acr_path.write_text(
        "\\glossentry{DFT} {\\glossaryentrynumbers{\\relax ~n\\glsXpageXglsnumberformat{}{1}\n\n",
        encoding="utf-8",
    )

    assert pyxindy.sanitize_glossary_output(acr_path) is True
    content = acr_path.read_text(encoding="utf-8")
    assert "~n" not in content
    assert content.strip().endswith("}}")


def test_glossaries_prefers_pyxindy_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Helper:
        def __init__(self, path: Path) -> None:
            self.path = path

    monkeypatch.setattr(engine, "pyxindy_available", lambda: True)
    monkeypatch.setattr(
        engine,
        "select_makeglossaries",
        lambda *_args, **_kwargs: _Helper(Path("/usr/bin/makeglossaries")),
    )
    tokens = engine._glossaries_command_tokens()
    if Path(tokens[0]).stem == "makeglossaries-py":
        assert tokens == [tokens[0]]
    else:
        assert tokens[1:] == ["-m", "xindy.tex.makeglossaries"]


def test_run_engine_command_reruns_until_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = engine.EngineCommand(
        argv=["tectonic", "main.tex"],
        log_path=tmp_path / "main.log",
        pdf_path=tmp_path / "main.pdf",
    )
    features = engine.EngineFeatures(
        requires_shell_escape=False,
        bibliography=False,
        has_index=False,
        has_glossary=False,
    )
    passes = 0

    def fake_run(
        argv: list[str], *, workdir: Path, env: dict[str, str], console: object
    ) -> engine.LatexStreamResult:
        nonlocal passes
        passes += 1
        if passes == 1:
            log_text = "Label(s) may have changed. Rerun to get cross-references right.\n"
        else:
            log_text = "All references resolved.\n"
        command.log_path.write_text(log_text, encoding="utf-8")
        return engine.LatexStreamResult(returncode=0, messages=[])

    def fail_run(*_: object, **__: object) -> None:  # pragma: no cover - safety
        raise AssertionError("Auxiliary tools should not run")

    monkeypatch.setattr(engine, "run_tectonic_engine", fake_run)
    monkeypatch.setattr(engine.subprocess, "run", fail_run)

    result = engine.run_engine_command(
        command,
        backend="tectonic",
        workdir=tmp_path,
        env={},
        console=None,
        features=features,
    )

    assert result.returncode == 0
    assert passes == 2


def test_run_engine_command_enforces_rerun_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = engine.EngineCommand(
        argv=["tectonic", "main.tex"],
        log_path=tmp_path / "main.log",
        pdf_path=tmp_path / "main.pdf",
    )
    features = engine.EngineFeatures(
        requires_shell_escape=False,
        bibliography=False,
        has_index=False,
        has_glossary=False,
    )

    def fake_run(
        argv: list[str], *, workdir: Path, env: dict[str, str], console: object
    ) -> engine.LatexStreamResult:
        command.log_path.write_text(
            "LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.\n",
            encoding="utf-8",
        )
        return engine.LatexStreamResult(returncode=0, messages=[])

    def fail_run(*_: object, **__: object) -> None:  # pragma: no cover - safety
        raise AssertionError("Auxiliary tools should not run")

    monkeypatch.setattr(engine, "run_tectonic_engine", fake_run)
    monkeypatch.setattr(engine.subprocess, "run", fail_run)

    result = engine.run_engine_command(
        command,
        backend="tectonic",
        workdir=tmp_path,
        env={},
        console=None,
        features=features,
        rerun_limit=1,
    )

    assert result.returncode == 1
    assert result.messages
    assert "did not resolve references" in result.messages[0].summary
