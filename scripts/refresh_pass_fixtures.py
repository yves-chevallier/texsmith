"""Refresh the IR fixtures of the pass tests (``tests/passes/<pass>/<case>.in.json``).

Every ``<case>.md`` under ``tests/passes/`` is parsed with the installed
``tmark`` wheel and written next to it as ``<case>.in.json`` (ids and spans
included), the input the harness in ``tests/passes/conftest.py`` loads. The
expected outputs (``.out.json``, ``.diag.json``) are reviewed by hand and not
touched here.

Usage::

    uv run python scripts/refresh_pass_fixtures.py [--check]

``--check`` exits 1 when a committed ``.in.json`` differs from a fresh parse
(the wheel moved; regenerate and review the goldens).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "passes"


def render(source: Path) -> str:
    import tmark

    payload = tmark.parse(source.read_text(encoding="utf-8"), file=source.name, file_id=0)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = parser.parse_args(argv)

    drift: list[Path] = []
    for source in sorted(FIXTURES.glob("*/*.md")):
        target = source.with_suffix(".in.json")
        fresh = render(source)
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != fresh:
                drift.append(target)
            continue
        target.write_text(fresh, encoding="utf-8")
        print(f"wrote {target.relative_to(ROOT)}")  # noqa: T201
    if drift:
        for path in drift:
            print(f"stale: {path.relative_to(ROOT)}", file=sys.stderr)  # noqa: T201
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
