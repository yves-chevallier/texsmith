"""TeXSmith's code table against tmark's identifiers.

``tests/fixtures/tmark_codes.txt`` is a vendored copy of the ids in
``crates/tmark-ir/src/diagnostic.rs``, refreshed by
``scripts/refresh_tmark_codes.py``.
"""

from __future__ import annotations

from pathlib import Path
import re

from texsmith.diagnostics import CODES, Severity, default_severity
from texsmith.diagnostics.codes import own_codes, reused_tmark_codes


FIXTURE = Path(__file__).parent / "fixtures" / "tmark_codes.txt"
KEBAB = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _tmark_ids() -> frozenset[str]:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    ids = frozenset(line.strip() for line in lines if line.strip() and not line.startswith("#"))
    assert ids, "the vendored tmark id list is empty; run scripts/refresh_tmark_codes.py"
    return ids


def test_own_codes_do_not_shadow_a_tmark_id() -> None:
    clash = own_codes() & _tmark_ids()
    assert not clash, f"TeXSmith codes shadow tmark ids: {sorted(clash)}"


def test_reused_codes_are_tmark_ids() -> None:
    unknown = reused_tmark_codes() - _tmark_ids()
    assert not unknown, f"codes marked as tmark's are not in tmark's list: {sorted(unknown)}"


def test_the_table_covers_the_planned_codes() -> None:
    planned = {
        "asset-missing",
        "asset-convert-failed",
        "doi-fetch-failed",
        "snippet-build-failed",
        "slot-missing",
        "slot-selector-unsupported",
        "slot-nested-heading",
        "var-unresolved",
        "var-not-scalar",
        "font-missing",
        "frontmatter-root-overrides-press",
        "file-unreadable",
        "include-missing",
        "deprecated-frontmatter-key",
    }
    assert planned <= set(CODES)


def test_every_code_the_python_side_emits_is_in_the_table() -> None:
    """A code passed to ``emit`` or ``emit_diagnostic`` must be declared.

    The table is what ``--diagnostics-json`` consumers and the guide read, and
    a code absent from it silently defaults to ``warning``. Only literals are
    checked — a code built at runtime would not be greppable either.
    """
    root = Path(__file__).resolve().parents[1] / "src" / "texsmith"
    call = re.compile(r"(?:\.emit|emit_diagnostic)\(\s*(?:[\w.]+,\s*)?\"([a-z][a-z0-9-]*)\"")
    seen: set[str] = set()
    for path in root.rglob("*.py"):
        seen.update(call.findall(path.read_text(encoding="utf-8")))
    assert seen, "no coded emission found; the pattern no longer matches"
    undeclared = seen - set(CODES) - _tmark_ids()
    assert not undeclared, f"codes emitted but not declared: {sorted(undeclared)}"


def test_codes_are_kebab_case_with_a_doc_line() -> None:
    for code, info in CODES.items():
        assert KEBAB.match(code), code
        assert info.code == code
        assert info.doc and "\n" not in info.doc and not info.doc.endswith(".")


def test_default_severity_from_the_table_or_warning() -> None:
    assert default_severity("frontmatter-root-overrides-press") is Severity.INFO
    assert default_severity("asset-missing") is Severity.WARNING
    assert default_severity("base-level-invalid") is Severity.ERROR
    # A tmark id not listed here (records arrive with their own severity anyway).
    assert default_severity("heading-skip") is Severity.WARNING
