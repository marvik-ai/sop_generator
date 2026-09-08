#!/usr/bin/env bash
# Re-downloads the local-only video fixtures listed in manifest.md.
# Not committed to git — see .gitignore. Requires `uv` (uses `uvx yt-dlp`
# and `uvx --from imageio-ffmpeg` for a sandboxed ffmpeg, no sudo/apt needed).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

FFMPEG=$(uvx --from imageio-ffmpeg python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")

download() {
  local out="$1" url="$2"
  echo "== $out =="
  uvx yt-dlp --no-warnings --ffmpeg-location "$FFMPEG" \
    -f "bv*[height<=480]+ba/b[height<=480]" --merge-output-format mp4 \
    -o "${out}.%(ext)s" "$url"
}

# Here is an example usage of the `download` function. Uncomment to download a video fixture.

# download "01_pivot_table_1min"     "https://www.youtube.com/shorts/tL9qyGP9ivI"
