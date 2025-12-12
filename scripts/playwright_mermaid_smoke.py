"""Exercise TexSmith's Mermaid Playwright backend directly.

This mirrors the code path used in examples/diagrams: it instantiates the
MermaidToPdfStrategy and forces the Playwright backend to render a tiny graph.
Fails with a non-zero exit code if anything goes wrong.
"""

from __future__ import annotations

import sys
from pathlib import Path

from texsmith.adapters.transformers.strategies import MermaidToPdfStrategy


def main() -> int:
    target = Path("/tmp/mermaid-playwright-smoke.pdf")
    content = "graph TD; A[Hello] --> B[Playwright]"
    strategy = MermaidToPdfStrategy()
    try:
        strategy._run_playwright(  # noqa: SLF001 - intentional test of private API
            content,
            target=target,
            format_opt="pdf",
            theme="neutral",
            mermaid_config=None,
            emitter=None,
        )
    except Exception as exc:  # pragma: no cover - debug helper
        print(f"Mermaid Playwright smoke failed: {exc}", file=sys.stderr)
        return 1

    print(f"Mermaid Playwright smoke succeeded, PDF at {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
