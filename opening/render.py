#!/usr/bin/env python3
"""Cinematic documentary opening — "قصص كفاح المرأة".

The four original archival photographs are never redrawn, morphed or
re-generated: every frame is a 2-D camera move (push-in, pan, parallax) over
the untouched photo, plus film treatment (sepia toning, grain, dust,
scratches, flicker, gate weave, light sweeps, light leaks).

Usage:
    python3 render.py --both          # 4K 24 fps, titled + clean versions in one pass
    python3 render.py --res 1080      # faster HD render
    python3 render.py --still 9.5     # single preview frame (PNG)
"""
import argparse
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
FPS = 24
DUR = 60.0
IVORY = np.array([0.96, 0.92, 0.84], np.float32)
FONT_REG = os.path.join(ROOT, "fonts", "Amiri-Regular.ttf")
FONT_BOLD = os.path.join(ROOT, "fonts", "Amiri-Bold.ttf")

# --------------------------------------------------------------- the four women
# face = (x, y) of the face in the photo, normalised 0..1
# path = camera focus point at start / end, zoom = start / end
CHARS = [
    dict(file="01_mabruka_alwakwak.jpg", role="المجاهدة", name="مبروكة الوكواك",
         face=(0.50, 0.36), p0=(0.50, 0.50), p1=(0.50, 0.38), z=(1.00, 1.42),
         tint=0.42, contrast=1.0, exposure=0.86, t=(3.5, 14.0), fade_in=(3.5, 7.5), fade_out=(12.4, 14.0),
         caption=(7.0, 12.0)),
    dict(file="02_zaima_albarouni.jpg", role="الأديبة", name="زعيمة الباروني",
         face=(0.52, 0.45), p0=(0.50, 0.52), p1=(0.52, 0.45), z=(1.04, 1.28),
         tint=0.30, contrast=1.08, t=(13.6, 22.3), fade_in=(13.6, 15.4), fade_out=(21.0, 22.3),
         caption=(15.4, 20.4), parallax=True),
    dict(file="03_hamida_alenezi.jpg", role="الرائدة", name="حميدة العنيزي",
         face=(0.46, 0.36), p0=(0.50, 0.66), p1=(0.47, 0.40), z=(1.16, 1.40),
         tint=0.62, contrast=1.06, t=(22.1, 31.5), fade_in=(22.1, 23.9), fade_out=(30.3, 31.5),
         caption=(24.8, 29.8)),
    dict(file="04_khadija_aljahmi.jpg", role="الإعلامية", name="خديجة الجهمي",
         face=(0.25, 0.22), p0=(0.50, 0.50), p1=(0.25, 0.24), z=(1.00, 1.75),
         tint=0.32, contrast=1.20, t=(31.3, 41.0), fade_in=(31.3, 32.8), fade_out=(39.6, 40.9),
         caption=(33.2, 38.6), cover=True),
]
MONTAGE = (40.4, 47.8)
PRINT_IN = [40.6, 41.6, 42.6, 43.6]
LINE1 = "نساءٌ لم يكتفينَ بكتابة التاريخ..."
LINE2 = "بل كنَّ جزءًا من صناعته."
TITLE = "قصص كفاح المرأة"
TEXT1_T = (48.0, 53.4)
TEXT2_T = (50.5, 53.4)
TITLE_T = (55.0, 59.0)

G = {}  # per-process globals


# --------------------------------------------------------------- helpers
def sstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ramp(t, a, b):
    return sstep((t - a) / (b - a))


def ease_cam(u):
    """Mostly constant-speed camera with soft start/stop."""
    u = min(max(u, 0.0), 1.0)
    return 0.55 * u + 0.45 * (0.5 - 0.5 * math.cos(math.pi * u))


def lerp(a, b, u):
    return a + (b - a) * u


def smooth_noise(t, seed, freqs=(0.11, 0.23, 0.47)):
    r = np.random.default_rng(seed)
    ph = r.uniform(0, 6.283, len(freqs))
    return sum(math.sin(2 * math.pi * f * t + p) for f, p in zip(freqs, ph)) / len(freqs)


def load_gray(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im, np.float32) / 255.0
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    lo, hi = np.percentile(lum, [0.8, 99.6])
    lum = np.clip((lum - lo) / (hi - lo), 0, 1) * 0.94 + 0.03
    return lum


