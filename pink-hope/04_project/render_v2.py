#!/usr/bin/env python3
"""PINK HOPE v2 — beat-synced hyper-edit in the style of the supplied reference.

Transitions: whip pans (directional motion blur), camera rolls, zoom punches with
impact shake, light flashes, a circle reveal opening from the pink balloon,
neon "lights-on" flicker for poster 2, speed ramp into true 120 fps slow motion,
letter-by-letter typing and word-by-word Arabic kinetic text.

Usage: python3 render_v2.py [--stills]   ->  build/video_v2.mp4 (no audio)
"""
import json, os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "02_assets", "fonts")
LOGOS = os.environ.get("PINKHOPE_LOGOS", os.path.join(ROOT, "02_assets", "logos"))
BUILD = os.path.join(HERE, "build")
os.makedirs(BUILD, exist_ok=True)
E = json.load(open(os.path.join(HERE, "edit_v2.json"), encoding="utf-8"))
FPS = E["fps"]
BEAT = 60.0 / E["bpm"]
SRC = os.path.normpath(os.path.join(HERE, E["source_dir"]))
STILLS = "--stills" in sys.argv
W, H = 1080, 1920
WHITE, PINK, PINK_DEEP, PLUM, PLUM_SOFT = (255, 255, 255), (255, 92, 160), (214, 59, 120), (61, 24, 48), (107, 69, 96)
TR = 4  # frames each side of a cut used by whip / roll / punch / flash
CIRCLE = 9  # frames of the balloon circle reveal (overlap)
rng = np.random.default_rng(3)


def font(weight, size):
    return ImageFont.truetype(os.path.join(FONTS, f"Tajawal-{weight}.ttf"), size, layout_engine=ImageFont.Layout.RAQM)


def smooth(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0); return 1 - (1 - x) ** 3


def ease_in(x):
    x = min(max(x, 0.0), 1.0); return x ** 2.2


# ---------------------------------------------------------------- timeline
shots = E["shots"]
for i, s in enumerate(shots):
    s["start"] = s["b"] * BEAT
    s["dur"] = s["len"] * BEAT
    s["tr"] = s.get("tr", "cut")
for i, s in enumerate(shots):
    nxt = shots[i + 1] if i + 1 < len(shots) else None
    s["out_tr"] = nxt["tr"] if nxt else "card"
    s["ext"] = CIRCLE / FPS if (nxt and nxt["tr"] == "circle") else 0.0
CARD_START = E["card"]["b"] * BEAT
TOTAL = CARD_START + E["card"]["len"] * BEAT
NFR = int(round(TOTAL * FPS))
shots[-1]["ext"] = 6 / FPS  # last shot keeps running under the card's flash-in


