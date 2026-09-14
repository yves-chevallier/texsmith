"""The CLI side of diagnostics: rendering, ``--strict``, ``--diagnostics-json``, ``-q``."""

from __future__ import annotations

import json
from pathlib import Path
import re

from typer.testing import CliRunner

from texsmith.ui.cli import app


DUPLICATE_COUNTER = """\
---
press:
  declare:
    counters:
      n:
        name: Requirement
        format: "N-{n:02d}"
---
First {counter}(n:joy) and again {counter}(n:joy).
"""

STRICT_FRONT_MATTER = DUPLICATE_COUNTER.replace(
    "press:\n",
    "press:\n  features:\n    strict: true\n",
    1,
)


def _write(directory: Path, text: str) -> Path:
    source = directory / "report.md"
    source.write_text(text, encoding="utf-8")
    return source


def test_authoring_defects_print_as_diagnostics(tmp_path: Path) -> None:
    source = _write(tmp_path, DUPLICATE_COUNTER)
    result = CliRunner().invoke(app, [str(source)])
    assert result.exit_code == 0, result.output
    assert f"{source}:9:34: warning label-duplicate: `#n:joy` is defined twice" in result.output
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
    source = _write(
        tmp_path, DUPLICATE_COUNTER.replace("again {counter}(n:joy)", "then {counter}(n:respect)")
    )
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
    assert record["origin"] == "tmark"
    assert record["path"] == str(source)
    assert (record["line"], record["col"]) == (9, 34)
    assert record["related"][0][1] == "first definition"


def test_diagnostics_json_is_written_for_a_clean_run(tmp_path: Path) -> None:
    source = _write(
        tmp_path, DUPLICATE_COUNTER.replace("again {counter}(n:joy)", "then {counter}(n:respect)")
    )
    dump = tmp_path / "diagnostics.json"
    result = CliRunner().invoke(app, [str(source), "--diagnostics-json", str(dump)])
    assert result.exit_code == 0, result.output
    assert json.loads(dump.read_text(encoding="utf-8")) == []


def test_quiet_keeps_warnings(tmp_path: Path) -> None:
    source = _write(tmp_path, DUPLICATE_COUNTER)
    result = CliRunner().invoke(app, [str(source), "-q"])
    assert result.exit_code == 0, result.output
    assert "warning label-duplicate" in result.output


# -- the ``--deprecated`` transition knob on the tmark reader -----------------

#: Legacy spellings tmark reports as ``deprecated-frontmatter-key`` (root
#: ``counters``) and ``deprecated`` (``#{prefix:key}``); nothing else is wrong.
LEGACY_SPELLINGS = """\
---
counters:
  n:
    format: "N-{n:02d}"
---
First #{n:joy}.
"""


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _tmark(source: Path, *extra: str) -> tuple[int, str]:
    # Typer colours its usage box when the terminal claims colour (CI sets
    # FORCE_COLOR); the assertions read the plain text.
    result = CliRunner().invoke(app, [str(source), *extra])
    return result.exit_code, _ANSI.sub("", result.output)


def test_deprecated_records_fail_strict_by_default(tmp_path: Path) -> None:
    source = _write(tmp_path, LEGACY_SPELLINGS)
    code, output = _tmark(source, "--strict")
    assert code == 1, output
    assert "warning deprecated-frontmatter-key: `counters` is deprecated" in output
    assert "warning deprecated: `#{prefix:key}` is deprecated" in output
    assert "0 errors, 2 warnings" in output


def test_deprecated_info_passes_strict_and_still_prints(tmp_path: Path) -> None:
    source = _write(tmp_path, LEGACY_SPELLINGS)
    code, output = _tmark(source, "--strict", "--deprecated", "info")
    assert code == 0, output
    assert "info deprecated-frontmatter-key: `counters` is deprecated" in output
    assert "info deprecated: `#{prefix:key}` is deprecated" in output
    assert "warning deprecated" not in output
    assert "warnings" not in output, "nothing at warning level: no summary line"
    # ``-q`` then hides them like any other info record.
    code, output = _tmark(source, "--strict", "--deprecated", "info", "-q")
    assert code == 0, output
    assert not _reports_deprecated(output)


def _reports_deprecated(output: str) -> bool:
    """Whether a ``deprecated`` / ``deprecated-frontmatter-key`` record was printed.

    (The pytest ``tmp_path`` of these tests spells ``deprecated`` too, so the
    check is on the ``severity code:`` part of the line.)
    """
    return " deprecated: " in output or " deprecated-frontmatter-key: " in output


def test_deprecated_off_drops_the_records(tmp_path: Path) -> None:
    source = _write(tmp_path, LEGACY_SPELLINGS)
    dump = tmp_path / "diagnostics.json"
    code, output = _tmark(
        source, "--strict", "--deprecated", "OFF", "--diagnostics-json", str(dump)
    )
    assert code == 0, output
    assert not _reports_deprecated(output)
    assert "errors" not in output, "nothing recorded, no summary"
    assert json.loads(dump.read_text(encoding="utf-8")) == []


def test_deprecated_level_leaves_other_warnings_alone(tmp_path: Path) -> None:
    source = _write(tmp_path, LEGACY_SPELLINGS.replace("First #{n:joy}.", "#{n:joy} #{n:joy}"))
    code, output = _tmark(source, "--strict", "--deprecated", "off")
    assert code == 1, output
    assert not _reports_deprecated(output)
    assert "warning label-duplicate" in output
    assert "0 errors, 1 warning" in output


def test_front_matter_sets_the_deprecated_level(tmp_path: Path) -> None:
    source = _write(
        tmp_path,
        LEGACY_SPELLINGS.replace(
            "counters:", "press:\n  diagnostics:\n    deprecated: info\ncounters:"
        ),
    )
    code, output = _tmark(source, "--strict")
    assert code == 0, output
    assert "info deprecated: `#{prefix:key}` is deprecated" in output
    # The CLI switch wins over the front matter.
    code, output = _tmark(source, "--strict", "--deprecated", "warning")
    assert code == 1, output
    assert "warning deprecated: `#{prefix:key}` is deprecated" in output


def test_deprecated_option_is_validated(tmp_path: Path) -> None:
    source = _write(tmp_path, LEGACY_SPELLINGS)
    code, output = _tmark(source, "--deprecated", "loud")
    assert code != 0
    assert "--deprecated must be 'warning', 'info' or 'off'" in output