def tone_lut(tint, contrast):
    x = np.linspace(0, 1, 1024, dtype=np.float32)
    y = np.clip(0.5 + (x - 0.5) * contrast, 0, 1.2)
    y = 0.025 + 0.925 * (1 - np.exp(-2.6 * y)) / (1 - np.exp(-2.6))  # soft shoulder, lifted blacks
    r = y ** (1 / (1 + 0.20 * tint))
    g = y ** (1 + 0.04 * tint)
    b = y ** (1 + 0.42 * tint)
    return np.stack([r, g, b], 1).astype(np.float32)


def text_layer(text, font_path, size, shadow=True, spacing=0):
    font = ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.RAQM)
    l, t, r, b = font.getbbox(text, direction="rtl", language="ar")
    pad = int(size * 0.6)
    w, h = r - l + 2 * pad, b - t + 2 * pad
    txt = Image.new("L", (w, h), 0)
    ImageDraw.Draw(txt).text((pad - l, pad - t), text, font=font, fill=255, direction="rtl", language="ar")
    a = np.asarray(txt, np.float32) / 255
    sh = np.zeros_like(a)
    if shadow:
        sh = np.asarray(txt.filter(ImageFilter.GaussianBlur(size * 0.18)), np.float32) / 255 * 0.85
    return a, sh


# --------------------------------------------------------------- setup
def setup(W, H, outputs):
    G.update(W=W, H=H, outputs=outputs, sc=W / 3840)
    clean = "titled" not in outputs
    lw, lh = 480, 270
    G["lw"], G["lh"] = lw, lh
    yy, xx = np.mgrid[0:lh, 0:lw].astype(np.float32)
    G["lx"], G["ly"] = (xx + 0.5) / lw, (yy + 0.5) / lh
    d = np.sqrt(((G["lx"] - 0.5) * 1.15) ** 2 + ((G["ly"] - 0.47) * 1.0) ** 2)
    G["vignette"] = (1 - 0.72 * np.clip((d - 0.22) / 0.55, 0, 1) ** 1.6).astype(np.float32)

    shots = []
    for c in CHARS:
        lum = load_gray(os.path.join(ROOT, "assets", c["file"]))
        sh, sw = lum.shape
        cover = c.get("cover", False)
        up = (H * 1.0 * c["z"][1] * 1.15) / sh if not cover else (H * c["z"][1] * 1.1) / sh
        up = max(up, 1.0)
        big = Image.fromarray((lum * 255).astype(np.uint8)).resize((int(sw * up), int(sh * up)), Image.LANCZOS)
        big = big.filter(ImageFilter.GaussianBlur(max(1.0, up * 0.35)))  # hide JPEG blocks, add no detail
        bw, bh = big.size
        if not cover:
            yy, xx = np.mgrid[0:bh, 0:bw].astype(np.float32)
            ex = np.clip(np.minimum(xx, bw - 1 - xx) / (0.16 * bw), 0, 1)
            ey = np.clip(np.minimum(yy, bh - 1 - yy) / (0.12 * bh), 0, 1)
            mask = (ex * ex * (3 - 2 * ex)) * (ey * ey * (3 - 2 * ey))
            fg = Image.merge("LA", (big, Image.fromarray((mask * 255).astype(np.uint8))))
            bgsrc = Image.fromarray((lum * 255).astype(np.uint8)).resize((sw * 4, sh * 4), Image.BICUBIC)
            bgsrc = bgsrc.filter(ImageFilter.GaussianBlur(sw * 4 * 0.05))
            base = H * 0.92 / bh
        else:
            fg = Image.merge("LA", (big, Image.new("L", big.size, 255)))
            bgsrc = None
            base = max(W / bw, H / bh)
        shot = dict(c, fg=fg, bg=bgsrc, base=base, size=(bw, bh), lut=tone_lut(c["tint"], c["contrast"]))
        if not clean:
            shot["cap"] = caption_layer(c["role"], c["name"])
        shots.append(shot)
    G["shots"] = shots
    G["mont_lut"] = tone_lut(0.42, 1.08)
    G["prints"] = make_prints()
    if not clean:
        s = G["sc"]
        G["line1"] = text_layer(LINE1, FONT_REG, int(150 * s))
        G["line2"] = text_layer(LINE2, FONT_REG, int(150 * s))
        G["title"] = text_layer(TITLE, FONT_BOLD, int(270 * s))


