#!/usr/bin/env bash
set -euo pipefail

# Install the Noto Sans Syriac font variant (Eastern or Western) from the published OTF files.
# Downloads specific weights directly from notofonts.github.io instead of relying on GitHub release zips.

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

for cmd in curl fc-cache; do
  require_cmd "$cmd"
done

variant="${1:-Eastern}"

case "$variant" in
  Eastern)
    urls=(
      "https://notofonts.github.io/syriac/fonts/NotoSansSyriacEastern/full/otf/NotoSansSyriacEastern-Thin.otf"
      "https://notofonts.github.io/syriac/fonts/NotoSansSyriacEastern/full/otf/NotoSansSyriacEastern-Regular.otf"
      "https://notofonts.github.io/syriac/fonts/NotoSansSyriacEastern/full/otf/NotoSansSyriacEastern-Black.otf"
    )
    ;;
  Western)
    urls=(
      "https://notofonts.github.io/syriac/fonts/NotoSansSyriacWestern/full/otf/NotoSansSyriacWestern-Thin.otf"
      "https://notofonts.github.io/syriac/fonts/NotoSansSyriacWestern/full/otf/NotoSansSyriacWestern-Regular.otf"
      "https://notofonts.github.io/syriac/fonts/NotoSansSyriacWestern/full/otf/NotoSansSyriacWestern-Black.otf"
    )
    ;;
  *)
    echo "Invalid variant '${variant}'. Expected 'Eastern' or 'Western'." >&2
    exit 1
    ;;
esac

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

font_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/fonts"
mkdir -p "${font_dir}"

for url in "${urls[@]}"; do
  dest="${tmp_dir}/$(basename "${url}")"
  echo "Downloading ${url}" >&2
  curl -sL -o "${dest}" "${url}"
  cp -f "${dest}" "${font_dir}/"
done

fc-cache -fv "${font_dir}"
echo "Installed Noto Sans Syriac ${variant} fonts to ${font_dir}"
