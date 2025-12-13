"""Exercise TexSmith's Mermaid Playwright backend directly.

This mirrors the code path used in examples/diagrams: it instantiates the
MermaidToPdfStrategy and forces the Playwright backend to render a tiny graph.
Fails with a non-zero exit code if anything goes wrong.
"""

from __future__ import annotations

import sys
from pathlib import Path

from texsmith.adapters.transformers import strategies
from texsmith.adapters.transformers.strategies import MermaidToPdfStrategy


def _inline_worker(func):
    print("[smoke] _PlaywrightWorker.run -> inline execution", flush=True)
    return func()


def main() -> int:
    print("[smoke] start", flush=True)
    target = Path("/tmp/mermaid-playwright-smoke.pdf")
    content = "graph TD; A[Hello] --> B[Playwright]"
    # Monkeypatch worker to avoid threads and add logs.
    strategies._PlaywrightWorker.run = staticmethod(_inline_worker)

    # Wrap ensure_browser to log entry/exit.
    original_ensure = strategies._PlaywrightManager.ensure_browser

    def ensure_browser_with_logs(cls, *args, **kwargs):
        print("[smoke] ensure_browser: enter", flush=True)
        res = original_ensure(*args, **kwargs)
        print("[smoke] ensure_browser: exit", flush=True)
        return res

    strategies._PlaywrightManager.ensure_browser = classmethod(ensure_browser_with_logs)

    original_svg_to_pdf = MermaidToPdfStrategy._svg_to_pdf

    def svg_to_pdf_with_logs(self, browser, svg, target):
        print("[smoke] _svg_to_pdf: enter", flush=True)
        res = original_svg_to_pdf(self, browser, svg, target)
        print("[smoke] _svg_to_pdf: exit", flush=True)
        return res

    MermaidToPdfStrategy._svg_to_pdf = svg_to_pdf_with_logs

    strategy = MermaidToPdfStrategy()
    try:
        print("[smoke] calling _run_playwright()", flush=True)
        strategy._run_playwright(  # noqa: SLF001 - intentional test of private API
            content,
            target=target,
            format_opt="pdf",
            theme="neutral",
            mermaid_config=None,
            emitter=None,
        )
    except Exception as exc:  # pragma: no cover - debug helper
        print(f"[smoke] Mermaid Playwright smoke failed: {exc}", file=sys.stderr, flush=True)
        return 1

    print(f"[smoke] Mermaid Playwright smoke succeeded, PDF at {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
