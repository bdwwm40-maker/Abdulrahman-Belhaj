#!/usr/bin/env bash
# Apply the "Dark Cinematic Car Reel" look to an already-cut clip.
# Usage: ./apply.sh input.mp4 output.mp4
set -euo pipefail
IN="$1"; OUT="$2"
ffmpeg -y -i "$IN" -filter_complex "
[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,
eq=brightness=-0.06:contrast=1.2:gamma=0.9,
hue=s=0.25,
colorbalance=bs=0.05:ms=0.02,
vignette=PI/5,
drawbox=x=0:y=0:w=iw:h='if(lt(t,0.35),t/0.35*700,if(lt(t,1.15),700,if(lt(t,1.53),700*(1.53-t)/0.38,0)))':color=black:t=fill,
drawbox=x=0:y='ih-if(lt(t,0.35),t/0.35*700,if(lt(t,1.15),700,if(lt(t,1.53),700*(1.53-t)/0.38,0)))':w=iw:h=700:color=black:t=fill,
format=yuv420p[v];
[0:a]loudnorm=I=-14:TP=-1:LRA=4[a]" \
-map "[v]" -map "[a]" -c:v libx264 -profile:v high -preset slow -crf 18 -c:a aac -b:a 192k -ar 44100 -movflags +faststart "$OUT"
# Note: hue=s=0.25 desaturates all colors; to keep the reds, do the HSL step in your editor (CapCut / Premiere / DaVinci).
