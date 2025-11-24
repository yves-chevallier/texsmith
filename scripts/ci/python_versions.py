from __future__ import annotations

from pathlib import Path
import re
import sys
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
        raise SystemExit("No Python versions found in pyproject classifiers.")

    unique = sorted(set(versions), key=lambda v: tuple(map(int, v.split("."))))
    sys.stdout.write(" ".join(unique))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
