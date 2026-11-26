#!/usr/bin/env bash
# Apply the "Dark Cinematic Car Reel" look to an already-cut clip.
# Usage: ./apply.sh input.mp4 output.mp4
set -euo pipefail
IN="$1"; OUT="$2"
ffmpeg -y -i "$IN" -filter_complex "
[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,
eq=brightness=-0.06:contrast=1.2:gamma=0.9,
hue=s=0.25,
colorbalance=bs=0.05:bm=0.02,
vignette=PI/5,
drawbox=x=0:y=0:w=iw:h=560:color=black:t=fill:enable='between(t,0.35,1.53)',
drawbox=x=0:y=1360:w=iw:h=560:color=black:t=fill:enable='between(t,0.35,1.53)',
format=yuv420p[v];
[0:a]loudnorm=I=-14:TP=-1:LRA=4[a]" \
-map "[v]" -map "[a]" -c:v libx264 -profile:v high -preset slow -crf 18 -c:a aac -b:a 192k -ar 44100 -movflags +faststart "$OUT"
# Note: hue=s=0.25 desaturates all colors; to keep the reds, do the HSL step in your editor (CapCut / Premiere / DaVinci).
