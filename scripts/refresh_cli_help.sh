#!/usr/bin/env bash
set -euo pipefail

# Write the current texsmith --help output (81-column width) to docs/assets/cli-help.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

mkdir -p docs/assets

export COLUMNS=85
# Force no color in help output to keep LaTeX clean on CI.
NO_COLOR=1 UV_NO_COLOR=1 TERM=dumb uv run texsmith --help > docs/assets/cli-help
# Strip trailing whitespace so diffs stay clean.
perl -pi -e 's/[ \t]+$//' docs/assets/cli-help
