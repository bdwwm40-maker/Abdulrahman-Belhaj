"""Per-frame animated face patches (lip sync, blinks, brows) for the stage.

Inputs : face library (face_rig.py build -> <lib>.npz, crop geometry), build/timeline.js,
         <audio>/phones.json (lipsync.py)
Outputs: build/face/<n>.png  RGBA patches in char.png coordinates (deduplicated)
         build/face.js       window.FACE = {box: [x, y, w, h], frames: [patch id per frame or -1]}

Every frame is composed from the rendered library: the mouth image is interpolated in
the (open, shape) grid and blended towards the lip-closure renders for b/m/f, the eye
image in the (blink, brow) grid. Only the change against the neutral render is added
to the original character pixels, so a neutral frame is exactly the original artwork.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
# char.png = the cutout cropped to this box and resized to 756x2200 (see stage/assets)
CUT_BOX, CHAR_SIZE = (846, 105, 2161, 3934), (756, 2200)

# viseme -> (open 0..100, shape -1 round .. +1 spread, lip closure 0..1)
VIS = {"A": (66, 0.0, 0), "I": (22, 0.8, 0), "U": (24, -0.9, 0), "M": (0, 0.0, 1.0), "F": (4, 0.3, 0.6),
       "W": (14, -1.0, 0), "S": (14, 0.35, 0), "K": (28, 0.0, 0)}


def load_tl():
    s = (ROOT / "build" / "timeline.js").read_text()
    return json.loads(s[s.index("{"):s.rindex("}") + 1])


def grid_lerp(stack, axis_vals, v):
    """Linear interpolation of images along one axis of `stack` (first dim)."""
    v = float(np.clip(v, axis_vals[0], axis_vals[-1]))
    j = int(np.clip(np.searchsorted(axis_vals, v) - 1, 0, len(axis_vals) - 2))
    k = (v - axis_vals[j]) / (axis_vals[j + 1] - axis_vals[j])
    return stack[j] * (1 - k) + stack[j + 1] * k


def masks(lib):
    """Soft region masks (crop space) for the mouth and eye layers from where the renders move."""
    neu = lib["neutral"].astype(np.float32)

    def region(stack):
        # the renders also drift by a pixel or so everywhere (stitching); only the real motion counts
        nb = cv2.GaussianBlur(neu, (0, 0), 2)
        d = np.zeros(neu.shape[:2], np.float32)
        for im in stack.reshape(-1, *neu.shape):
            d = np.maximum(d, np.abs(cv2.GaussianBlur(im.astype(np.float32), (0, 0), 2) - nb).mean(-1))
        m = (d > 12).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        keep = np.zeros_like(m)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] > 300:
                keep[lab == i] = 1
        keep = cv2.dilate(keep, np.ones((11, 11), np.uint8))
        return cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 6)

    return region(np.concatenate([lib["mouth"].reshape(-1, *neu.shape), lib["close"]])), region(lib["eyes"])


def mouth_track(tl, phones, n, fps):
    """Per-frame (open, shape, close) from aligned phones, with coarticulation smoothing."""
    keys = []  # (time, open, shape, close)
    for sc in tl["scenes"]:
        ph = phones.get(sc["id"], [])
        if not ph:
            continue
        t0 = sc["start"]
        keys.append((t0 + ph[0]["t"] - 0.12, 0, 0, 0))
        for i, p in enumerate(ph):
            o, s, c = VIS[p["v"]]
            a, b = t0 + p["t"], t0 + p["e"]
            if p["v"] == "A" and b - a > 0.11:
                o += 14                                     # long / stressed a opens wider
            if c:
                keys += [(a + 0.01, o, s, c), (max(a + 0.02, b - 0.01), o, s, c)]
            else:
                keys.append(((a + b) / 2, o, s, c))
            if i + 1 < len(ph) and ph[i + 1]["t"] - p["e"] > 0.14:  # pause inside the line: rest
                g0, g1 = t0 + p["e"], t0 + ph[i + 1]["t"]
                keys += [(g0 + 0.06, 0, 0, 0), (g1 - 0.06, 0, 0, 0)]
        keys.append((t0 + ph[-1]["e"] + 0.1, 0, 0, 0))
    keys.sort()
    kt = np.array([k[0] for k in keys])
    t = np.arange(n) / fps
    tr = np.stack([np.interp(t, kt, [k[i] for k in keys], left=0, right=0) for i in (1, 2, 3)], 1)
    # coarticulation: light smoothing (keeps closures, softens the vowel peaks)
    ker = np.exp(-0.5 * (np.arange(-3, 4) / 0.9) ** 2)
    ker /= ker.sum()
    for i in range(3):
        tr[:, i] = np.convolve(np.pad(tr[:, i], 3, mode="edge"), ker, mode="valid")
    return tr


def eye_track(tl, n, fps, seed=7):
    """Per-frame (blink, brow): natural blinks, a blink after each line, brows lift on ! and ؟ lines."""
    rng = np.random.default_rng(seed)
    blink = np.zeros(n)
    brow = np.zeros(n)
    shape = np.array([-6, -14, -20, -20, -15, -8, -3])
    times = []
    t = 1.5
    while t < n / fps:
        times.append(t)
        t += rng.uniform(2.4, 4.6)
    times += [sc["end"] + 0.2 for sc in tl["scenes"] if rng.random() < 0.6]
    for bt in sorted(times):
        f = int(bt * fps)
        for i, v in enumerate(shape):
            if 0 <= f + i < n:
                blink[f + i] = min(blink[f + i], v)
    # brows lift on exclamations and questions (caption chunks end with their punctuation)
    for c in tl["captions"]:
        if re.search(r"[!؟?]\s*$", c["text"]):
            a = int(c["t"] * fps)
            for f in range(max(0, a - 6), min(n, a + 30)):
                k = min(1, (f - a + 6) / 8, (a + 30 - f) / 10)
                brow[f] = max(brow[f], 7 * max(0, k))
    return np.stack([blink, brow], 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True, help="face library .npz from face_rig.py")
    ap.add_argument("--audio", default="audio-fusha")
    a = ap.parse_args()

    lib = dict(np.load(a.lib))
    tl = load_tl()
    fps, n = tl["fps"], len(tl["env"])
    phones = json.loads((ROOT / a.audio / "phones.json").read_text())

    neu = lib["neutral"].astype(np.float32)
    mouth = lib["mouth"].astype(np.float32)
    close = np.concatenate([neu[None], lib["close"].astype(np.float32)])
    eyes = lib["eyes"].astype(np.float32)
    OPEN, SHAPE, BLINK, BROW = (lib[k].astype(np.float32) for k in ("OPEN", "SHAPE", "BLINK", "BROW"))
    CLOSE = np.concatenate([[0.0], lib["CLOSE"]]).astype(np.float32)
    mm, me = masks(lib)

    # crop (512) -> cutout -> char.png
    x0, y0, x1, y1 = CUT_BOX
    S = np.array([[CHAR_SIZE[0] / (x1 - x0), 0, -x0 * CHAR_SIZE[0] / (x1 - x0)],
                  [0, CHAR_SIZE[1] / (y1 - y0), -y0 * CHAR_SIZE[1] / (y1 - y0)], [0, 0, 1]])
    A = (S @ lib["M_c2o"])[:2]
    reg = cv2.warpAffine(np.maximum(mm, me), A, CHAR_SIZE)
    ys, xs = np.nonzero(reg > 0.01)
    bx, by = int(xs.min()) - 2, int(ys.min()) - 2
    bw, bh = int(xs.max()) + 3 - bx, int(ys.max()) + 3 - by
    Ab = A.copy()
    Ab[:, 2] -= (bx, by)
    char = np.array(Image.open(ROOT / "stage" / "assets" / "char.png").convert("RGBA")).astype(np.float32)
    base = char[by:by + bh, bx:bx + bw]

    mtr = mouth_track(tl, phones, n, fps)
    etr = eye_track(tl, n, fps)
    env = np.array(tl["env"])
    mtr[:, 0] *= np.clip(0.65 + 0.55 * env, 0.65, 1.15)     # louder syllables open wider

    out = ROOT / "build" / "face"
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.png"):
        p.unlink()
    ids, seen = [], {}
    for f in range(n):
        o, s, c = mtr[f]
        b, w = etr[f]
        key = (round(o / 2), round(s * 20), round(c * 20), round(b), round(w * 2))
        if key not in seen:
            m = grid_lerp(np.stack([grid_lerp(mouth[i], SHAPE, s) for i in range(len(OPEN))]), OPEN, o) if o > 0.5 or abs(s) > 0.02 else neu
            if c > 0.01:
                m = m + (grid_lerp(close, CLOSE, c) - m) * min(1.0, c / 0.35)
            e = grid_lerp(np.stack([grid_lerp(eyes[i], BROW, w) for i in range(len(BLINK))]), -BLINK, -b) \
                if (b < -0.5 or w > 0.2) else neu
            delta = (m - neu) * mm[..., None] + (e - neu) * me[..., None]
            # small changes shift the original pixels; where the face changes a lot (closed lids,
            # open mouth) the render itself is shown, or the old iris / teeth edges would shine through
            wt = np.clip((cv2.GaussianBlur(np.abs(delta).mean(-1), (0, 0), 8) - 3) / 8, 0, 1)
            warp = lambda x: cv2.warpAffine(x, Ab, (bw, bh), flags=cv2.INTER_LINEAR)
            d = warp(cv2.GaussianBlur(delta, (0, 0), 0.6))
            r = warp(cv2.GaussianBlur(neu + delta, (0, 0), 0.6))
            wt = warp(wt)[..., None]
            rgb = np.clip((1 - wt) * (base[..., :3] + d) + wt * r, 0, 255)
            patch = np.dstack([rgb, base[..., 3:]]).astype(np.uint8)
            seen[key] = len(seen)
            Image.fromarray(patch).save(out / f"{seen[key]}.png", optimize=False, compress_level=3)
        ids.append(seen[key])
        if f % 300 == 0:
            print(f"frame {f}/{n}  unique {len(seen)}", flush=True)
    (ROOT / "build" / "face.js").write_text("window.FACE = " + json.dumps({"box": [bx, by, bw, bh], "frames": ids}) + ";\n")
    print(f"{n} frames, {len(seen)} unique patches, box {bx},{by} {bw}x{bh}")


if __name__ == "__main__":
    main()
