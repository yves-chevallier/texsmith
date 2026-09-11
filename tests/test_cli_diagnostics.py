"""The CLI side of diagnostics: rendering, ``--strict``, ``--diagnostics-json``, ``-q``."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from texsmith.ui.cli import app


DUPLICATE_COUNTER = """\
---
counters:
  n:
    name: Requirement
    format: "N-{n:02d}"
---
First #{n:joy} and again #{n:joy}.
"""

STRICT_FRONT_MATTER = DUPLICATE_COUNTER.replace(
    "counters:",
    "press:\n  features:\n    strict: true\ncounters:",
)


def _write(directory: Path, text: str) -> Path:
    source = directory / "report.md"
    source.write_text(text, encoding="utf-8")
    return source


def test_authoring_defects_print_as_diagnostics(tmp_path: Path) -> None:
    source = _write(tmp_path, DUPLICATE_COUNTER)
    result = CliRunner().invoke(app, [str(source)])
    assert result.exit_code == 0, result.output
    assert (
        f"{source}: warning label-duplicate: Counter 'n:joy' is defined more than once; "
        "keeping the first number." in result.output
    )
    assert "0 errors, 1 warning" in result.output


def test_strict_fails_after_rendering(tmp_path: Path) -> None:
    source = _write(tmp_path, DUPLICATE_COUNTER)
    output = tmp_path / "report.tex"
    result = CliRunner().invoke(app, [str(source), "-o", str(output), "--strict"])
    assert result.exit_code == 1, result.output
    assert output.exists(), "the LaTeX is written before --strict stops the run"
    assert "warning label-duplicate" in result.output
    assert "--strict" in result.output


def test_strict_passes_a_clean_document(tmp_path: Path) -> None:
    source = _write(tmp_path, DUPLICATE_COUNTER.replace("again #{n:joy}", "then #{n:respect}"))
    result = CliRunner().invoke(app, [str(source), "--strict"])
    assert result.exit_code == 0, result.output
    assert "label-duplicate" not in result.output
    assert "errors" not in result.output, "no summary when nothing was recorded"


def test_front_matter_can_turn_strict_on(tmp_path: Path) -> None:
    source = _write(tmp_path, STRICT_FRONT_MATTER)
    result = CliRunner().invoke(app, [str(source)])
    assert result.exit_code == 1, result.output
    assert "warning label-duplicate" in result.output


def test_diagnostics_json_dumps_the_records(tmp_path: Path) -> None:
    source = _write(tmp_path, DUPLICATE_COUNTER)
    dump = tmp_path / "out" / "diagnostics.json"
    result = CliRunner().invoke(app, [str(source), "--diagnostics-json", str(dump)])
    assert result.exit_code == 0, result.output
    payload = json.loads(dump.read_text(encoding="utf-8"))
    assert len(payload) == 1
    (record,) = payload
    assert record["code"] == "label-duplicate"
    assert record["severity"] == "warning"
    assert record["origin"] == "texsmith"
    assert record["path"] == str(source)
    assert record["line"] is None and record["col"] is None
    assert record["span"][1:] == [0, 0]


def test_diagnostics_json_is_written_for_a_clean_run(tmp_path: Path) -> None:
    source = _write(tmp_path, DUPLICATE_COUNTER.replace("again #{n:joy}", "then #{n:respect}"))
    dump = tmp_path / "diagnostics.json"
    result = CliRunner().invoke(app, [str(source), "--diagnostics-json", str(dump)])
    assert result.exit_code == 0, result.output
    assert json.loads(dump.read_text(encoding="utf-8")) == []


def test_quiet_keeps_warnings(tmp_path: Path) -> None:
    source = _write(tmp_path, DUPLICATE_COUNTER)
    result = CliRunner().invoke(app, [str(source), "-q"])
    assert result.exit_code == 0, result.output
    assert "warning label-duplicate" in result.output
