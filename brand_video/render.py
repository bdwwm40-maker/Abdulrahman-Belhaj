#!/usr/bin/env python3
"""Brand video: logo built circle-by-circle on ticks -> mask reveal -> character.

Style carried over from montage/preset_circle_match_cut.json:
one event per tick (0.5 s = 120 BPM), circles as the visual motif,
riser into an impact, circular mask reveal.
Run:  python3 render.py   (needs numpy, pillow, scipy-free, ffmpeg)
"""
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, DUR = 1080, 1920, 30, 12.0
BEAT = 0.5
SS = 2  # supersampling for the logo

PURPLE_TOP = np.array([174, 42, 255])
PURPLE_BOT = np.array([150, 44, 222])
DARK = (18, 5, 31)

# Logo geometry measured from assets/logo.png (1880x1880 canvas)
HEADS = [((745, 684), 73), ((958, 714), 65), ((1148, 741), 58)]
RINGS = [  # outer box, thickness
    ((597, 792, 893, 1200), 76),
    ((823, 814, 1091, 1180), 70),
    ((1029, 835, 1266, 1158), 62),
]
LOGO_C = (931, 905)
LOGO_W = 670


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x, s=1.9):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, x):
    return a + (b - a) * x


# ---------------------------------------------------------------- logo
def logo_mask(t, scale):
    """Return (L-mask, top-left) of the logo for time t, drawn at `scale` (px per logo px)."""
    s = scale * SS
    size = int(LOGO_W * 1.5 * s)
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    ox, oy = size / 2 - LOGO_C[0] * s, size / 2 - LOGO_C[1] * s
    P = lambda x, y: (ox + x * s, oy + y * s)

    for i, (box, th) in enumerate(RINGS):
        p = ease_in_out(prog(t, 2.0 + i * 0.25, 0.45))
        if p <= 0:
            continue
        x0, y0, x1, y1 = box
        ring = Image.new("L", (size, size), 0)
        rd = ImageDraw.Draw(ring)
        r = (x1 - x0) / 2
        rd.rounded_rectangle([*P(x0, y0), *P(x1, y1)], radius=r * s, fill=255)
        rd.rounded_rectangle([*P(x0 + th, y0 + th), *P(x1 - th, y1 - th)], radius=(r - th) * s, fill=0)
        if p < 1:
            sweep = Image.new("L", (size, size), 0)
            cx, cy = P((x0 + x1) / 2, (y0 + y1) / 2)
            R = (y1 - y0) * s
            ImageDraw.Draw(sweep).pieslice([cx - R, cy - R, cx + R, cy + R], 90, 90 + 360 * p, fill=255)
            ring = Image.fromarray(np.minimum(np.asarray(ring), np.asarray(sweep)))
        m = Image.fromarray(np.maximum(np.asarray(m), np.asarray(ring)))
        d = ImageDraw.Draw(m)

    for i, ((x, y), r) in enumerate(HEADS):
        p = prog(t, 0.5 + i * BEAT, 0.35)
        if p <= 0:
            continue
        k = ease_back(p, 2.6)
        cx, cy = P(x, y)
        rr = r * s * k
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=255)

    m = m.resize((size // SS, size // SS), Image.LANCZOS)
    return m


def colorize(mask, alpha=1.0):
    w, h = mask.size
    g = np.linspace(0, 1, h)[:, None, None]
    rgb = (PURPLE_TOP * (1 - g) + PURPLE_BOT * g).astype(np.uint8)
    rgb = np.broadcast_to(rgb, (h, w, 3)).copy()
    a = (np.asarray(mask).astype(np.float32) * alpha).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), "RGBA")


# ---------------------------------------------------------------- backgrounds
yy, xx = np.mgrid[0:H, 0:W]


def dark_bg(t):
    d = np.hypot(xx - W / 2, yy - H * 0.47) / (H * 0.55)
    pulse = 0.18 + 0.12 * ease_out(prog(t, 3.0, 0.3)) * (1 - prog(t, 3.3, 0.7))
    glow = np.clip(1 - d, 0, 1)[..., None] ** 2 * (0.35 + pulse)
    base = np.array(DARK, np.float32)
    col = base + glow * np.array([110, 30, 170], np.float32)
    return np.clip(col, 0, 255)


LIGHT = None


def light_bg():
    global LIGHT
    if LIGHT is None:
        g = (yy / H)[..., None]
        top, bot = np.array([255, 255, 255], np.float32), np.array([236, 224, 255], np.float32)
        LIGHT = top * (1 - g) + bot * g
    return LIGHT


# ---------------------------------------------------------------- character
CHAR = Image.open(os.path.join(HERE, "assets/character_cut.png")).convert("RGBA")
bb = Image.fromarray((np.asarray(CHAR)[..., 3] > 20).astype(np.uint8) * 255).getbbox()
CHAR = CHAR.crop(bb)
CH_H = 1250
CHAR = CHAR.resize((int(CHAR.width * CH_H / CHAR.height), CH_H), Image.LANCZOS)
shadow = Image.new("RGBA", CHAR.size, (0, 0, 0, 0))
shadow.putalpha(CHAR.getchannel("A").point(lambda v: v * 0.22))
SHADOW = shadow.filter(ImageFilter.GaussianBlur(18))


