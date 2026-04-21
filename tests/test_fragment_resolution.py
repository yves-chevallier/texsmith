"""Tests for the fragment resolution logic, including the dict modifier format."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from texsmith.core.conversion.execution import _resolve_fragments_list
from texsmith.core.documents import Document
from texsmith.core.templates import load_template_runtime
from texsmith.core.templates.session import TemplateSession


_DEFAULTS = ["ts-geometry", "ts-typesetting", "ts-fonts", "ts-extra", "ts-code"]


def _runtime_with_defaults(fragments: list[str]) -> MagicMock:
    runtime = MagicMock()
    runtime.extras = {"fragments": fragments}
    return runtime


# ---------------------------------------------------------------------------
# Unit tests for _resolve_fragments_list
# ---------------------------------------------------------------------------


class TestResolveFragmentsList:
    def test_list_format_replaces_defaults(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, ["ts-code", "ts-fonts"], [], [])
        assert result == ["ts-code", "ts-fonts"]

    def test_none_returns_template_defaults(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, None, [], [])
        assert result == _DEFAULTS

    def test_none_no_runtime_returns_empty(self) -> None:
        result = _resolve_fragments_list(None, None, [], [])
        assert result == []

    def test_dict_append_adds_to_end(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {"append": ["./my-logo"]}, [], [])
        assert result == [*_DEFAULTS, "./my-logo"]

    def test_dict_prepend_adds_to_start(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {"prepend": ["./header"]}, [], [])
        assert result == ["./header", *_DEFAULTS]

    def test_dict_disable_removes_fragment(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {"disable": ["ts-geometry"]}, [], [])
        assert "ts-geometry" not in result
        assert "ts-fonts" in result

    def test_dict_disable_multiple(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {"disable": ["ts-geometry", "ts-extra"]}, [], [])
        assert "ts-geometry" not in result
        assert "ts-extra" not in result
        assert len(result) == len(_DEFAULTS) - 2

    def test_dict_all_keys_combined(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(
            runtime,
            {
                "disable": ["ts-geometry"],
                "prepend": ["./header"],
                "append": ["./footer"],
            },
            [],
            [],
        )
        assert result[0] == "./header"
        assert result[-1] == "./footer"
        assert "ts-geometry" not in result
        assert "ts-fonts" in result

    def test_dict_empty_has_no_effect(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {}, [], [])
        assert result == _DEFAULTS

    def test_dict_no_duplicates_from_append(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {"append": ["ts-fonts"]}, [], [])
        assert result.count("ts-fonts") == 1

    def test_dict_no_duplicates_from_prepend(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {"prepend": ["ts-fonts"]}, [], [])
        assert result.count("ts-fonts") == 1

    def test_dict_disable_applied_before_prepend(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        # ts-geometry is in defaults; disable it, then prepend something else
        result = _resolve_fragments_list(
            runtime,
            {"disable": ["ts-geometry"], "prepend": ["./header"]},
            [],
            [],
        )
        assert "ts-geometry" not in result
        assert result[0] == "./header"

    def test_cli_disable_still_applies_with_dict_format(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {"append": ["./logo"]}, [], ["ts-extra"])
        assert "ts-extra" not in result
        assert "./logo" in result

    def test_cli_enable_still_applies_with_dict_format(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {}, ["ts-glossary"], [])
        assert "ts-glossary" in result

    def test_dict_without_runtime_uses_empty_base(self) -> None:
        result = _resolve_fragments_list(
            None, {"append": ["./logo"], "prepend": ["./header"]}, [], []
        )
        assert result == ["./header", "./logo"]

    def test_string_values_are_stripped(self) -> None:
        runtime = _runtime_with_defaults(_DEFAULTS)
        result = _resolve_fragments_list(runtime, {"append": ["  ./logo  "]}, [], [])
        assert "./logo" in result
        assert "  ./logo  " not in result

    def test_duplicates_in_input_list_deduplicated(self) -> None:
        result = _resolve_fragments_list(None, ["ts-fonts", "ts-fonts", "ts-code"], [], [])
        assert result == ["ts-fonts", "ts-code"]


# ---------------------------------------------------------------------------
# Integration test via TemplateSession
# ---------------------------------------------------------------------------


def test_fragments_append_integration(tmp_path: Path) -> None:
    """Dict append format adds a custom fragment on top of template defaults."""
    fragment = tmp_path / "mylogo.sty"
    fragment.write_text(
        "\\ProvidesPackage{mylogo}[2025/01/01 Logo]\n\\newcommand{\\Logo}{LOGO}\n",
        encoding="utf-8",
    )

    md = tmp_path / "doc.md"
    md.write_text(
        "---\npress:\n  fragments:\n    append:\n      - mylogo.sty\n---\nBody\n",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{mylogo}" in tex
    assert "\\usepackage{ts-fonts}" in tex  # default not lost


def test_fragments_disable_integration(tmp_path: Path) -> None:
    """Dict disable format removes a specific built-in fragment."""
    md = tmp_path / "doc.md"
    md.write_text(
        "---\npress:\n  fragments:\n    disable:\n      - ts-geometry\n---\nBody\n",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{ts-geometry}" not in tex
    assert "\\usepackage[a4paper]{geometry}" not in tex
    assert "\\usepackage{ts-fonts}" in tex  # other defaults preserved


def test_fragments_prepend_integration(tmp_path: Path) -> None:
    """Dict prepend format injects a fragment before the built-ins."""
    fragment = tmp_path / "preamble.sty"
    fragment.write_text(
        "\\ProvidesPackage{preamble}[2025/01/01 Preamble]\n",
        encoding="utf-8",
    )

    md = tmp_path / "doc.md"
    md.write_text(
        "---\npress:\n  fragments:\n    prepend:\n      - preamble.sty\n---\nBody\n",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{preamble}" in tex
    assert "\\usepackage{ts-fonts}" in tex

    preamble_pos = tex.index("\\usepackage{preamble}")
    fonts_pos = tex.index("\\usepackage{ts-fonts}")
    assert preamble_pos < fonts_pos, "prepended fragment should appear before ts-fonts"
