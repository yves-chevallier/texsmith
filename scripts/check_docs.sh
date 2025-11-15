#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${ROOT_DIR}/.uv-cache}"

echo "→ Building documentation with mkdocs --strict"
(
  cd "${ROOT_DIR}"
  uv run mkdocs build --strict
)

echo "Documentation check complete."