def ring_img(radius, width, color, alpha):
    size = int(radius * 2 + width * 2 + 4)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = size / 2
    ImageDraw.Draw(im).ellipse([c - radius, c - radius, c + radius, c + radius],
                               outline=(*color, int(255 * alpha)), width=int(width))
    return im


def disc_img(radius, color, alpha, blur=0):
    pad = int(blur * 3) + 2
    size = int(radius * 2) + pad * 2
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = size / 2
    ImageDraw.Draw(im).ellipse([c - radius, c - radius, c + radius, c + radius], fill=(*color, int(255 * alpha)))
    return im.filter(ImageFilter.GaussianBlur(blur)) if blur else im


def paste_c(canvas, im, cx, cy):
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


DOTS = [(-380, -300, 26, 0.0), (400, -120, 18, 1.3), (-420, 380, 14, 2.1),
        (390, 520, 30, 0.7), (-300, 760, 20, 1.8), (330, -520, 12, 2.6)]


# ---------------------------------------------------------------- frame
def frame(t):
    # background: dark, then circular mask reveal of the light scene from the big head
    reveal = ease_in_out(prog(t, 4.0, 0.6))
    logo_scale_0 = 1.1
    lc0 = (W / 2, H * 0.47)
    if reveal <= 0:
        bg = dark_bg(t)
    else:
        hx = lc0[0] + (HEADS[0][0][0] - LOGO_C[0]) * logo_scale_0
        hy = lc0[1] + (HEADS[0][0][1] - LOGO_C[1]) * logo_scale_0
        R = reveal * math.hypot(W, H) * 1.05
        inside = (np.hypot(xx - hx, yy - hy) < R)[..., None]
        bg = np.where(inside, light_bg(), dark_bg(t)) if reveal < 1 else light_bg()
    canvas = Image.fromarray(bg.astype(np.uint8)).convert("RGBA")

    # shockwave rings on impact (3.0) and end beat (10.0)
    for t0, cy, base in ((3.0, lc0[1], 300), (10.0, 330, 160)):
        for k in range(2):
            p = prog(t, t0 + k * 0.12, 0.9)
            if 0 < p < 1:
                col = (200, 130, 255) if t0 == 3.0 else (160, 70, 240)
                paste_c(canvas, ring_img(base + 520 * ease_out(p), 10 * (1 - p) + 2, col, 0.7 * (1 - p)), W / 2, cy)

    # light scene: halo, floating dots, character
    if t >= 4.3:
        hp = ease_out(prog(t, 4.3, 0.8))
        pulse = 1 + 0.025 * math.sin((t - 4.3) * math.pi * 2 * 0.5)
        paste_c(canvas, disc_img(430 * hp * pulse, (190, 140, 255), 0.35, blur=40), W / 2, 1150)
        paste_c(canvas, ring_img(470 * hp * pulse, 6, (174, 42, 255), 0.25 * hp), W / 2, 1150)
        for i, (dx, dy, r, ph) in enumerate(DOTS):
            dp = ease_back(prog(t, 4.6 + i * 0.1, 0.4))
            if dp <= 0:
                continue
            fy = 18 * math.sin(t * 1.6 + ph)
            paste_c(canvas, disc_img(r * dp, (174, 42, 255), 0.85), W / 2 + dx, 1150 + dy + fy)

        cp = prog(t, 4.5, 0.9)
        if cp > 0:
            k = ease_back(cp, 1.4)
            bob = 10 * math.sin((t - 5.4) * 2.2) * prog(t, 5.4, 0.5)
            x = W / 2 - CHAR.width / 2
            y = H - 90 - CH_H + (1 - k) * 900 + bob
            canvas.alpha_composite(SHADOW, (int(x + 14), int(y + 20)))
            canvas.alpha_composite(CHAR, (int(x), int(y)))

    # logo: built on ticks, then flies to the top
    move = ease_in_out(prog(t, 4.1, 0.9))
    end_pop = ease_back(prog(t, 10.0, 0.45), 2.2) - 1 if t >= 10.0 else 0
    bounce = 0.07 * math.sin(math.pi * prog(t, 3.0, 0.35))
    scale = lerp(logo_scale_0, 0.42, move) * (1 + bounce) * (1 + 0.15 * end_pop)
    cx, cy = W / 2, lerp(lc0[1], 330, move)
    m = logo_mask(t, scale)
    if t >= 2.9 and move < 1:  # glow on dark
        g = colorize(m.filter(ImageFilter.GaussianBlur(28)), 0.9 * (1 - move))
        paste_c(canvas, g, cx, cy)
    paste_c(canvas, colorize(m), cx, cy)

    # fade out
    f = prog(t, DUR - 0.5, 0.5)
    if f > 0:
        canvas = Image.blend(canvas, Image.new("RGBA", canvas.size, (255, 255, 255, 255)), f)
    return canvas.convert("RGB")


