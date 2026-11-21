#!/usr/bin/env bash
# Builds a beat-synced edit of the wedding-car clips in the style of the reference video.
set -euo pipefail
U=/root/.claude/uploads/292e6acd-7b8c-5914-bde3-b14a5a763d1f
REF=/home/user/Abdulrahman-Belhaj/media/videos/car_edit_reference.mp4
W=/tmp/claude-0/-home-user-Abdulrahman-Belhaj/292e6acd-7b8c-5914-bde3-b14a5a763d1f/scratchpad/build
OUT=${1:-/home/user/Abdulrahman-Belhaj/media/edits/wedding_car_edit.mp4}
mkdir -p "$W" "$(dirname "$OUT")"; rm -f "$W"/s*.mp4

TM="zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
GRADE="eq=contrast=1.18:brightness=-0.07:saturation=0.82:gamma=0.92,curves=all='0/0 0.25/0.15 0.6/0.55 1/0.95',colorbalance=bs=0.06:bm=0.02:bh=-0.02,vignette=PI/4.5"

# idx | file | src start (s) | speed | frames @30fps | extra filters
# Cut points copied from the reference: 0 1.53 2.27 3.9 6.9 7.63 7.83 8.4 9.23 10.7 13.03 14.87 16.0
SHOTS=(
"01|cb812b6e-IMG_0410.mov|0.5|1|46|crop=1080:608:0:816,pad=1080:1920:0:656:black,fade=t=in:start_frame=0:nb_frames=9"
"02|740ad3cf-IMG_0422.mov|0.2|1|22|"
"03|5e9b48b1-IMG_0412.mov|0.5|1|49|"
"04|7fd4336e-IMG_0416.mov|3.0|2|90|"
"05|ec4d48d6-IMG_0413.mov|0.0|1|22|"
"06|c93bb22d-IMG_0415.mov|1.6|1|6|"
"07|42b34156-IMG_0418.mov|0.0|1|17|"
"08|ec4d48d6-IMG_0413.mov|9.0|1|25|"
"09|833fe083-IMG_0421.mov|0.1|1|44|"
"10|13bfd3e2-IMG_0417.mov|0.5|2|70|"
"11|03b39b57-IMG_0424.mov|0.0|0.835|55|"
"12|0de3a406-IMG_0411.mov|5.5|1|34|fade=t=out:start_frame=14:nb_frames=20"
)

: > "$W/list.txt"
for s in "${SHOTS[@]}"; do
  IFS='|' read -r i f ss sp nf extra <<< "$s"
  need=$(awk -v n="$nf" -v sp="$sp" 'BEGIN{printf "%.3f", n/30*sp+0.5}')
  vf="$TM,setpts=(PTS-STARTPTS)/$sp,fps=30,trim=end_frame=$nf,setpts=PTS-STARTPTS,$GRADE"
  [ -n "$extra" ] && vf="$vf,$extra"
  vf="$vf,setsar=1,format=yuv420p"
  ffmpeg -v error -y -ss "$ss" -t "$need" -i "$U/$f" -an -vf "$vf" \
    -c:v libx264 -preset slow -crf 16 -r 30 "$W/s$i.mp4"
  echo "file '$W/s$i.mp4'" >> "$W/list.txt"
done

ffmpeg -v error -y -f concat -safe 0 -i "$W/list.txt" -c copy "$W/video.mp4"
ffmpeg -v error -y -i "$W/video.mp4" -i "$REF" -map 0:v -map 1:a \
  -af "atrim=0:16,afade=t=out:st=15.2:d=0.8" -c:v copy -c:a aac -b:a 192k \
  -shortest -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=duration,size -of compact "$OUT"
