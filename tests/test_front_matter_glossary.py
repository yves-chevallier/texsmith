"""Tests for the front-matter ``glossary`` section and end-to-end rendering."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import bs4  # noqa: F401  (ensure real BeautifulSoup is loaded for downstream imports)
import pytest

from texsmith.core.conversion.glossary import (
    GlossaryEntry,
    GlossaryFrontMatter,
    GlossaryGroup,
    GlossaryValidationError,
    append_synthetic_abbr_lines,
    parse_front_matter_glossary,
)


try:
    from texsmith.ui.cli import render  # type: ignore[attr-defined]
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    if exc.name == "typer":
        render = None
    else:
        raise


pytestmark_render = pytest.mark.skipif(render is None, reason="Typer dependency is not available.")


ARTICLE_TEMPLATE = str(
    Path(__file__).resolve().parents[1] / "src" / "texsmith" / "templates" / "article"
)


def test_parse_returns_none_when_glossary_missing() -> None:
    assert parse_front_matter_glossary(None) is None
    assert parse_front_matter_glossary({}) is None
    assert parse_front_matter_glossary({"glossary": False}) is None


def test_parse_legacy_string_form() -> None:
    payload = parse_front_matter_glossary({"glossary": "long3col"})
    assert isinstance(payload, GlossaryFrontMatter)
    assert payload.style == "long3col"
    assert payload.entries == []
    assert payload.groups == []


def test_parse_full_payload_with_groups() -> None:
    fm = {
        "glossary": {
            "style": "long",
            "groups": {
                "tech": "Acronymes techniques",
                "inst": "Acronymes institutionnels",
            },
            "entries": {
                "API": {
                    "group": "tech",
                    "description": "Application Programming Interface",
                },
                "ONU": {
                    "group": "inst",
                    "description": "Organisation des Nations Unies",
                },
                "XYZ": "Plain ungrouped acronym",
            },
        }
    }

    payload = parse_front_matter_glossary(fm)
    assert payload is not None
    assert payload.style == "long"
    assert payload.groups == [
        GlossaryGroup(key="tech", title="Acronymes techniques"),
        GlossaryGroup(key="inst", title="Acronymes institutionnels"),
    ]
    assert payload.entries == [
        GlossaryEntry(
            key="API",
            description="Application Programming Interface",
            group="tech",
        ),
        GlossaryEntry(
            key="ONU",
            description="Organisation des Nations Unies",
            group="inst",
        ),
        GlossaryEntry(key="XYZ", description="Plain ungrouped acronym"),
    ]


def test_parse_rejects_unknown_group_reference() -> None:
    fm = {
        "glossary": {
            "groups": {"tech": "Tech"},
            "entries": {"API": {"description": "API", "group": "missing"}},
        }
    }

    with pytest.raises(GlossaryValidationError):
        parse_front_matter_glossary(fm)


def test_parse_rejects_invalid_glossary_shape() -> None:
    with pytest.raises(GlossaryValidationError):
        parse_front_matter_glossary({"glossary": ["not", "a", "mapping"]})


def test_synthetic_abbr_lines_use_long_form_when_present() -> None:
    payload = GlossaryFrontMatter(
        entries=[
            GlossaryEntry(key="API", description="API short", long="Application Programming Interface"),
            GlossaryEntry(key="HTTP", description="HyperText Transfer Protocol"),
        ]
    )
    lines = payload.synthetic_abbr_lines()
    assert lines == [
        "*[API]: Application Programming Interface",
        "*[HTTP]: HyperText Transfer Protocol",
    ]


def test_append_synthetic_abbr_lines_adds_block() -> None:
    payload = GlossaryFrontMatter(
        entries=[GlossaryEntry(key="API", description="Application Programming Interface")]
    )
    body = "Some body that mentions API.\n"
    result = append_synthetic_abbr_lines(body, payload)
    assert result.endswith("*[API]: Application Programming Interface\n")
    assert "Some body that mentions API." in result


def test_append_synthetic_abbr_lines_skips_when_no_entries() -> None:
    payload = GlossaryFrontMatter()
    body = "no glossary here\n"
    assert append_synthetic_abbr_lines(body, payload) is body


@pytestmark_render
def test_front_matter_glossary_renders_groups_and_localised_title() -> None:
    """End-to-end: front-matter glossary produces grouped \\printglossary calls."""
    source = """---