# ---------------------------------------------------------------- audio
SR = 48000


def audio():
    n = int(SR * DUR)
    out = np.zeros(n)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(7)

    def add(sig, at, gain=1.0):
        i = int(at * SR)
        j = min(n, i + len(sig))
        out[i:j] += sig[: j - i] * gain

    def env(d, a=0.003, r=8.0):
        x = np.arange(int(d * SR)) / SR
        return np.minimum(1, x / a) * np.exp(-r * x)

    def tick():
        x = np.arange(int(0.08 * SR)) / SR
        return (np.sin(2 * np.pi * 2800 * x) * np.exp(-70 * x) + 0.5 * np.sin(2 * np.pi * 1200 * x) * np.exp(-90 * x))

    def pop(f0):
        d = 0.25
        x = np.arange(int(d * SR)) / SR
        f = f0 * (1 + 1.5 * np.exp(-30 * x))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(d, 0.002, 14)

    def whoosh(d, up=True):
        x = np.arange(int(d * SR)) / SR
        noise = rng.standard_normal(len(x))
        k = np.linspace(0.02, 0.25, len(x)) if up else np.linspace(0.25, 0.02, len(x))
        y = np.zeros_like(noise)
        acc = 0.0
        for i in range(len(x)):  # one-pole low-pass with moving cutoff
            acc += k[i] * (noise[i] - acc)
            y[i] = acc
        return y * np.sin(np.pi * x / d) ** 2

    # riser 0..3
    d = 3.0
    x = np.arange(int(d * SR)) / SR
    riser = 0.35 * np.sin(2 * np.pi * np.cumsum(90 + 260 * (x / d) ** 2) / SR) * (x / d) ** 2
    riser += whoosh(d) * (x / d) ** 2 * 0.9
    add(riser, 0.0)
    # heads: tick + pop on each beat
    for i, f0 in enumerate((520, 620, 740)):
        add(tick(), 0.5 + i * BEAT, 0.45)
        add(pop(f0), 0.5 + i * BEAT, 0.6)
    # rings draw on
    for i in range(3):
        add(whoosh(0.45), 2.0 + i * 0.25, 0.7)
        add(tick(), 2.0 + i * 0.25, 0.25)
    # impact at 3.0
    d = 1.6
    x = np.arange(int(d * SR)) / SR
    boom = np.sin(2 * np.pi * np.cumsum(48 + 70 * np.exp(-12 * x)) / SR) * np.exp(-2.8 * x)
    add(boom, 3.0, 0.9)
    add(rng.standard_normal(int(0.3 * SR)) * env(0.3, 0.001, 16), 3.0, 0.35)
    # reveal whoosh + character pop
    add(whoosh(0.7), 3.95, 0.9)
    add(pop(330), 4.75, 0.5)
    # music bed 4..12: soft chords + kick + ticks at 120 BPM
    chords = [(261.6, 329.6, 392.0, 493.9), (220.0, 261.6, 329.6, 392.0),
              (174.6, 220.0, 261.6, 329.6), (196.0, 246.9, 293.7, 392.0)]
    bar = 4 * BEAT
    for b in range(4):
        t0 = 4.0 + b * bar
        dd = bar + 0.3
        x = np.arange(int(dd * SR)) / SR
        e = np.minimum(1, x / 0.25) * np.minimum(1, (dd - x) / 0.4)
        sig = sum(np.sin(2 * np.pi * f * x) + 0.3 * np.sin(4 * np.pi * f * x) for f in chords[b % 4])
        add(sig * e / 8, t0, 0.55)
        add(np.sin(2 * np.pi * chords[b % 4][0] / 2 * x) * e, t0, 0.18)  # bass
    kick_d = 0.35
    x = np.arange(int(kick_d * SR)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(50 + 110 * np.exp(-25 * x)) / SR) * np.exp(-9 * x)
    t = 5.0
    while t < DUR - 0.6:
        add(kick, t, 0.55)
        add(tick(), t + BEAT / 2, 0.12)
        t += BEAT
    # end accent at 10.0
    add(pop(880), 10.0, 0.5)
    add(boom, 10.0, 0.4)
    # fade + normalise
    fade = np.clip((DUR - tt) / 0.6, 0, 1)
    out *= fade
    out = np.tanh(out * 1.2)
    out /= np.max(np.abs(out)) / 0.89
    st = np.stack([out, out], 1)
    return (st * 32767).astype(np.int16)


def main():
    outdir = os.path.join(HERE, "out")
    os.makedirs(outdir, exist_ok=True)
    wav = os.path.join(outdir, "audio.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes(audio().tobytes())
    mp4 = os.path.join(outdir, "brand_video_9x16.mp4")
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5",
                           "-movflags", "+faststart", "-shortest", mp4], stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    for i in range(total):
        ff.stdin.write(frame(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"frame {i}/{total}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done:", mp4)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        for tt in map(float, sys.argv[2:]):
            frame(tt).resize((W // 3, H // 3)).save(os.path.join(HERE, f"out/prev_{tt:05.2f}.png"))
    else:
        main()
