"""Standalone Playwright mermaid render without TexSmith wiring.

This mirrors the logic of Mermaid _run_playwright: load mermaid from CDN,
render a tiny diagram, export to PDF, and exit. Fails fast on error.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


TARGET = Path("/tmp/playwright-mermaid-direct.pdf")
MERMAID_SNIPPET = "graph TD; A[Hello] --> B[World];"


def main() -> int:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 2400, "height": 1800})
            page.set_content(
                """<!doctype html>
<html><head><meta charset="utf-8" />
<script src="https://unpkg.com/mermaid@11/dist/mermaid.min.js"></script>
</head><body style="margin:0; background:white;"><div id="container"></div></body></html>""",
                wait_until="load",
                timeout=120_000,
            )
            page.evaluate("cfg => { window.mermaid.initialize(cfg); }", {"startOnLoad": False, "theme": "neutral"})
            svg = page.evaluate(
                """
async (code) => {
  const result = await window.mermaid.render("theGraph", code);
  const header = '<?xml version="1.0" encoding="UTF-8"?>\\n';
  return header + result.svg;
}
""",
                MERMAID_SNIPPET,
            )
            pdf_page = browser.new_page()
            pdf_page.set_content(f"<html><body style='margin:0; display:inline-block'>{svg}</body></html>")
            locator = pdf_page.locator("svg")
            box = locator.bounding_box()
            width = int(box["width"]) if box else 800
            height = int(box["height"]) if box else 600
            pdf_page.pdf(
                path=str(TARGET),
                print_background=True,
                width=f"{width}px",
                height=f"{height}px",
                page_ranges="1",
            )
            pdf_page.close()
            browser.close()
            print(f"Direct mermaid render succeeded, PDF at {TARGET}")
            return 0
    except Exception as exc:  # pragma: no cover - debug helper
        print(f"Direct mermaid render failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
