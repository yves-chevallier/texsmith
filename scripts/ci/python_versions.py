from __future__ import annotations

import re
import sys
from pathlib import Path

import tomllib


def main() -> int:
    pyproject = Path("pyproject.toml")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    classifiers = data.get("project", {}).get("classifiers", [])

    versions: list[str] = []
    for classifier in classifiers:
        match = re.fullmatch(r"Programming Language :: Python :: (\d\.\d+)", classifier.strip())
        if match:
            versions.append(match.group(1))

    if not versions:
        msg = "No Python versions found in pyproject classifiers."
        print(msg, file=sys.stderr)
        return 1

    unique = sorted(set(versions), key=lambda v: tuple(map(int, v.split("."))))
    print(" ".join(unique))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
