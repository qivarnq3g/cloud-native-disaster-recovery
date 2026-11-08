#!/usr/bin/env bash
set -euo pipefail
dir="${1:-demo}"
shopt -s nullglob
for cast in "$dir"/*.cast; do
  base="${cast%.cast}"
  agg --font-family "DejaVu Sans Mono" --font-size 20 --idle-time-limit 2 --last-frame-duration 4 "$cast" "$base.gif"
  ffmpeg -loglevel error -y -i "$base.gif" -movflags faststart -pix_fmt yuv420p -vf "fps=15,scale=trunc(iw/2)*2:trunc(ih/2)*2" "$base.mp4"
  rm -f "$base.gif"
  echo "$base.mp4"
done
