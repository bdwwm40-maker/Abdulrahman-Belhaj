#!/usr/bin/env bash
# Mux the rendered frames with the narration and a quiet music bed.
#   tools/mix.sh [music_volume]   (default 0.10; pass 0 for voice only)
# The voice is cleaned (high-pass, gentle compression) and normalised to -16 LUFS;
# the bed is low-passed and ducks under the voice through a sidechain compressor.
set -euo pipefail
cd "$(dirname "$0")/.."
MUSIC_VOL="${1:-0.10}"
OUT="${2:-final/youth-future-ajaylat.mp4}"
mkdir -p "$(dirname "$OUT")"
# the video sets the length; loudnorm/sidechain can drop a few seconds of tail, so pad then cut
DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 build/frames.mp4)

ffmpeg -y -loglevel error -i build/frames.mp4 -i build/voice.wav -i build/music.wav -filter_complex "
[1:a]aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=75,
     acompressor=threshold=-20dB:ratio=2.5:attack=5:release=150:makeup=2,
     loudnorm=I=-16:TP=-1.5:LRA=9,asplit=2[voice][key];
[2:a]aformat=sample_rates=48000:channel_layouts=stereo,lowpass=f=4500,volume=${MUSIC_VOL}[bed];
[bed][key]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=500[duck];
[voice][duck]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.89,apad[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -movflags +faststart -t "$DUR" "$OUT"
echo "wrote $OUT"