title: Glossary demo
language: french
glossary:
  style: long
  groups:
    tech: Acronymes techniques
    inst: Acronymes institutionnels
  entries:
    API:
      group: tech
      description: Application Programming Interface
    ONU:
      group: inst
      description: Organisation des Nations Unies
    XYZ: Plain ungrouped acronym
---

# Sample

The API is used. The ONU was founded in 1945. XYZ is here.
"""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        src = temp_path / "doc.md"
        src.write_text(source, encoding="utf-8")
        out_dir = temp_path / "build"

        assert render is not None
        render(input_path=src, output=out_dir, template=ARTICLE_TEMPLATE)

        tex = (out_dir / "doc.tex").read_text(encoding="utf-8")
        sty = (out_dir / "ts-glossary.sty").read_text(encoding="utf-8")

        # Babel must come before glossaries for localisation to kick in.
        babel_pos = tex.find("\\usepackage[french]{babel}")
        glossaries_pos = tex.find("\\usepackage{ts-glossary}")
        assert 0 <= babel_pos < glossaries_pos

        # Groups become \newglossary*; entries get type=<group> assignments.
        assert "\\newglossary*{tech}{Acronymes techniques}" in sty
        assert "\\newglossary*{inst}{Acronymes institutionnels}" in sty
        assert "\\newacronym[type=tech]{API}{API}{Application Programming Interface}" in sty
        assert "\\newacronym[type=inst]{ONU}{ONU}{Organisation des Nations Unies}" in sty
        assert "\\newacronym{XYZ}{XYZ}{Plain ungrouped acronym}" in sty
        assert "\\setglossarystyle{long}" in sty

        # Body acronyms get \acrshort substitution from the synthesised abbr lines.
        assert "\\acrshort{API}" in tex
        assert "\\acrshort{ONU}" in tex
        assert "\\acrshort{XYZ}" in tex

        # Backmatter: ungrouped table first (using default \acronymname title), then
        # one \printglossary per group in declaration order. No bare \printglossary
        # (legacy main-glossary call) when ``glossary`` is a structured config.
        assert "\\printglossary[type=\\acronymtype]" in tex
        assert "List of Acronyms" not in tex
        tech_idx = tex.find("\\printglossary[type=tech")
        inst_idx = tex.find("\\printglossary[type=inst")
        assert 0 <= tech_idx < inst_idx
        # No double \printglossary (without type) — that would render an empty main glossary.
        bare_calls = [
            line for line in tex.splitlines() if line.strip() == "\\printglossary"
        ]
        assert bare_calls == []


@pytestmark_render
def test_front_matter_glossary_merges_with_body_definitions() -> None:
    source = """---
title: Mixed
glossary:
  entries:
    API: Application Programming Interface
---

API and NMR are common acronyms.

*[NMR]: Nuclear Magnetic Resonance
"""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        src = temp_path / "doc.md"
        src.write_text(source, encoding="utf-8")
        out_dir = temp_path / "build"

        assert render is not None
        render(input_path=src, output=out_dir, template=ARTICLE_TEMPLATE)

        tex = (out_dir / "doc.tex").read_text(encoding="utf-8")
        sty = (out_dir / "ts-glossary.sty").read_text(encoding="utf-8")

        assert "\\newacronym{API}{API}{Application Programming Interface}" in sty
        assert "\\newacronym{NMR}{NMR}{Nuclear Magnetic Resonance}" in sty
        assert "\\acrshort{API}" in tex
        assert "\\acrshort{NMR}" in tex


@pytestmark_render
def test_front_matter_glossary_includes_unused_entries() -> None:
    """Entries declared in the front matter must appear even if absent from the body."""
    source = """---
title: Unused
glossary:
  entries:
    API: Application Programming Interface
    HTTP: HyperText Transfer Protocol
---

This document mentions only API.
"""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        src = temp_path / "doc.md"
        src.write_text(source, encoding="utf-8")
        out_dir = temp_path / "build"

        assert render is not None
        render(input_path=src, output=out_dir, template=ARTICLE_TEMPLATE)

        sty = (out_dir / "ts-glossary.sty").read_text(encoding="utf-8")
        # Both entries present; HTTP never appears in body but must be defined.
        assert "\\newacronym{API}{API}{Application Programming Interface}" in sty
        assert "\\newacronym{HTTP}{HTTP}{HyperText Transfer Protocol}" in sty