# ---------------------------------------------------------------- decoding with time remap
class Reader:
    def __init__(self, s):
        slow = s.get("slowmo", 1.0)
        vf = ([f"setpts=PTS*{slow}"] if slow != 1 else []) + [
            f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={W}:{H}",
            "unsharp=5:5:0.55:5:5:0",
            # punchier look than v1, like the reference: more contrast + saturation, warm
            "eq=brightness=0.01:contrast=1.12:saturation=1.20",
            "colorbalance=rs=0.03:gs=-0.015:bs=-0.02:rm=0.02:gm=-0.02:bm=0.0:rh=0.03:gh=0.0:bh=0.01",
            f"fps={FPS}", "format=rgb24"]
        need = (s["dur"] + s["ext"]) * 4 + 0.5 if s.get("ramp") else (s["dur"] + s["ext"]) / slow + 0.3
        cmd = ["ffmpeg", "-v", "error", "-ss", f"{s['in']}", "-t", f"{need}", "-i", os.path.join(SRC, s["src"]),
               "-an", "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.idx, self.last = -1, None

    def get(self, idx):
        while self.idx < idx:
            buf = self.p.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            self.last = np.frombuffer(buf, np.uint8).reshape(H, W, 3); self.idx += 1
        if self.last is None:
            raise RuntimeError("no frames")
        return self.last

    def close(self):
        self.p.stdout.close(); self.p.wait()


def src_index(s, lt):
    """Output local time -> decoded-stream frame index (supports speed ramps)."""
    if not s.get("ramp"):
        return int(round(lt * FPS))
    idx, t0 = 0.0, 0.0
    for seg_dur, rate in s["ramp"]:
        d = min(seg_dur, max(0.0, lt - t0))
        idx += d * FPS * rate; t0 += seg_dur
        if lt <= t0:
            break
    return int(round(idx))


# ---------------------------------------------------------------- per-shot geometry
def pink_center(img):
    """Centroid of saturated pink pixels (the balloon) — focus point for push-in and circle."""
    sm = cv2.resize(img, (W // 8, H // 8)).astype(np.int16)
    r, g, b = sm[..., 0], sm[..., 1], sm[..., 2]
    m = (r > 170) & (g < 140) & (b > 110) & (r - g > 70)
    if m.sum() < 6:
        return W / 2, H / 2, 60
    ys, xs = np.nonzero(m)
    return xs.mean() * 8, ys.mean() * 8, max(40, np.sqrt(m.sum() / np.pi) * 8)


def cover_scale(deg):
    t = np.radians(abs(deg))
    return np.cos(t) + (H / W) * np.sin(t)


def transform(img, s, lt, extra_zoom=1.0, extra_rot=0.0, dx=0.0, dy=0.0):
    k = lt / s["dur"]
    k = ease_in(k) if s.get("ease") == "in" else smooth(k)
    z0, z1 = s["zoom"]
    z = (z0 + (z1 - z0) * k) * extra_zoom
    r0, r1 = s.get("rot", [0, 0])
    rot = r0 + (r1 - r0) * k + extra_rot
    z = max(z, cover_scale(rot))
    cx, cy = (s["focus_xy"] if "focus_xy" in s else (W / 2, H / 2))
    px, py = s.get("pan", [0, 0])
    M = cv2.getRotationMatrix2D((cx, cy), rot, z)
    # keep the focus point drifting toward the centre as we push in
    M[0, 2] += (W / 2 - cx) * (z - 1) / max(z, 1e-6) * 0.6 + px * W * k + dx
    M[1, 2] += (H / 2 - cy) * (z - 1) / max(z, 1e-6) * 0.6 + py * H * k + dy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def motion_blur(img, length, vertical=False):
    L = int(length)
    if L < 3:
        return img
    k = np.ones((1, L), np.float32) / L
    if vertical:
        k = k.T
    small = cv2.resize(img, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    small = cv2.filter2D(small, -1, k if not vertical else k, borderType=cv2.BORDER_REFLECT)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)


# ---------------------------------------------------------------- look
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
VIGNETTE = (1 - 0.28 * np.clip((rr - 0.5) / 0.9, 0, 1) ** 1.5)[..., None]


def bloom(img, amt, thr=0.62):
    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    lum = small.mean(axis=2, keepdims=True)
    hl = small * np.clip((lum - thr) / (1 - thr), 0, 1)
    g = cv2.resize(cv2.GaussianBlur(hl, (0, 0), 9), (W, H))
    return 1 - (1 - img) * (1 - amt * g)


def look(img, extra_bloom=0.0):
    img = bloom(img, 0.24 + extra_bloom)
    img = 0.012 + 0.988 * (img / (1 + 0.12 * img)) * 1.12
    return np.clip(img * VIGNETTE, 0, 1)


# ---------------------------------------------------------------- text sprites
def sprite(txt, f, color, shadow=0.6, latin=False, glow=None):
    pad = 50
    kw = {} if latin else dict(direction="rtl", language="ar")
    tw = f.getlength(txt, **kw)
    asc, desc = f.getmetrics()
    mask = Image.new("L", (int(tw) + 2 * pad, asc + desc + 2 * pad), 0)
    ImageDraw.Draw(mask).text((pad, pad), txt, font=f, fill=255, **kw)
    m = np.asarray(mask, np.float32) / 255
    rgb = np.broadcast_to(np.float32(color) / 255, m.shape + (3,))
    a = m.copy()
    out = rgb * m[..., None]
    if glow is not None:  # coloured halo (neon-like) for the typing effect
        gl = np.asarray(mask.filter(ImageFilter.GaussianBlur(14)), np.float32) / 255 * 0.9
        out = out + np.float32(glow) / 255 * (gl * (1 - m))[..., None]
        a = m + gl * (1 - m)
    if shadow:
        sh = np.roll(np.asarray(mask.filter(ImageFilter.GaussianBlur(10)), np.float32) / 255 * shadow, 5, axis=0)
        a2 = a + sh * (1 - a)
        out = out  # shadow is black: colour unchanged, alpha grows
        a = a2
    rgb_out = out / np.maximum(a, 1e-6)[..., None]
    return np.dstack([rgb_out, a]).astype(np.float32)


def over(dst, spr, cx, cy, alpha, scale=1.0):
    if alpha <= 0.003:
        return
    if abs(scale - 1) > 1e-3:
        spr = cv2.resize(spr, (max(1, int(spr.shape[1] * scale)), max(1, int(spr.shape[0] * scale))), interpolation=cv2.INTER_LINEAR)
    h, w = spr.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb:
        return
    s = spr[ya - y0:yb - y0, xa - x0:xb - x0]
    a = s[..., 3:4] * alpha
    dst[ya:yb, xa:xb] = dst[ya:yb, xa:xb] * (1 - a) + s[..., :3] * a


class KineticLine:
    """Word-by-word Arabic line(s); words laid out right-to-left, each pops in on its beat."""

    def __init__(self, g, on_card=False):
        size = g.get("size", 104 if not on_card else 100)
        dark = g.get("dark", False)
        base = PLUM_SOFT if g.get("soft") else (PLUM if dark else WHITE)
        hl = PINK_DEEP if dark else PINK
        f = font(900 if size >= 90 else 700, size)
        sp = f.getlength(" ", direction="rtl", language="ar") + size * 0.2
        self.until = g["until"] * BEAT
        self.items = []
        lh = size * 1.3
        n = len(g["lines"])
        for li, line in enumerate(g["lines"]):
            sprs = [sprite(w[0], f, hl if (len(w) > 2 and w[2] == "hl") else base, shadow=0 if dark else 0.65) for w in line]
            widths = [f.getlength(w[0], direction="rtl", language="ar") for w in line]
            total = sum(widths) + sp * (len(line) - 1)
            x = W / 2 + total / 2  # first word starts at the right edge
            y = g["y"] - (n - 1) * lh / 2 + li * lh
            for (w, spr, wd) in zip(line, sprs, widths):
                self.items.append(dict(spr=spr, cx=x - wd / 2, cy=y, t=w[1] * BEAT))
                x -= wd + sp

    def draw(self, img, tt):
        if tt > self.until + 0.2 or tt < min(i["t"] for i in self.items) - 0.05:
            return 0.0
        out = 1 - smooth((tt - self.until) / 0.12)
        vis = 0.0
        for it in self.items:
            k = (tt - it["t"]) / 0.16
            if k < 0:
                continue
            a = ease_out(k) * out
            sc = 1.0 + 0.45 * (1 - ease_out(k)) + 0.08 * (1 - out)
            over(img, it["spr"], it["cx"], it["cy"] - (1 - ease_out(k)) * 10, a, sc)
            vis = max(vis, a)
        return vis


class Typing:
    """Letter-by-letter reveal (like the reference's sign lettering)."""

    def __init__(self, g):
        on_card = g["where"] == "card"
        f = font(900, g["size"])
        self.letters = []
        col = PINK_DEEP if on_card else WHITE
        glow = None if on_card else PINK
        track = g["size"] * 0.12
        widths = [f.getlength(c) for c in g["text"]]
        total = sum(widths) + track * (len(widths) - 1)
        x = W / 2 - total / 2
        t = g["b"] * BEAT
        for c, wd in zip(g["text"], widths):
            if c != " ":
                self.letters.append(dict(spr=sprite(c, f, col, shadow=0 if on_card else 0.5, latin=True, glow=glow),
                                         cx=x + wd / 2, t=t))
                t += g["step"] * BEAT
            x += wd + track
        self.y = g["y"]
        self.where = g["where"]
        self.t_end = g["until"] * BEAT if "until" in g else (CARD_START if not on_card else TOTAL)

    def draw(self, img, tt):
        for l in self.letters:
            k = (tt - l["t"]) / 0.1
            if k < 0 or tt > self.t_end:
                continue
            a = min(1.0, k) * (1 - smooth((tt - (self.t_end - 0.15)) / 0.15) if self.where == "film" else 1)
            flick = 0.55 if 0.0 <= k < 1.6 and int(k * 3) % 2 == 1 else 1.0  # tiny neon flicker on arrival
            over(img, l["spr"], l["cx"], self.y, a * flick, 1.0 + 0.25 * (1 - min(1, k)))


film_text = [KineticLine(g) for g in E["words"]]
card_text = [KineticLine(g, on_card=True) for g in E["card_words"]]
typing = [Typing(g) for g in E["typing"]]
film_typing = [t_ for t_ in typing if t_.where == "film"]
card_typing = [t_ for t_ in typing if t_.where == "card"]
g_ = np.clip((np.arange(H, dtype=np.float32) - 900) / 760, 0, 1) ** 1.3
GRAD = (g_ * 0.62)[:, None, None]

# card background
k_ = (yy / H)[..., None]
CARD_BG = (np.float32([255, 247, 250]) / 255 * (1 - k_) + np.float32([249, 221, 233]) / 255 * k_).astype(np.float32)
DIVIDER = np.dstack([np.broadcast_to(np.float32(PINK_DEEP) / 255, (6, 170, 3)), np.ones((6, 170), np.float32)]).astype(np.float32)


def load_logos():
    order = os.path.join(LOGOS, "order.txt")
    if not os.path.exists(order):
        return []
    names = [l.strip() for l in open(order, encoding="utf-8") if l.strip() and not l.startswith("#")]
    n = max(1, len(names)); out = []
    for nm in names:
        im = Image.open(os.path.join(LOGOS, nm)).convert("RGBA")
        sc = min(150 / im.height, ((W - 160) - 60 * (n - 1)) / n / im.width)
        out.append(np.asarray(im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS), np.float32) / 255)
    return out


LOGO_SPR = load_logos()


def draw_card(img, tt):
    ct = tt - CARD_START
    img[:] = CARD_BG
    for tx in card_text:
        tx.draw(img, tt)
    dw = ease_out((ct - 1.4) / 0.4)
    if dw > 0:
        d = cv2.resize(DIVIDER, (max(2, int(170 * dw)), 6))
        over(img, d, W / 2, 880, 1.0)
    for ty in card_typing:
        ty.draw(img, tt)
    if LOGO_SPR:
        a = ease_out((ct - 3.6) / 0.6)
        gap = 60; total = sum(l.shape[1] for l in LOGO_SPR) + gap * (len(LOGO_SPR) - 1)
        x = W / 2 + total / 2
        for l in LOGO_SPR:
            over(img, l, x - l.shape[1] / 2, 1640, a); x -= l.shape[1] + gap
    f = smooth((ct - (E["card"]["len"] * BEAT - 0.5)) / 0.5)
    if f > 0:
        img[:] = img * (1 - f) + CARD_BG * f


# ---------------------------------------------------------------- shot frame with transitions
def shot_frame(s, reader, tt):
    lt = tt - s["start"]
    fr = reader.get(src_index(s, lt))
    i_in = int(round(lt * FPS))                       # frames since this shot began
    i_out = int(round((s["start"] + s["dur"] - tt) * FPS))  # frames until the next cut
    dx = dy = 0.0; ez = 1.0; er = 0.0; blur = 0; vblur = False; flash = 0.0
    # --- entering
    if s["tr"] in ("whip_l", "whip_r") and i_in < TR:
        k = 1 - (i_in + 1) / (TR + 1)
        dx = (W * 0.55 * k ** 1.6) * (1 if s["tr"] == "whip_l" else -1)
        blur = 140 * k
    elif s["tr"] == "roll" and i_in < TR:
        k = 1 - (i_in + 1) / (TR + 1)
        er = -28 * k ** 1.5; ez = 1 + 0.25 * k; blur = 60 * k; vblur = True
    elif s["tr"] == "punch" and i_in < TR + 2:
        k = 1 - (i_in + 1) / (TR + 3)
        ez = 1 + 0.22 * k ** 1.4
        dx, dy = rng.normal(0, 14 * k, 2)
    elif s["tr"] == "flash" and i_in < TR + 2:
        flash = (1 - (i_in + 1) / (TR + 3)) ** 1.3
    # --- leaving (motion continues into the next shot's direction)
    nt = s["out_tr"]
    if 0 < i_out <= TR and nt in ("whip_l", "whip_r", "roll"):
        k = 1 - (i_out - 1) / TR
        if nt == "roll":
            er += 28 * k ** 1.5; ez *= 1 + 0.25 * k; blur = max(blur, 60 * k); vblur = True
        else:
            dx += (-W * 0.55 * k ** 1.6) * (1 if nt == "whip_l" else -1); blur = max(blur, 140 * k)
    elif 0 < i_out <= 3 and nt == "flash":
        flash = max(flash, (1 - (i_out - 1) / 3) ** 1.5 * 0.9)
    # extra flash points inside the shot (in beats, relative to the film)
    for fb in s.get("flash", []):
        d = abs(tt - fb * BEAT) * FPS
        if d < 5:
            flash = max(flash, (1 - d / 5) ** 1.4)
    img = transform(fr, s, max(0.0, min(lt, s["dur"])), ez, er, dx, dy).astype(np.float32) / 255
    if blur > 2:
        if vblur:
            img = cv2.GaussianBlur(img, (0, 0), blur / 12)
        else:
            img = motion_blur(img, blur)
    # neon "lights on" flicker (poster 2)
    if s.get("neon") and CIRCLE <= i_in < CIRCLE + 12:  # flicker once the circle has opened
        pattern = [1.0, 0.45, 1.2, 0.5, 0.45, 1.15, 1.0, 0.6, 1.1, 1.0, 1.0, 1.0]
        v = pattern[i_in - CIRCLE]
        img = np.clip(img * v, 0, 1)
        img = bloom(img, 0.6 * max(0, v - 0.9) * 4)
    img = look(img, extra_bloom=0.5 * flash)
    if flash > 0:
        img = img * (1 - 0.75 * flash) + np.float32([1.0, 0.95, 0.97]) * 0.75 * flash
    return img


def circle_blend(out_img, in_img, k, c):
    cx, cy, r0 = c
    rmax = np.hypot(max(cx, W - cx), max(cy, H - cy)) * 1.05
    r = r0 + (rmax - r0) * ease_in(k) if k < 1 else rmax
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    m = np.clip((r - d) / 6, 0, 1)[..., None]
    ring = np.clip(1 - np.abs(d - r) / 10, 0, 1)[..., None] * (1 - k)
    res = out_img * (1 - m) + in_img * m
    return np.clip(res + ring * np.float32([1.0, 0.55, 0.78]) * 0.9, 0, 1)


# ---------------------------------------------------------------- main
def main():
    out = os.path.join(BUILD, "video_v2.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", out],
                           stdin=subprocess.PIPE)
    readers = {}
    qc = os.path.join(ROOT, "06_qc", "stills_v2"); os.makedirs(qc, exist_ok=True)
    stills = {}
    if STILLS:
        for s in shots:
            stills[int((s["start"] + s["dur"] * 0.6) * FPS)] = s["id"]
        for g in E["words"]:
            stills[int((g["until"] * BEAT - 0.15) * FPS)] = "T_" + g["group"]
        stills[int((CARD_START + 4.6) * FPS)] = "CARD"
        stills[int(1.9 * FPS)] = "TYPING"
        stills[int((shots[3]["start"] - 4 / FPS) * FPS)] = "CIRCLE"
    for s in shots:
        if s.get("focus") == "pink":
            r_ = Reader(s); fr = r_.get(int(s["dur"] * FPS)); r_.close()
            s["focus_xy"] = pink_center(fr)[:2]
    circle_c = None
    for fi in range(NFR):
        tt = fi / FPS
        active = [s for s in shots if s["start"] - 1e-6 <= tt < s["start"] + s["dur"] + s["ext"] - 1e-6]
        for s in shots:
            if s["id"] in readers and tt >= s["start"] + s["dur"] + s["ext"]:
                readers.pop(s["id"]).close()
        imgs = []
        for s in active:
            if s["id"] not in readers:
                readers[s["id"]] = Reader(s)
            imgs.append((s, shot_frame(s, readers[s["id"]], tt)))
        frame = None
        if imgs:
            frame = imgs[0][1]
            if len(imgs) > 1 and imgs[1][0]["tr"] == "circle":
                s_in = imgs[1][0]
                k = (tt - s_in["start"]) / (CIRCLE / FPS)
                if circle_c is None:  # find the balloon in the frame actually on screen
                    cx, cy, r = pink_center((imgs[0][1] * 255).astype(np.uint8))
                    circle_c = (cx, cy, r * 1.1)
                frame = circle_blend(imgs[0][1], imgs[1][1], max(0.0, k), circle_c)
        if tt >= CARD_START:
            card = np.empty((H, W, 3), np.float32); draw_card(card, tt)
            k = (tt - CARD_START) * FPS
            if frame is not None and k < 6:
                fl = (1 - k / 6)
                frame = frame * (1 - (k + 1) / 6) + card * ((k + 1) / 6)
                frame = frame * (1 - 0.6 * fl) + 0.6 * fl  # white flash into the card
            else:
                frame = card
        else:
            frame = frame.copy()
            vis = 0.0
            for tx in film_text:
                if tx.items[0]["t"] - 0.1 <= tt <= tx.until + 0.25:
                    vis = 1.0
            if vis:
                frame[:] = frame * (1 - GRAD) + np.float32([22, 8, 18]) / 255 * GRAD
            for ty in film_typing:
                ty.draw(frame, tt)
            for tx in film_text:
                tx.draw(frame, tt)
        u8 = (np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8)
        enc.stdin.write(u8.tobytes())
        if fi in stills:
            Image.fromarray(u8).save(os.path.join(qc, f"{fi:04d}_{stills[fi]}.jpg"), quality=90)
        if fi % 150 == 0:
            print(f"v2: frame {fi}/{NFR}", flush=True)
    for r_ in readers.values():
        r_.close()
    enc.stdin.close(); enc.wait()
    json.dump({"total": TOTAL, "card_start": CARD_START, "beat": BEAT,
               "cuts": [{"id": s["id"], "t": round(s["start"], 3), "tr": s["tr"]} for s in shots]},
              open(os.path.join(BUILD, "timeline_v2.json"), "w"), indent=1)
    print("done", out, f"{TOTAL:.2f}s")


if __name__ == "__main__":
    main()