def caption_layer(role, name):
    s = G["sc"]
    ra, rs = text_layer(role, FONT_REG, int(76 * s))
    na, ns = text_layer(name, FONT_BOLD, int(132 * s))
    w = max(ra.shape[1], na.shape[1])
    gap = int(10 * s)
    h = ra.shape[0] + na.shape[0] + gap - int(80 * s)
    A = np.zeros((h, w), np.float32)
    S = np.zeros((h, w), np.float32)
    # right-aligned (Arabic)
    A[: ra.shape[0], w - ra.shape[1]:] = np.maximum(A[: ra.shape[0], w - ra.shape[1]:], ra * 0.78)
    S[: ra.shape[0], w - ra.shape[1]:] = np.maximum(S[: ra.shape[0], w - ra.shape[1]:], rs)
    y2 = ra.shape[0] + gap - int(80 * s)
    A[y2:y2 + na.shape[0], w - na.shape[1]:] = np.maximum(A[y2:y2 + na.shape[0], w - na.shape[1]:], na)
    S[y2:y2 + na.shape[0], w - na.shape[1]:] = np.maximum(S[y2:y2 + na.shape[0], w - na.shape[1]:], ns)
    # thin rule between role and name
    pad = int(76 * 0.6 * s)
    ly = ra.shape[0] - int(32 * s)
    L = int(420 * s)
    x1 = w - pad
    fade = np.linspace(0, 1, L, dtype=np.float32) ** 1.5
    A[ly:ly + max(1, int(2 * s)), x1 - L:x1] = np.maximum(A[ly:ly + max(1, int(2 * s)), x1 - L:x1], fade * 0.55)
    return A, S


