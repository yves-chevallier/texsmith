"""End-to-end tests for the MkDocs plugin numbering custom counters site-wide.

The site is rendered through the ``texsmith`` plugin on tmark: the pre-pass
resolves every page with ``numbering: "all"`` and a ``start`` chained in
navigation order, and each page is lowered with ``tmark.lower_web``.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re

import pytest


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
  - texsmith:
      declare:
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
| #(fw:watchdog) | The watchdog does not fire. |
| #(fw:ota-brick) | OTA update bricks the node. |

Requirement #(req:watchdog-reset) is not met by @fw:watchdog.

## Log buffer wiped {#fw:log-wrap}

See @fw:log-wrap.
"""


def build_site(root: Path, mkdocs_yml: str, pages: dict[str, str]) -> Path:
    """Write ``pages`` under ``docs/``, build the site, return its directory."""
    (root / "docs").mkdir(exist_ok=True)
    (root / "mkdocs.yml").write_text(mkdocs_yml, encoding="utf-8")
    for name, text in pages.items():
        target = root / "docs" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    config = load_config(str(root / "mkdocs.yml"), site_dir=str(root / "site"))
    mkdocs_build(config)
    return root / "site"


@pytest.fixture
def site(tmp_path: Path) -> dict[str, str]:
    """Build a two-page MkDocs site and return its rendered pages."""
    site_dir = build_site(tmp_path, MKDOCS_YML, {"index.md": INDEX_MD, "findings.md": FINDINGS_MD})
    return {
        "index": (site_dir / "index.html").read_text(encoding="utf-8"),
        "findings": (site_dir / "findings" / "index.html").read_text(encoding="utf-8"),
    }


def counter_span(html: str, identifier: str) -> str | None:
    """The text of the ``ts-counter`` span carrying ``identifier``.

    ``lower_web`` writes the attributes as ``class``, ``id``, ``data-counter``,
    ``data-key`` (the per-construct table of ``web-profile.md``), so the id is
    not the last attribute before the text.
    """
    match = re.search(
        rf'<span class="ts-counter" id="{re.escape(identifier)}"[^>]*>([^<]*)</span>', html
    )
    return match.group(1) if match else None


def test_definitions_render_their_formatted_number(site: dict[str, str]) -> None:
    html = site["findings"]
    assert counter_span(html, "fw:watchdog") == "FW-01"
    assert counter_span(html, "fw:ota-brick") == "FW-02"


def test_site_wide_counter_declared_in_mkdocs_yml_honours_start(site: dict[str, str]) -> None:
    assert counter_span(site["findings"], "req:watchdog-reset") == "REQ-100"


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


def test_deprecated_plugin_aliases_warn_and_do_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    mkdocs_yml = """\
site_name: Aliases
plugins:
  - texsmith.counters:
      counters:
        req:
          format: "REQ-{n}"
  - texsmith.index
nav:
  - index.md
"""
    with caplog.at_level(logging.WARNING, logger="mkdocs"):
        site_dir = build_site(
            tmp_path, mkdocs_yml, {"index.md": "# Home\n\nItem #(req:one) here.\n"}
        )
    messages = [record.getMessage() for record in caplog.records]
    assert any("'texsmith.counters' plugin is deprecated" in m for m in messages)
    assert any("'texsmith.index' plugin is deprecated" in m for m in messages)
    # Without the ``texsmith`` plugin nothing is numbered: the marker stays.
    assert "Item #(req:one) here." in (site_dir / "index.html").read_text(encoding="utf-8")
