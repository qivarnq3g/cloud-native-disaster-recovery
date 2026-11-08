#!/usr/bin/env bash
set -euo pipefail
dir="${1:-demo}"
shopt -s nullglob
for cast in "$dir"/*.cast; do
  base="${cast%.cast}"
  agg --font-family "Noto Sans Mono,Noto Mono" --font-size 44 --theme dracula --idle-time-limit 5 --last-frame-duration 10 "$cast" "$base.gif"
  ffmpeg -loglevel error -y -i "$base.gif" -movflags faststart -pix_fmt yuv420p -c:v libx264 -preset slow -crf 20 -r 30 -vf "scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=0x282a36,setsar=1" "$base.mp4"
  rm -f "$base.gif"
  echo "$base.mp4"
done
