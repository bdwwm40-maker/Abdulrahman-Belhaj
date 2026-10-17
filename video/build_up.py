"""Build-up animation: the building drops in block by block onto an empty lot and
locks into place. Every block is cut from the original photo and lands on its exact
original position, so the final frames are the untouched photo."""
import random, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter

src, out = sys.argv[1], sys.argv[2]
img = Image.open(src).convert("RGB")
IW, IH = img.size
A = np.asarray(img).astype(np.int16)
OW, OH, FPS, DUR = 1920, 1080, 60, 10.0
HORIZON = 528

# Structure regions measured on the 1280x960 source (x0, y0, x1, y1).
RECTS = [
    (0, 428, 590, 548),      # canopy + lower left block
    (155, 342, 590, 548),    # arched left block
    (588, 355, 681, 528),    # tower
    (598, 421, 812, 528),    # entrance + sign
    (810, 423, 1226, 528),   # right wing
    (754, 399, 1056, 425),   # rooftop structure
    (734, 401, 754, 423), (833, 407, 853, 428),  # water tanks
    (962, 385, 970, 400),    # antenna
    (530, 396, 544, 430),    # lamp post
]
mask = np.zeros((IH, IW), bool)
for x0, y0, x1, y1 in RECTS:
    mask[y0:y1, x0:x1] = True
# Leave clear blue sky that falls inside a rectangle as background.
r, g, b = A[..., 0], A[..., 1], A[..., 2]
mask &= ~((b > r + 25) & (b > g) & (np.arange(IH)[:, None] < 440))
# Grow slightly so no anti-aliased roof edge is left behind on the empty sky.
mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))) > 0

# Empty-lot plate (shown only while the building is missing): the sky from higher up in the
# same photo, shifted down behind the building, hazing toward the horizon; pavement below.
Af = A.astype(np.float32)
yy = np.arange(IH)[:, None]
haze = Af[395:410, 1080:1200].reshape(-1, 3).mean(0)

def blur(a, r):
    return np.asarray(Image.fromarray(a.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)),
                      np.float32)

# Smooth membrane fill from the surrounding sky (seamless), horizon edge held at a pale haze.
sky_hole = mask & (yy < HORIZON)
known = Af.copy()
known[(yy >= HORIZON) & mask.any(0)[None, :]] = haze
S = 4
small = known[::S, ::S].copy()
hole = sky_hole[::S, ::S]
small[hole] = haze
for _ in range(1500):
    p = np.pad(small, ((1, 1), (1, 1), (0, 0)), mode="edge")
    avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
    small[hole] = avg[hole]
membrane = np.asarray(Image.fromarray(small.clip(0, 255).astype(np.uint8)).resize((IW, IH), Image.BICUBIC),
                      np.float32)
# Cloud texture: high-frequency detail of the sky higher up in the same photo.
shifted = np.roll(Af, 220, axis=0)
detail = shifted - blur(shifted, 8)
filled = membrane + detail * 0.7
ground = np.roll(Af, -60, axis=0)  # sunlit pavement from below the curb
filled = np.where(yy[..., None] >= HORIZON, ground, filled)
plate = np.where(mask[..., None], filled, Af)
plate_img = Image.fromarray(plate.clip(0, 255).astype(np.uint8))

# Cut blocks from the original.
TW, TH = 64, 30
my, mx = np.nonzero(mask)
X0, Y0, X1, Y1 = mx.min(), my.min(), mx.max() + 1, my.max() + 1
blocks = []
for by in range(Y1, Y0, -TH):                # bottom row first
    row = []
    for bx in range(X0, X1, TW):
        x0, y0, x1, y1 = bx, max(by - TH, Y0), min(bx + TW, X1), by
        m = mask[y0:y1, x0:x1]
        if m.any():
            tile = img.crop((x0, y0, x1, y1))
            alpha = Image.fromarray((m * 255).astype(np.uint8))
            row.append((x0, y0, tile, alpha))
    random.Random(by).shuffle(row)
    blocks += row

random.seed(7)
START, END, FALL = 0.8, 7.4, 0.6
for i, blk in enumerate(blocks):
    t0 = START + (END - START) * i / max(len(blocks) - 1, 1) + random.uniform(-0.08, 0.08)
    drop = blk[1] + random.uniform(260, 420)  # start above the frame top
    blocks[i] = blk + (t0, drop)

def land(p):  # gravity fall with a small settle bounce
    if p < 0.8:
        q = p / 0.8
        return q * q
    q = (p - 0.8) / 0.2
    return 1 - 0.035 * np.sin(np.pi * q)

def ease(t):
    return t * t * t * (t * (t * 6 - 15) + 10)

cam0 = dict(cx=640.0, cy=480.0, w=1280.0)
cam1 = dict(cx=690.0, cy=470.0, w=1280.0 / 1.12)

ff = subprocess.Popen([
    "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
    "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-movflags", "+faststart", out], stdin=subprocess.PIPE)

for i in range(int(FPS * DUR)):
    t = i / FPS
    frame = plate_img.copy()
    for x0, y0, tile, alpha, t0, drop in blocks:
        if t < t0:
            continue
        p = min((t - t0) / FALL, 1.0)
        y = y0 if p >= 1 else round(y0 - drop * (1 - land(p)))
        frame.paste(tile, (x0, y), alpha)
    k = ease(t / DUR)
    cx = cam0["cx"] + (cam1["cx"] - cam0["cx"]) * k
    cy = cam0["cy"] + (cam1["cy"] - cam0["cy"]) * k
    w = cam0["w"] + (cam1["w"] - cam0["w"]) * k
    s = w / OW
    x0, y0 = cx - w / 2, cy - w * OH / OW / 2
    out_f = frame.transform((OW, OH), Image.AFFINE, (s, 0, x0, 0, s, y0), resample=Image.BICUBIC)
    ff.stdin.write(out_f.tobytes())
    if i == int(FPS * DUR) - 1:
        assert np.array_equal(np.asarray(frame), np.asarray(img)), "final frame differs from source"
ff.stdin.close()
sys.exit(ff.wait())
