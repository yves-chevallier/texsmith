#!/usr/bin/env python3
"""Refresh ``tests/fixtures/tmark_codes.txt`` from tmark's ``diagnostic.rs``.

The fixture is the list of tmark's diagnostic identifiers; the test
``tests/test_diagnostics_codes.py`` checks that no TeXSmith code shadows one.
Run it after a tmark bump::

    uv run python scripts/refresh_tmark_codes.py            # reads ~/tmark
    uv run python scripts/refresh_tmark_codes.py /path/to/tmark
    uv run python scripts/refresh_tmark_codes.py --check    # exit 1 when stale

``TMARK_ROOT`` overrides the default checkout location.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "tmark_codes.txt"
SOURCE = Path("crates") / "tmark-ir" / "src" / "diagnostic.rs"

#: ``Code::AttrNoHost => "attr-no-host",`` inside ``fn id``.
_ID_ARM = re.compile(r'Code::\w+\s*=>\s*"([a-z0-9-]+)"')


def tmark_ids(root: Path) -> list[str]:
    """The identifiers of ``Code::id``, in catalogue order."""
    text = (root / SOURCE).read_text(encoding="utf-8")
    start = text.index("pub fn id(self)")
    end = text.index("pub fn default_severity", start)
    ids = _ID_ARM.findall(text[start:end])
    if not ids:
        raise SystemExit(f"no identifiers found in {root / SOURCE}")
    return ids


def render(ids: list[str]) -> str:
    header = [
        "# tmark diagnostic identifiers, vendored from",
        f"# {SOURCE.as_posix()} (Code::id). Refresh with",
        "# scripts/refresh_tmark_codes.py; do not edit by hand.",
    ]
    return "\n".join([*header, *ids]) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "root",
        nargs="?",
        default=os.environ.get("TMARK_ROOT", str(Path.home() / "tmark")),
        help="tmark checkout (default: $TMARK_ROOT or ~/tmark)",
    )
    parser.add_argument("--check", action="store_true", help="exit 1 when the fixture is stale")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser()
    content = render(tmark_ids(root))
    current = FIXTURE.read_text(encoding="utf-8") if FIXTURE.exists() else ""
    if args.check:
        if current != content:
            sys.stderr.write(f"{FIXTURE} is stale; run {Path(__file__).name}\n")
            return 1
        return 0
    if current != content:
        FIXTURE.write_text(content, encoding="utf-8")
        sys.stderr.write(f"wrote {FIXTURE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
