#!/usr/bin/env python3
"""Turn each still photo into a short video clip (2.5D parallax).

For every photo:
  1. the subject (car / wheel / dashboard) is cut out with rembg,
  2. the hole it leaves in the background is inpainted,
  3. the two layers move at different speeds and scales (camera parallax),
  4. headlights / taillights / red details get a slow glowing pulse.
Clips keep the photo's aspect ratio so the montage can still crop 9:16
details from them.

Usage:
  python3 photo_to_clip.py out_dir photo1.jpg photo2.jpg ... [--dur 4] [--fps 30]
"""
import argparse, os, subprocess, sys
import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

MOVES = [  # (direction of travel, push-in amount): varies the camera per clip
    (1, 0.06), (-1, 0.05), (1, 0.04), (-1, 0.07), (1, 0.05), (-1, 0.04),
]


def subject_mask(img_rgb, session):
    a = np.array(remove(Image.fromarray(img_rgb), session=session, only_mask=True))
    a = cv2.GaussianBlur(a, (0, 0), 2).astype(np.float32) / 255.0
    return a


def clean_plate(img, mask):
    """Background with the subject removed (inpainted at low res, then upscaled)."""
    h, w = mask.shape
    sc = 0.25
    small = cv2.resize(img, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
    m = cv2.resize((mask > 0.1).astype(np.uint8) * 255, (small.shape[1], small.shape[0]))
    m = cv2.dilate(m, np.ones((9, 9), np.uint8))
    filled = cv2.inpaint(small, m, 7, cv2.INPAINT_TELEA)
    filled = cv2.GaussianBlur(cv2.resize(filled, (w, h), interpolation=cv2.INTER_CUBIC), (0, 0), 3)
    hard = cv2.dilate((mask > 0.1).astype(np.uint8), np.ones((25, 25), np.uint8))[..., None]
    return np.where(hard > 0, filled, img)


def light_mask(img, mask):
    """Bright lights and saturated reds on the subject -> glow layer."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = (((hue < 8) | (hue > 170)) & (sat > 120) & (val > 110)).astype(np.float32)
    bright = ((val > 235) & (sat < 60)).astype(np.float32)
    lm = np.clip(red * 0.8 + bright, 0, 1) * (mask > 0.3)
    glow = img.astype(np.float32) * lm[..., None]
    return cv2.GaussianBlur(glow, (0, 0), max(img.shape[:2]) / 90)


def transform(layer, scale, dx, w, h):
    M = np.float32([[scale, 0, (1 - scale) * w / 2 + dx], [0, scale, (1 - scale) * h / 2]])
    return cv2.warpAffine(layer, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def make_clip(path, out, session, idx, dur, fps):
    img = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    w, h = w // 2 * 2, h // 2 * 2
    img = img[:h, :w]
    mask = subject_mask(img, session)
    cover = float((mask > 0.5).mean())
    parallax = 0.03 < cover < 0.75  # skip parallax when the cut-out is useless
    bg = clean_plate(img, mask) if parallax else img
    glow = light_mask(img, mask)
    direction, push = MOVES[idx % len(MOVES)]
    n = int(dur * fps)
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "14",
         "-preset", "medium", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    fg = img.astype(np.float32)
    bgf = bg.astype(np.float32)
    for f in range(n):
        p = f / max(1, n - 1)
        e = p * p * (3 - 2 * p)  # ease in-out
        if parallax:
            b = transform(bgf, 1.02 + push * 0.3 * e, direction * w * 0.008 * (e - 0.5), w, h)
            s_fg = 1.02 + push * e
            dx_fg = direction * w * 0.022 * (e - 0.5)
            a = transform(mask, s_fg, dx_fg, w, h)[..., None]
            c = transform(fg, s_fg, dx_fg, w, h)
            g = transform(glow, s_fg, dx_fg, w, h)
            frame = c * a + b * (1 - a)
        else:
            s = 1.02 + push * e
            dx = direction * w * 0.02 * (e - 0.5)
            frame = transform(fg, s, dx, w, h)
            g = transform(glow, s, dx, w, h)
        pulse = 0.35 + 0.35 * (0.5 - 0.5 * np.cos(2 * np.pi * p * 1.5))
        frame = np.clip(frame + g * pulse, 0, 255).astype(np.uint8)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    return cover, parallax


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("photos", nargs="+")
    ap.add_argument("--dur", type=float, default=4.0)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    session = new_session("isnet-general-use")
    for i, p in enumerate(a.photos):
        out = os.path.join(a.out_dir, os.path.splitext(os.path.basename(p))[0] + ".mp4")
        cover, par = make_clip(p, out, session, i, a.dur, a.fps)
        print(f"{out}  subject={cover:.0%}  parallax={'yes' if par else 'no'}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
