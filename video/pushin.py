"""Cinematic push-in on a still photo: pure geometric crop/scale of the original pixels, no generation."""
import subprocess, sys
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
img = Image.open(src).convert("RGB")
IW, IH = img.size                      # 1280x960
OW, OH, FPS, DUR, HOLD = 1920, 1080, 60, 10.0, 1.0

# Start: full-width 16:9 window centred on the building. End: ~1.22x, centred on the main entrance.
start = dict(cx=640.0, cy=480.0, w=1280.0)
end = dict(cx=690.0, cy=472.0, w=1280.0 / 1.22)

def ease(t):  # smootherstep: gentle start, calm stop
    return t * t * t * (t * (t * 6 - 15) + 10)

ff = subprocess.Popen([
    "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-movflags", "+faststart", out], stdin=subprocess.PIPE)

n = int(FPS * DUR)
for i in range(n):
    t = i / FPS
    k = 0.0 if t <= HOLD else ease((t - HOLD) / (DUR - HOLD))
    cx = start["cx"] + (end["cx"] - start["cx"]) * k
    cy = start["cy"] + (end["cy"] - start["cy"]) * k
    w = start["w"] + (end["w"] - start["w"]) * k
    h = w * OH / OW
    s = w / OW                                   # source px per output px (uniform -> no stretching)
    x0, y0 = cx - w / 2, cy - h / 2
    assert x0 >= 0 and y0 >= 0 and x0 + w <= IW and y0 + h <= IH
    frame = img.transform((OW, OH), Image.AFFINE, (s, 0, x0, 0, s, y0), resample=Image.BICUBIC)
    ff.stdin.write(frame.tobytes())
ff.stdin.close()
sys.exit(ff.wait())
