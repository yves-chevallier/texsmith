"""End-to-end tests for the MkDocs plugin rendering TeXSmith custom counters."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from texsmith.core.counters import clear_registry


try:  # pragma: no cover - optional dependency for this suite
    from mkdocs.commands.build import build as mkdocs_build
    from mkdocs.config import load_config
except ModuleNotFoundError:  # pragma: no cover - graceful degradation
    mkdocs_build = None  # type: ignore[assignment]
    load_config = None  # type: ignore[assignment]


pytestmark = pytest.mark.skipif(mkdocs_build is None, reason="MkDocs is not installed")


MKDOCS_YML = """\
site_name: Counters demo
plugins:
  - texsmith.counters:
      counters:
        req:
          name: Requirement
          format: "REQ-{n:03d}"
          start: 100
nav:
  - Overview: index.md
  - Findings: findings.md
"""

INDEX_MD = """\
# Overview

The blocking issue is finding @fw:watchdog, described on the next page,
and it violates @req:watchdog-reset.

A Ruby interpolation such as #{user.name} must stay literal.
"""

FINDINGS_MD = """\
---
counters:
  fw:
    name: Finding
    format: "FW-{n:02d}"
---

# Findings

| Id | Finding |
| --- | --- |
| #{fw:watchdog} | The watchdog does not fire. |
| #{fw:ota-brick} | OTA update bricks the node. |

Requirement #{req:watchdog-reset} is not met by @fw:watchdog.

## Log buffer wiped {#fw:log-wrap}

See @fw:log-wrap.
"""


@pytest.fixture(autouse=True)
def _clear_counter_registry() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def site(tmp_path: Path) -> dict[str, str]:
    """Build a two-page MkDocs site and return its rendered pages."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    (tmp_path / "docs" / "index.md").write_text(INDEX_MD, encoding="utf-8")
    (tmp_path / "docs" / "findings.md").write_text(FINDINGS_MD, encoding="utf-8")

    config = load_config(str(tmp_path / "mkdocs.yml"), site_dir=str(tmp_path / "site"))
    mkdocs_build(config)

    return {
        "index": (tmp_path / "site" / "index.html").read_text(encoding="utf-8"),
        "findings": (tmp_path / "site" / "findings" / "index.html").read_text(encoding="utf-8"),
    }


def test_definitions_render_their_formatted_number(site: dict[str, str]) -> None:
    html = site["findings"]
    assert 'id="fw:watchdog">FW-01' in html
    assert 'id="fw:ota-brick">FW-02' in html


def test_site_wide_counter_declared_in_mkdocs_yml_honours_start(site: dict[str, str]) -> None:
    assert 'id="req:watchdog-reset">REQ-100' in site["findings"]


def test_silent_heading_definition_continues_the_series(site: dict[str, str]) -> None:
    assert '<a href="#fw:log-wrap">FW-03</a>' in site["findings"]


def test_same_page_reference_keeps_a_local_anchor(site: dict[str, str]) -> None:
    assert '<a href="#fw:watchdog">FW-01</a>' in site["findings"]


def test_cross_page_forward_reference_resolves_to_the_defining_page(site: dict[str, str]) -> None:
    # ``fw`` is declared in findings.md only, and referenced from index.html —
    # which MkDocs renders first, before the definition has been converted.
    assert '<a href="findings/#fw:watchdog">FW-01</a>' in site["index"]
    assert '<a href="findings/#req:watchdog-reset">REQ-100</a>' in site["index"]


def test_undeclared_prefix_stays_literal_on_a_site(site: dict[str, str]) -> None:
    assert "#{user.name}" in site["index"]
