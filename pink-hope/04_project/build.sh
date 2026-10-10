#!/usr/bin/env bash
# PINK HOPE — full rebuild from the original footage.
# Requires: ffmpeg/ffprobe (libx264), python3 with numpy, pillow (raqm), opencv-python-headless.
set -euo pipefail
cd "$(dirname "$0")"
EXP=../05_export
mkdir -p "$EXP" ../06_qc

python3 audio.py                                  # 03_audio/mix.wav (+ stems)
python3 render.py vertical   --stills             # build/video_vertical.mp4
python3 render.py horizontal --stills             # build/video_horizontal.mp4

mux () {  # $1 video  $2 output
  ffmpeg -v error -y -i "$1" -i ../03_audio/mix.wav -map 0:v -map 1:a \
    -c:v copy -c:a aac -b:a 192k -ar 44100 -shortest -movflags +faststart "$2"
}
mux build/video_vertical.mp4   "$EXP/PinkHope_9x16_1080x1920.mp4"
mux build/video_horizontal.mp4 "$EXP/PinkHope_16x9_1920x1080.mp4"

# lightweight review copy (WhatsApp / quick approval)
ffmpeg -v error -y -i "$EXP/PinkHope_9x16_1080x1920.mp4" -vf scale=540:960:flags=lanczos \
  -c:v libx264 -preset slow -crf 27 -c:a aac -b:a 96k -movflags +faststart "$EXP/PinkHope_review_540x960.mp4"
echo "exports:"; ls -lh "$EXP"

# ---- v2: beat-synced edit in the style of the supplied reference video
python3 audio_v2.py                               # 03_audio/mix_v2.wav
python3 render_v2.py --stills                     # build/video_v2.mp4
mux2 () { ffmpeg -v error -y -i build/video_v2.mp4 -i ../03_audio/mix_v2.wav -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k -ar 44100 -shortest -movflags +faststart "$1"; }
mux2 "$EXP/PinkHope_v2_Reels_9x16_1080x1920.mp4"
ffmpeg -v error -y -i "$EXP/PinkHope_v2_Reels_9x16_1080x1920.mp4" -vf scale=540:960:flags=lanczos \
  -c:v libx264 -preset slow -crf 27 -c:a aac -b:a 96k -movflags +faststart "$EXP/PinkHope_v2_review_540x960.mp4"
ls -lh "$EXP"