def make_prints():
    """Archival prints for the generations montage (photo + paper border)."""
    H = G["H"]
    out = []
    for c in CHARS:
        lum = load_gray(os.path.join(ROOT, "assets", c["file"]))
        if c.get("cover"):
            sh, sw = lum.shape
            cw = int(sh * 0.76)
            cx = int(c["face"][0] * sw)
            x0 = min(max(cx - cw // 2, 0), sw - cw)
            lum = lum[:, x0:x0 + cw]
        ph = int(H * 0.44)
        sh, sw = lum.shape
        pw = int(sw * ph / sh)
        im = Image.fromarray((lum * 255).astype(np.uint8)).resize((pw, ph), Image.LANCZOS)
        im = im.filter(ImageFilter.GaussianBlur(ph / sh * 0.3))
        b = int(H * 0.016)
        paper = Image.new("L", (pw + 2 * b, ph + 2 * b), 196)
        paper.paste(im, (b, b))
        # aged paper: slightly uneven tone
        r = np.random.default_rng(len(out))
        pa = np.asarray(paper, np.float32)
        stain = np.asarray(Image.fromarray((r.random((12, 9)) * 255).astype(np.uint8)).resize(paper.size, Image.BICUBIC), np.float32)
        pa = pa * (0.9 + 0.1 * stain / 255)
        paper = Image.fromarray(np.clip(pa, 0, 255).astype(np.uint8))
        out.append(paper)
    return out


# --------------------------------------------------------------- frame parts
def gate_weave(t):
    s = G["sc"]
    return (1.3 * s * smooth_noise(t * 6, 11, (0.9, 2.1, 3.7)), 1.0 * s * smooth_noise(t * 6, 12, (0.8, 1.7, 3.1)))


def affine(sw, sh, P, Q, k):
    """Screen = Q + (src - P) * k   ->  PIL inverse affine."""
    return (1 / k, 0, P[0] - Q[0] / k, 0, 1 / k, P[1] - Q[1] / k)


def render_shot(sh, t):
    W, H = G["W"], G["H"]
    t0, t1 = sh["t"]
    u = ease_cam((t - t0) / (t1 - t0))
    z = lerp(sh["z"][0], sh["z"][1], u)
    bw, bh = sh["size"]
    k = sh["base"] * z
    fx, fy = lerp(sh["p0"][0], sh["p1"][0], u), lerp(sh["p0"][1], sh["p1"][1], u)
    P = [fx * bw, fy * bh]
    wx, wy = gate_weave(t)
    drift = 0.004 * W * smooth_noise(t, hash(sh["file"]) % 1000, (0.05, 0.09))
    Q = [W / 2 + wx + drift, H / 2 + wy]
    if sh.get("parallax"):
        Q[0] += lerp(-0.010, 0.010, u) * W
    if sh.get("cover"):  # keep the frame inside the photograph
        hw, hh = W / 2 / k, H / 2 / k
        P[0] = min(max(P[0], hw + 2), bw - hw - 2)
        P[1] = min(max(P[1], hh + 2), bh - hh - 2)
    fg = sh["fg"].transform((W, H), Image.AFFINE, affine(bw, bh, P, Q, k), Image.BICUBIC)
    f = np.asarray(fg, np.float32) / 255
    lum, a = f[..., 0], f[..., 1]
    if sh["bg"] is not None:
        gw, gh = sh["bg"].size
        kb = max(W / gw, H / gh) * lerp(1.12, 1.18, u)
        shift = (lerp(0.012, -0.012, u) * W) if sh.get("parallax") else 0.0
        Pb = [gw / 2 + (P[0] / bw - 0.5) * gw * 0.35, gh / 2 + (P[1] / bh - 0.5) * gh * 0.35]
        bg = sh["bg"].transform((W, H), Image.AFFINE, affine(gw, gh, Pb, (W / 2 + shift + wx * 0.5, H / 2), kb), Image.BILINEAR)
        b = np.asarray(bg, np.float32) / 255 * 0.26
        lum = b + (lum - b) * a
    # face position on screen (for light & reveal)
    fsx = (Q[0] + (sh["face"][0] * bw - P[0]) * k) / W
    fsy = (Q[1] + (sh["face"][1] * bh - P[1]) * k) / H
    return lum, (fsx, fsy)


def gain_map(t, face, sh_index, local_t):
    lx, ly = G["lx"], G["ly"]
    g = G["vignette"].copy()
    # slow volumetric light sweep across the photograph
    ang = 0.55
    pos = lerp(-0.35, 1.35, local_t)
    d = (lx * math.cos(ang) + ly * math.sin(ang) * 0.6) - pos
    g *= 1 + 0.10 * np.exp(-(d / 0.22) ** 2)
    # soft pool of light that lingers on the face
    fd = ((lx - face[0]) * 1.6) ** 2 + (ly - face[1]) ** 2
    g *= 0.88 + 0.14 * np.exp(-fd / 0.06)
    if sh_index == 0:  # Mabruka emerges from darkness, eyes first
        r = lerp(0.02, 1.6, ramp(t, 3.5, 9.0))
        g *= np.clip(1 - (np.sqrt(fd) - r) / 0.32, 0, 1) ** 1.4
    return g


def upsample(field):
    W, H = G["W"], G["H"]
    return np.asarray(Image.fromarray(field.astype(np.float32), "F").resize((W, H), Image.BILINEAR))


def flicker(t):
    n = int(t * FPS)
    r = np.random.default_rng(1000 + n)
    return 1 + 0.016 * smooth_noise(t, 5, (1.3, 2.9, 5.3)) + 0.008 * r.standard_normal()


def light_leak(t):
    """Very gentle amber film burn at chosen transitions (low-res RGB)."""
    events = [(21.4, 24.2, 0.20, (0.85, 0.30)), (40.0, 41.8, 0.10, (0.15, 0.65)), (30.9, 32.3, 0.07, (0.9, 0.8))]
    acc = None
    for a, b, s, (cx, cy) in events:
        if a < t < b:
            e = math.sin(math.pi * (t - a) / (b - a)) ** 2 * s
            u = (t - a) / (b - a)
            x = cx + 0.12 * (u - 0.5)
            fd = ((G["lx"] - x) * 1.4) ** 2 + (G["ly"] - cy) ** 2
            m = np.exp(-fd / 0.09) * e
            leak = np.stack([m * 1.0, m * 0.55, m * 0.22], -1)
            acc = leak if acc is None else acc + leak
    return acc


def montage(t):
    W, H = G["W"], G["H"]
    s = G["sc"]
    canvas = Image.new("L", (W, H), 8)
    prints = G["prints"]
    u = ramp(t, 44.6, 47.2)  # gather
    gap = int(70 * s)
    widths = [p.size[0] for p in prints]
    total = sum(widths) + gap * 3
    xs_spread, x = [], W / 2 + total / 2
    for w in widths:  # chronological, right to left
        xs_spread.append(x - w / 2)
        x -= w + gap
    stack_step = [w * 0.66 for w in widths]
    tot2 = sum(stack_step[:3])
    xs_stack, x = [], W / 2 + tot2 / 2
    for i in range(4):
        xs_stack.append(x)
        x -= stack_step[i]
    rots = [1.6, -1.2, 1.0, -1.8]
    zoom = lerp(1.0, 1.07, ramp(t, MONTAGE[0], MONTAGE[1]))
    wx, wy = gate_weave(t)
    for i, p in enumerate(prints):
        a = ramp(t, PRINT_IN[i], PRINT_IN[i] + 1.2)
        if a <= 0:
            continue
        cx = lerp(xs_spread[i], xs_stack[i], u)
        cy = H * 0.5 + (1 - a) * 40 * s + (lerp(0, [-14, 10, -8, 12][i], u)) * s
        cx = W / 2 + (cx - W / 2) * zoom + wx
        cy = H / 2 + (cy - H / 2) * zoom + wy
        pz = p.resize((int(p.size[0] * zoom), int(p.size[1] * zoom)), Image.BICUBIC) if zoom != 1 else p
        rot = rots[i] * u
        la = Image.merge("LA", (pz, Image.new("L", pz.size, 255)))
        if abs(rot) > 0.01:
            la = la.rotate(rot, Image.BICUBIC, expand=True)
        L, A = la.split()
        A = A.point(lambda v, a=a: int(v * a))
        shadow = A.filter(ImageFilter.GaussianBlur(28 * s)).point(lambda v: int(v * 0.8))
        pos = (int(cx - la.size[0] / 2), int(cy - la.size[1] / 2))
        canvas.paste(0, (pos[0] + int(18 * s), pos[1] + int(26 * s)), shadow)
        canvas.paste(L, pos, A)
    lum = np.asarray(canvas, np.float32) / 255
    return lum


def overlay_text(img, layer, cx, cy, opacity, scale=1.0, right=None):
    A, S = layer
    if opacity <= 0.001:
        return
    if scale != 1.0:
        h, w = A.shape
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        A = np.asarray(Image.fromarray(A, "F").resize(size, Image.BICUBIC))
        S = np.asarray(Image.fromarray(S, "F").resize(size, Image.BICUBIC))
    h, w = A.shape
    x0 = int(right - w) if right is not None else int(cx - w / 2)
    y0 = int(cy - h / 2)
    H, W = img.shape[:2]
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb:
        return
    a = np.clip(A[ya - y0:yb - y0, xa - x0:xb - x0], 0, 1)[..., None] * opacity
    sh = np.clip(S[ya - y0:yb - y0, xa - x0:xb - x0], 0, 1)[..., None] * opacity * 0.6
    reg = img[ya:yb, xa:xb]
    reg *= 1 - sh
    reg[:] = reg * (1 - a) + IVORY * a


def dust_and_scratches(img, t, n):
    W, H = G["W"], G["H"]
    s = G["sc"]
    r = np.random.default_rng(5000 + n)
    layer = Image.new("L", (W, H), 128)
    d = ImageDraw.Draw(layer)
    for _ in range(r.poisson(3.2)):
        x, y = r.uniform(0, W), r.uniform(0, H)
        rad = r.uniform(1.5, 6) * s
        v = 128 + int(r.choice([-1, 1]) * r.uniform(40, 110))
        d.ellipse([x - rad, y - rad * r.uniform(0.6, 1.4), x + rad, y + rad], fill=v)
    if r.random() < 0.06:  # occasional hair
        x, y = r.uniform(0, W), r.uniform(0, H)
        pts = [(x + 60 * s * math.sin(i * 0.4 + r.uniform(0, 1)) + i * 6 * s, y + i * 9 * s) for i in range(18)]
        d.line(pts, fill=128 - 70, width=max(1, int(2 * s)))
    # long vertical scratches persist for a few frames
    seg = n // 9
    rs = np.random.default_rng(9000 + seg)
    if rs.random() < 0.45:
        x = rs.uniform(0.08, 0.92) * W + (n % 9) * rs.uniform(-0.6, 0.6) * s
        v = 128 + int(rs.choice([-1, 1]) * rs.uniform(18, 40))
        d.line([(x, 0), (x + rs.uniform(-8, 8) * s, H)], fill=v, width=max(1, int(rs.uniform(1, 2.5) * s)))
    lay = np.asarray(layer.filter(ImageFilter.GaussianBlur(0.8 * s)), np.float32) / 255 - 0.5
    img += lay[..., None] * 0.9


def grain(img, n, amount, lum):
    W, H = G["W"], G["H"]
    r = np.random.default_rng(20000 + n)
    gw, gh = W // 2, H // 2
    g = r.standard_normal((gh, gw), dtype=np.float32)
    g = np.asarray(Image.fromarray(g, "F").resize((W, H), Image.BILINEAR))
    img += g[..., None] * amount * (0.35 + 0.9 * np.sqrt(np.clip(lum, 0, 1)) * (1.2 - lum))


def draw_text(out, t):
    W, H = G["W"], G["H"]
    for i, sh in enumerate(G["shots"]):
        c0, c1 = sh["caption"]
        if c0 - 0.1 < t < c1 + 1.2:
            op = ramp(t, c0, c0 + 1.4) * (1 - ramp(t, c1, c1 + 1.1))
            drift = (1 - ramp(t, c0, c0 + 3.0)) * 24 * G["sc"]
            cap = sh["cap"]
            overlay_text(out, cap, 0, H * 0.80, op * 0.92, right=W * 0.935 + drift)
    if TEXT1_T[0] < t < TEXT1_T[1] + 1.4:
        op = ramp(t, TEXT1_T[0], TEXT1_T[0] + 1.8) * (1 - ramp(t, TEXT1_T[1], TEXT1_T[1] + 1.2))
        overlay_text(out, G["line1"], W / 2, H * 0.44, op)
    if TEXT2_T[0] < t < TEXT2_T[1] + 1.4:
        op = ramp(t, TEXT2_T[0], TEXT2_T[0] + 1.3) * (1 - ramp(t, TEXT2_T[1], TEXT2_T[1] + 1.2))
        overlay_text(out, G["line2"], W / 2, H * 0.575, op)
    if TITLE_T[0] < t < TITLE_T[1] + 1.2:
        op = ramp(t, TITLE_T[0], TITLE_T[0] + 2.2) * (1 - ramp(t, TITLE_T[1], TITLE_T[1] + 1.0))
        sc = lerp(0.975, 1.0, ramp(t, TITLE_T[0], TITLE_T[1] + 1))
        overlay_text(out, G["title"], W / 2, H * 0.47, op, scale=sc)
        # thin rule that opens from the centre under the title
        lw = int(W * 0.16 * ramp(t, TITLE_T[0] + 0.8, TITLE_T[0] + 3.0))
        if lw > 2:
            y = int(H * 0.60)
            th = max(1, int(2 * G["sc"]))
            prof = 1 - np.abs(np.linspace(-1, 1, 2 * lw, dtype=np.float32)) ** 2
            seg = out[y:y + th, W // 2 - lw:W // 2 + lw]
            a = (prof * 0.6 * op)[None, :, None]
            seg[:] = seg * (1 - a) + IVORY * a


# --------------------------------------------------------------- frame
def render_frame(n):
    t = n / FPS
    W, H = G["W"], G["H"]
    out = np.zeros((H, W, 3), np.float32)
    fl = flicker(t)

    # 0–3.5 s: darkness, a faint projector glow
    if t < 6.0:
        glow = 0.022 * ramp(t, 0.6, 2.6) * (1 - ramp(t, 4.0, 6.0))
        out += glow * fl * upsample(G["vignette"])[..., None] * IVORY

    for i, sh in enumerate(G["shots"]):
        a, b = sh["t"]
        if not (a <= t <= b):
            continue
        alpha = ramp(t, *sh["fade_in"]) * (1 - ramp(t, *sh["fade_out"]))
        if alpha <= 0.002:
            continue
        lum, face = render_shot(sh, t)
        g = gain_map(t, face, i, (t - a) / (b - a)) * fl * sh.get("exposure", 1.0)
        lum = lum * upsample(g)
        idx = np.clip(lum * 1023, 0, 1023).astype(np.int32)
        rgb = sh["lut"][idx]
        out += rgb * alpha

    if MONTAGE[0] <= t <= MONTAGE[1]:
        alpha = 1 - ramp(t, 46.4, 47.8)
        lum = montage(t)
        lx, ly = G["lx"], G["ly"]
        g = G["vignette"] * (0.85 + 0.3 * np.exp(-((lx - 0.5) ** 2 + (ly - 0.5) ** 2) / 0.12)) * fl
        lum = lum * upsample(g)
        idx = np.clip(lum * 1023, 0, 1023).astype(np.int32)
        out += G["mont_lut"][idx] * alpha

    leak = light_leak(t)
    if leak is not None:
        L = np.stack([upsample(leak[..., c]) for c in range(3)], -1)
        out = 1 - (1 - out) * (1 - L)

    noise = film_noise(t, n, out[..., 1:2])
    end = 1 - ramp(t, DUR - 0.6, DUR)
    res = []
    if "clean" in G["outputs"]:
        res.append(finish(out, noise, end))
    if "titled" in G["outputs"]:
        draw_text(out, t)
        res.append(finish(out, noise, end))
    return res


def finish(img, noise, end):
    return (np.clip((img + noise) * end, 0, 1) * 255 + 0.5).astype(np.uint8)


def film_noise(t, n, lum):
    """Grain + dust + scratches as one additive layer (shared by both outputs)."""
    W, H = G["W"], G["H"]
    noise = np.zeros((H, W, 3), np.float32)
    dust_amt = ramp(t, 1.2, 3.0)
    if dust_amt > 0:
        dust_and_scratches(noise, t, n)
        noise *= dust_amt * (0.35 + 0.65 * np.clip(lum * 3, 0, 1))
    grain(noise, n, 0.045 * ramp(t, 0.2, 2.2) + 0.012, lum)
    return noise


def worker_init(W, H, outputs):
    setup(W, H, outputs)


def ffmpeg_cmd(W, H, path, audio):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", audio]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "17" if W >= 3840 else "16",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-x264-params", "aq-mode=3:psy-rd=1.0,0.15",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-r", str(FPS)]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "320k", "-shortest"]
    cmd += ["-movflags", "+faststart", path]
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=int, default=2160)
    ap.add_argument("--still", type=float, nargs="*")
    ap.add_argument("--clean", action="store_true", help="textless version only")
    ap.add_argument("--both", action="store_true", help="titled + textless in one pass")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=DUR)
    args = ap.parse_args()
    H = args.res
    W = H * 16 // 9
    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)

    outputs = ("clean",) if args.clean else ("clean", "titled") if args.both else ("titled",)
    if args.still:
        setup(W, H, outputs)
        for s in args.still:
            Image.fromarray(render_frame(int(round(s * FPS)))[-1]).save(os.path.join(out_dir, f"still_{s:05.1f}.png"))
        return

    tag = "4K" if H >= 2160 else f"{H}p"
    audio = os.path.join(out_dir, "score.wav")
    audio = audio if os.path.exists(audio) and args.start == 0 else None
    names = ["Qisas_Kifah_AlMara_Opening" + ("_CLEAN" if o == "clean" else "") + f"_{tag}_24fps.mp4" for o in outputs]
    procs = [subprocess.Popen(ffmpeg_cmd(W, H, os.path.join(out_dir, nm), audio), stdin=subprocess.PIPE) for nm in names]
    frames = range(int(args.start * FPS), int(args.end * FPS))
    with Pool(args.jobs, worker_init, (W, H, outputs)) as pool:
        for i, fs in enumerate(pool.imap(render_frame, frames, chunksize=2)):
            for p, f in zip(procs, fs):
                p.stdin.write(f.tobytes())
            if i % 24 == 0:
                print(f"\r{i / len(frames) * 100:5.1f}%", end="", file=sys.stderr, flush=True)
    for p in procs:
        p.stdin.close()
        p.wait()
    print("\nwrote " + ", ".join(names), file=sys.stderr)


if __name__ == "__main__":
    main()
