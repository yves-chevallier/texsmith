#!/usr/bin/env bash
set -euo pipefail

# Install the latest Noto Sans Syriac Western font release into the local user font directory.
# Uses the GitHub releases API for notofonts/syriac to locate the newest zip asset.

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

for cmd in curl jq unzip fc-cache; do
  require_cmd "$cmd"
done

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

asset_url="$(
  curl -s https://api.github.com/repos/notofonts/syriac/releases/latest \
    | jq -r '.assets[] | select(.name | test("NotoSansSyriacWestern.*\\.zip$")) | .browser_download_url' \
    | head -n 1
)"

if [[ -z "${asset_url}" || "${asset_url}" == "null" ]]; then
  echo "Could not locate NotoSansSyriacWestern zip asset in latest release." >&2
  exit 1
fi

zip_path="${tmp_dir}/NotoSansSyriacWestern.zip"
curl -sL -o "${zip_path}" "${asset_url}"

unzip -q "${zip_path}" -d "${tmp_dir}/unpacked"

font_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/fonts"
mkdir -p "${font_dir}"

mapfile -t font_files < <(find "${tmp_dir}/unpacked" -type f \( -iname '*.otf' -o -iname '*.ttf' \))
if [[ "${#font_files[@]}" -eq 0 ]]; then
  echo "No font files found in downloaded archive." >&2
  exit 1
fi

for font in "${font_files[@]}"; do
  cp -f "${font}" "${font_dir}/"
done

fc-cache -fv "${font_dir}"
echo "Installed Noto Sans Syriac Western fonts to ${font_dir}"
