"""Minimal Playwright smoke test.

Launches headless Chromium, renders a tiny HTML snippet, and writes a screenshot
to /tmp/playwright-smoke.png. Exits non-zero on failure so CI can surface the
error.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 800, "height": 600})
            page.set_content("<html><body><h1>Hello Playwright</h1></body></html>")
            target = Path("/tmp/playwright-smoke.png")
            page.screenshot(path=target, full_page=True)
            browser.close()
            print(f"Playwright smoke test completed, screenshot at {target}")
            return 0
    except Exception as exc:  # pragma: no cover - debug helper
        print(f"Playwright smoke test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
