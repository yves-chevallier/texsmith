#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build/examples-smoke"

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

run_render() {
  local example_dir=$1
  shift
  echo "→ Running texsmith render in ${example_dir}"
  (
    cd "${ROOT_DIR}/${example_dir}"
    texsmith render "$@" \
      --template article \
      --output-dir "${BUILD_DIR}/${example_dir}" \
      --build \
      --classic-output
  )
}

run_render "examples/paper" cheese.md cheese.bib
run_render "examples/diagrams" diagrams.md
run_render "examples/markdown" features.md

echo "Smoke tests complete. Outputs stored in ${BUILD_DIR}"
