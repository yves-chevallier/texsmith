#!/usr/bin/env bash
set -euo pipefail

# Write the current texsmith --help output (81-column width) to docs/assets/cli-help.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

mkdir -p docs/assets

export COLUMNS=85
uv run texsmith --help > docs/assets/cli-help
# Strip trailing whitespace so diffs stay clean.
perl -pi -e 's/[ \t]+$//' docs/assets/cli-help
