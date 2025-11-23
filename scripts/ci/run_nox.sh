#!/usr/bin/env bash
set -euo pipefail

if [[ "${ACT:-}" == "true" ]]; then
  PY_VER="$(python - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
  echo "Running nox with runner Python ${PY_VER}"
  uv run nox -s tests -p "${PY_VER}"
else
  uv run nox -s tests
fi
