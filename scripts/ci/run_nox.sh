#!/usr/bin/env bash
set -euo pipefail

PY_VER="${NOX_PYTHON:-}"

if [[ -z "${PY_VER}" ]]; then
  PY_VER="$(python - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
fi

echo "Running nox with Python ${PY_VER}"
uv run nox -s tests -p "${PY_VER}"
