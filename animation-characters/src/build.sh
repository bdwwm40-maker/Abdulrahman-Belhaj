#!/usr/bin/env bash
# Rebuild everything: SVGs -> stills/PNGs -> animation frames -> videos.
# Needs python3 (Pillow, numpy), node with playwright + chromium, and ffmpeg.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
BUILD="$ROOT/build"
FPS=30
LOOP_FRAMES=$((4 * FPS))   # every animation is a seamless 4 s loop
CHARS=(ahmed mariam yousef sara)
POSES=(idle wave talk point-right point-left)

python3 "$HERE/generate.py"
node "$HERE/render.mjs" stills "$BUILD/stills" 2
python3 "$HERE/finish.py" "$BUILD/stills"
node "$HERE/render.mjs" frames "$BUILD/frames" "$FPS"

mkdir -p "$ROOT/videos/greenscreen" "$ROOT/videos/transparent-webm" "$ROOT/videos/gif"
encode() {
    local c=$1 p=$2
    local in="$BUILD/frames/$c/$p/%04d.png"
    # MP4 on pure green (#00FF00), two loops = 8 s
    ffmpeg -y -v error -framerate $FPS -i "$in" -f lavfi -i "color=c=0x00FF00:s=1080x1350:r=$FPS" \
      -filter_complex "[0]loop=loop=1:size=$LOOP_FRAMES:start=0[c];[1][c]overlay=shortest=1,format=yuv420p" \
      -c:v libx264 -crf 18 -preset slow -movflags +faststart "$ROOT/videos/greenscreen/${c}_${p}.mp4"
    # WebM VP9 with a real alpha channel, two loops = 8 s
    ffmpeg -y -v error -framerate $FPS -i "$in" -vf "loop=loop=1:size=$LOOP_FRAMES:start=0" \
      -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 32 -row-mt 1 -deadline good -cpu-used 4 \
      "$ROOT/videos/transparent-webm/${c}_${p}.webm"
    # transparent GIF (half size, 15 fps) for slides / messaging apps
    ffmpeg -y -v error -framerate $FPS -i "$in" \
      -vf "fps=15,scale=540:-1:flags=lanczos,split[a][b];[a]palettegen=reserve_transparent=1:stats_mode=diff[pl];[b][pl]paletteuse=alpha_threshold=128:dither=none" \
      -loop 0 "$ROOT/videos/gif/${c}_${p}.gif"
    echo "encoded ${c}_${p}"
}
for c in "${CHARS[@]}"; do
  for p in "${POSES[@]}"; do encode "$c" "$p" & done
  wait
done
