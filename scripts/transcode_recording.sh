#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: scripts/transcode_recording.sh <input.webm> [output.mp4]" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required but was not found on PATH." >&2
  exit 1
fi

input_path=$1
if [[ ! -f "$input_path" ]]; then
  echo "Input file not found: $input_path" >&2
  exit 1
fi

if [[ $# -eq 2 ]]; then
  output_path=$2
else
  input_stem=${input_path%.*}
  output_path="${input_stem}.mp4"
fi

ffmpeg -y \
  -i "$input_path" \
  -c:v libx264 \
  -pix_fmt yuv420p \
  -movflags +faststart \
  -an \
  "$output_path"

echo "Wrote $output_path"
