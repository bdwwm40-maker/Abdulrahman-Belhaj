#!/usr/bin/env python3
"""PINK HOPE — compositor.

Reads edit.json, decodes + grades every shot with FFmpeg, composites push-ins,
dissolves, the cinematic look, Arabic titles (Raqm shaping via Pillow) and the
end card in NumPy/OpenCV, and pipes frames to FFmpeg (H.264).

Usage:  python3 render.py vertical|horizontal [--stills]
Output: build/video_<layout>.mp4 (no audio — mux.sh adds the mix)
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

E = json.load(open(os.path.join(HERE, "edit.json"), encoding="utf-8"))
FPS = E["fps"]
SRC = os.path.normpath(os.path.join(HERE, E["source_dir"]))

LAYOUT = sys.argv[1] if len(sys.argv) > 1 else "vertical"
STILLS = "--stills" in sys.argv
W, H = (1080, 1920) if LAYOUT == "vertical" else (1920, 1080)
PW, PH = 1080, 1920  # every shot is decoded as a 9:16 plate

# Palette
WHITE = (255, 255, 255)
PINK = (255, 111, 165)        # highlight on dark footage
PINK_DEEP = (214, 59, 120)    # highlight on the light end card
PLUM = (61, 24, 48)
PLUM_SOFT = (107, 69, 96)


def font(weight, size):
    return ImageFont.truetype(os.path.join(FONTS, f"Tajawal-{weight}.ttf"), size,
                              layout_engine=ImageFont.Layout.RAQM)


# ---------------------------------------------------------------- timeline
shots = E["shots"]
t = 0.0
for s in shots:
    s["start"] = t
    ov = s.get("xf", 0) / FPS if s["out"] in ("xfade", "card") else 0.0
    s["ov"] = ov
    t += s["dur"] - ov
CARD_START = t
TOTAL = CARD_START + E["card_dur"]
NFR = int(round(TOTAL * FPS))
by_id = {s["id"]: s for s in shots}


# ---------------------------------------------------------------- decoding
class Reader:
    """Streams graded 1080x1920 RGB frames for one shot."""

    def __init__(self, s):
        g = s["grade"]
        slow = s.get("slowmo", 1.0)
        warm = g["warm"]
        vf = []
        if slow != 1.0:
            vf.append(f"setpts=PTS*{slow}")
        vf += [
            f"scale={PW}:{PH}:force_original_aspect_ratio=increase:flags=lanczos",
            f"crop={PW}:{PH}",
            "unsharp=5:5:0.45:5:5:0",
            # 1) exposure / contrast / saturation  2) neutralise fluorescent green, warm skin a touch
            f"eq=brightness={g['bri']}:contrast=1.05:saturation={g['sat']}",
            f"colorbalance=rs={warm:.3f}:gs=-0.015:bs={-warm:.3f}:rm=0.010:gm=-0.020:bm=0.012:rh=0.020:gh=-0.006:bh=0.016",
            f"fps={FPS}", "format=rgb24",
        ]
        cmd = ["ffmpeg", "-v", "error", "-ss", f"{s['in']}", "-t", f"{s['dur'] / slow + 0.2}",
               "-i", os.path.join(SRC, s["src"]), "-an", "-vf", ",".join(vf),
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.last = None
        self.n = 0

    def read(self):
        buf = self.p.stdout.read(PW * PH * 3)
        if len(buf) == PW * PH * 3:
            self.last = np.frombuffer(buf, np.uint8).reshape(PH, PW, 3)
        elif self.last is None:
            raise RuntimeError("no frames decoded")
        self.n += 1
        return self.last

    def close(self):
        self.p.stdout.close(); self.p.wait()


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def push(img, s, local_t):
    """Smooth sub-pixel push-in / drift (never reveals frame edges)."""
    k = smooth(local_t / s["dur"])
    z = s["zoom"][0] + (s["zoom"][1] - s["zoom"][0]) * k
    lim = (z - 1) / 2
    px = max(-lim, min(lim, s["pan"][0] * k)) * PW
    py = max(-lim, min(lim, s["pan"][1] * k)) * PH
    if abs(z - 1) < 1e-4 and px == 0 and py == 0:
        return img.astype(np.float32) / 255
    M = np.float32([[z, 0, (1 - z) * PW / 2 + px], [0, z, (1 - z) * PH / 2 + py]])
    return cv2.warpAffine(img, M, (PW, PH), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REFLECT).astype(np.float32) / 255


# ---------------------------------------------------------------- look
yy, xx = np.mgrid[0:PH, 0:PW].astype(np.float32)
r = np.sqrt(((xx - PW / 2) / (PW / 2)) ** 2 + ((yy - PH / 2) / (PH / 2)) ** 2)
VIGNETTE = (1 - 0.22 * np.clip((r - 0.55) / 0.85, 0, 1) ** 1.6)[..., None]
del yy, xx, r


def look(img):
    # soft highlight glow
    small = cv2.resize(img, (PW // 4, PH // 4), interpolation=cv2.INTER_AREA)
    lum = small.mean(axis=2, keepdims=True)
    hl = small * np.clip((lum - 0.68) / 0.32, 0, 1)
    hl = cv2.GaussianBlur(hl, (0, 0), 7)
    glow = cv2.resize(hl, (PW, PH), interpolation=cv2.INTER_LINEAR)
    img = 1 - (1 - img) * (1 - 0.16 * glow)
    # gentle filmic shoulder + lifted blacks
    img = 0.018 + 0.982 * (img / (1 + 0.10 * img)) * 1.10
    # very light pink in highlights only
    lum = img.mean(axis=2, keepdims=True)
    img = img + (lum ** 2) * np.float32([0.012, -0.004, 0.010])
    return np.clip(img * VIGNETTE, 0, 1)


# ---------------------------------------------------------------- text sprites
def text_line(txt, f, color, hl_words=(), hl_color=PINK, shadow=True, tracking=0):
    """RGBA sprite of one RTL Arabic line; highlighted words recoloured in place."""
    pad = 40
    if tracking:  # latin wordmark with letter spacing
        widths = [f.getlength(c) for c in txt]
        tw = sum(widths) + tracking * (len(txt) - 1)
        asc, desc = f.getmetrics()
        im = Image.new("L", (int(tw) + 2 * pad, asc + desc + 2 * pad), 0)
        d = ImageDraw.Draw(im); x = pad
        for c, w in zip(txt, widths):
            d.text((x, pad), c, font=f, fill=255); x += w + tracking
        mask = im
        colmask = Image.new("L", im.size, 0)
    else:
        kw = dict(direction="rtl", language="ar")
        tw = f.getlength(txt, **kw)
        asc, desc = f.getmetrics()
        mask = Image.new("L", (int(tw) + 2 * pad, asc + desc + 2 * pad), 0)
        ImageDraw.Draw(mask).text((pad, pad), txt, font=f, fill=255, **kw)
        colmask = Image.new("L", mask.size, 0)
        for wd in hl_words:
            i = txt.find(wd)
            if i < 0:
                continue
            right = pad + tw - f.getlength(txt[:i], **kw) if i else pad + tw
            left = right - f.getlength(wd, **kw)
            ImageDraw.Draw(colmask).rectangle([left - 2, 0, right + 2, mask.size[1]], fill=255)
    m = np.asarray(mask, np.float32) / 255
    c = np.asarray(colmask, np.float32)[..., None] / 255
    rgb = np.float32(color) / 255 * (1 - c) + np.float32(hl_color) / 255 * c
    rgb = np.broadcast_to(rgb, m.shape + (3,)) if rgb.ndim == 1 else rgb
    rgba = np.dstack([np.broadcast_to(rgb, m.shape + (3,)), m])
    if shadow:
        sh = np.asarray(mask.filter(ImageFilter.GaussianBlur(9)), np.float32) / 255 * 0.55
        sh = np.roll(sh, 4, axis=0)
        a = m + sh * (1 - m)
        out_rgb = (rgba[..., :3] * m[..., None]) / np.maximum(a, 1e-6)[..., None]
        rgba = np.dstack([out_rgb, a])
    return rgba.astype(np.float32)


def bar(w, h, color):
    im = Image.new("L", (w + 8, h + 8), 0)
    ImageDraw.Draw(im).rounded_rectangle([4, 4, w + 4, h + 4], radius=h // 2, fill=255)
    m = np.asarray(im, np.float32) / 255
    return np.dstack([np.broadcast_to(np.float32(color) / 255, m.shape + (3,)), m]).astype(np.float32)


def over(dst, spr, cx, cy, alpha):
    """Alpha-composite sprite centred at (cx, cy)."""
    if alpha <= 0.002:
        return
    h, w = spr.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, dst.shape[1]), min(y0 + h, dst.shape[0])
    if xa >= xb or ya >= yb:
        return
    s = spr[ya - y0:yb - y0, xa - x0:xb - x0]
    a = s[..., 3:4] * alpha
    dst[ya:yb, xa:xb] = dst[ya:yb, xa:xb] * (1 - a) + s[..., :3] * a


V = LAYOUT == "vertical"
SIZES = {"hero": 112, "main": 104, "sub": 78} if V else {"hero": 92, "main": 100, "sub": 66}
TEXT_CX = W / 2 if V else 600
FG_W, FG_H = 576, 1024          # portrait panel inside the 16:9 layout
FG_X, FG_Y = 1920 - FG_W - 170, (1080 - FG_H) // 2

titles = []
for ti in E["titles"]:
    f = font(800 if ti["style"] != "sub" else 700, SIZES[ti["style"]])
    sprites = [text_line(l, f, WHITE, ti["hl"]) for l in ti["lines"]]
    lh = SIZES[ti["style"]] * 1.32
    if V:
        cy = 1000 if ti["style"] == "hero" else 1360
    else:
        cy = 540
    titles.append(dict(t0=by_id[ti["shot"]]["start"] + ti["at"], dur=ti["dur"], sprites=sprites,
                       lh=lh, cy=cy, style=ti["style"]))
ACCENT = bar(84, 7, PINK)

# bottom legibility gradient (vertical only)
g = np.clip((np.arange(PH, dtype=np.float32) - 900) / 760, 0, 1) ** 1.3
GRAD = (g * 0.72)[:, None, None]
GRAD_COL = np.float32([22, 8, 18]) / 255


def title_state(ti, tt):
    """Returns per-line (alpha, dy) for a title at global time tt."""
    out = []
    for i in range(len(ti["sprites"])):
        a_in = ease_out((tt - ti["t0"] - i * 0.12) / 0.45)
        a_out = 1 - smooth((tt - (ti["t0"] + ti["dur"] - 0.35)) / 0.35)
        dy = (1 - a_in) * 28 - (1 - a_out) * 10
        out.append((max(0.0, min(a_in, a_out)), dy))
    return out


def draw_titles(img, tt):
    vis = 0.0
    for ti in titles:
        if not (ti["t0"] - 0.05 <= tt <= ti["t0"] + ti["dur"] + 0.05):
            continue
        st = title_state(ti, tt)
        a_max = max(a for a, _ in st)
        if ti["style"] == "hero":
            img *= 1 - 0.22 * a_max
        vis = max(vis, a_max)
    if V and vis > 0:
        img[:] = img * (1 - GRAD * vis) + GRAD_COL * GRAD * vis
    for ti in titles:
        if not (ti["t0"] - 0.05 <= tt <= ti["t0"] + ti["dur"] + 0.05):
            continue
        st = title_state(ti, tt)
        n = len(ti["sprites"])
        top = ti["cy"] - (n - 1) * ti["lh"] / 2
        for i, (spr, (a, dy)) in enumerate(zip(ti["sprites"], st)):
            over(img, spr, TEXT_CX, top + i * ti["lh"] + dy, a)
        a0 = st[0][0]
        over(img, ACCENT, TEXT_CX, top + (n - 1) * ti["lh"] + ti["lh"] * 0.62, a0)


# ---------------------------------------------------------------- end card
C = E["card"]
cs = 118 if V else 104
card_slogan = [text_line(l, font(900, cs), PLUM, C["slogan_hl"], PINK_DEEP, shadow=False) for l in C["slogan"]]
card_cta = [text_line(l, font(700, 64 if V else 54), PLUM_SOFT, (), shadow=False) for l in C["cta"]]
card_brand_en = text_line(C["brand_en"], font(800, 60 if V else 50), PINK_DEEP, shadow=False, tracking=16)
card_brand_ar = text_line(C["brand_ar"], font(700, 66 if V else 54), PLUM, shadow=False)
DIVIDER = bar(170, 6, PINK_DEEP)

# card background: soft blush gradient with two very soft light blooms
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
top_c, bot_c = np.float32([255, 247, 250]) / 255, np.float32([249, 221, 233]) / 255
k = (yy / H)[..., None]
CARD_BG = top_c * (1 - k) + bot_c * k
for (bx, by, rad, amt) in [(0.85, 0.15, 0.55, 0.06), (0.1, 0.9, 0.6, 0.05)]:
    d = np.sqrt(((xx / W - bx) * W / max(W, H)) ** 2 + ((yy / H - by) * H / max(W, H)) ** 2)
    CARD_BG = CARD_BG - (np.exp(-(d / rad) ** 2) * amt)[..., None] * np.float32([0.0, 0.5, 0.25])
CARD_BG = np.clip(CARD_BG, 0, 1).astype(np.float32)
del yy, xx, k


def load_logos():
    """Official logos, used exactly as supplied (uniform scale only, never recoloured)."""
    order = os.path.join(LOGOS, "order.txt")
    if not os.path.exists(order):
        return []
    names = [l.strip() for l in open(order, encoding="utf-8") if l.strip() and not l.startswith("#")]
    out = []
    n = max(len(names), 1)
    max_h = 150 if V else 120
    max_w = ((W - 160) - 60 * (n - 1)) / n if V else (1500 - 60 * (n - 1)) / n
    for nm in names:
        im = Image.open(os.path.join(LOGOS, nm)).convert("RGBA")
        sc = min(max_h / im.height, max_w / im.width)
        im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
        out.append(np.asarray(im, np.float32) / 255)
    return out


LOGO_SPR = load_logos()


def draw_card(img, ct):
    """ct = seconds since card start."""
    img[:] = CARD_BG
    if V:
        y_sl, y_div, y_cta, y_ben, y_bar, y_logo = 690, 880, 1000, 1330, 1430, 1620
    else:
        y_sl, y_div, y_cta, y_ben, y_bar, y_logo = 300, 450, 545, 735, 805, 945
    sl_lh = cs * 1.22
    for i, spr in enumerate(card_slogan):
        a = ease_out((ct - 0.35 - i * 0.15) / 0.6)
        over(img, spr, W / 2, y_sl - sl_lh / 2 + i * sl_lh + (1 - a) * 30, a)
    dw = ease_out((ct - 1.0) / 0.6)
    if dw > 0:
        d = cv2.resize(DIVIDER, (max(2, int(DIVIDER.shape[1] * dw)), DIVIDER.shape[0]))
        over(img, d, W / 2, y_div, 1.0)
    for i, spr in enumerate(card_cta):
        a = ease_out((ct - 1.4 - i * 0.12) / 0.6)
        over(img, spr, W / 2, y_cta + i * (78 if V else 66) + (1 - a) * 20, a)
    a = ease_out((ct - 2.7) / 0.7)
    over(img, card_brand_en, W / 2, y_ben + (1 - a) * 14, a)
    over(img, card_brand_ar, W / 2, y_bar + (1 - a) * 14, a)
    if LOGO_SPR:
        a = ease_out((ct - 3.3) / 0.8)  # soft fade only — no spin, no glow
        gap = 60
        total = sum(l.shape[1] for l in LOGO_SPR) + gap * (len(LOGO_SPR) - 1)
        x = W / 2 + total / 2
        for l in LOGO_SPR:  # order.txt order, laid out right-to-left for Arabic reading
            over(img, l, x - l.shape[1] / 2, y_logo, a)
            x -= l.shape[1] + gap
    # final soft fade to the background colour
    f = smooth((ct - (E["card_dur"] - 0.45)) / 0.45)
    if f > 0:
        img[:] = img * (1 - f) + CARD_BG * f


# ---------------------------------------------------------------- 16:9 layout
def horizontal(plate):
    small = cv2.resize(plate, (1920 // 8, int(1920 / PW * PH) // 8), interpolation=cv2.INTER_AREA)
    oy = (small.shape[0] - 1080 // 8) // 2
    bg = small[oy:oy + 1080 // 8]
    bg = cv2.GaussianBlur(bg, (0, 0), 6)
    bg = cv2.resize(bg, (1920, 1080), interpolation=cv2.INTER_LINEAR)
    bg = bg * 0.38 + np.float32([40, 12, 30]) / 255 * 0.25
    fg = cv2.resize(plate, (FG_W, FG_H), interpolation=cv2.INTER_AREA)
    # soft shadow behind the panel
    sh = np.zeros((1080, 1920), np.float32)
    sh[FG_Y + 10:FG_Y + FG_H + 10, FG_X:FG_X + FG_W] = 1
    sh = cv2.GaussianBlur(sh, (0, 0), 22)[..., None] * 0.55
    bg = bg * (1 - sh)
    bg[FG_Y:FG_Y + FG_H, FG_X:FG_X + FG_W] = fg
    return bg


# ---------------------------------------------------------------- main loop
def main():
    out = os.path.join(BUILD, f"video_{LAYOUT}.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                            "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                            "-profile:v", "high", "-movflags", "+faststart", out],
                           stdin=subprocess.PIPE)
    readers = {}
    still_times = {}
    if STILLS:
        for s in shots:
            still_times[int((s["start"] + s["dur"] * 0.55) * FPS)] = s["id"]
        for ti in titles:
            still_times[int((ti["t0"] + 1.0) * FPS)] = "T_" + str(round(ti["t0"], 1))
        still_times[int((CARD_START + 4.5) * FPS)] = "CARD"
    qc = os.path.join(ROOT, "06_qc", f"stills_{LAYOUT}")
    os.makedirs(qc, exist_ok=True)

    for fi in range(NFR):
        tt = fi / FPS
        layers = []
        for s in shots:
            if s["start"] - 1e-6 <= tt < s["start"] + s["dur"] - 1e-6:
                if s["id"] not in readers:
                    readers[s["id"]] = Reader(s)
                fr = readers[s["id"]].read()
                lt = tt - s["start"]
                w = 1.0
                if s["ov"] and lt > s["dur"] - s["ov"]:
                    w = 1 - smooth((lt - (s["dur"] - s["ov"])) / s["ov"])
                layers.append((push(fr, s, lt), w))
            elif s["id"] in readers and tt >= s["start"] + s["dur"]:
                readers.pop(s["id"]).close()
        # composite plate (outgoing layer fades over the incoming one)
        plate = None
        if layers:
            if len(layers) == 1:
                plate = layers[0][0]
            else:
                (a, wa), (b, _) = layers[0], layers[1]
                plate = a * wa + b * (1 - wa)
            plate = look(plate)
        frame = horizontal(plate) if (plate is not None and not V) else plate
        if tt >= CARD_START:
            card = np.empty((H, W, 3), np.float32)
            draw_card(card, tt - CARD_START)
            if frame is None:
                frame = card
            else:
                last = shots[-1]
                k = smooth((tt - CARD_START) / last["ov"])
                frame = frame * (1 - k) + card * k
        else:
            frame = frame.copy()
            draw_titles(frame, tt)
        u8 = (np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8)
        enc.stdin.write(u8.tobytes())
        if fi in still_times:
            Image.fromarray(u8).save(os.path.join(qc, f"{fi:04d}_{still_times[fi]}.jpg"), quality=90)
        if fi % 150 == 0:
            print(f"{LAYOUT}: frame {fi}/{NFR}", flush=True)
    for r_ in readers.values():
        r_.close()
    enc.stdin.close(); enc.wait()
    json.dump({"total": TOTAL, "card_start": CARD_START,
               "shots": [{k: s[k] for k in ("id", "src", "in", "dur", "start", "chapter", "note")} for s in shots],
               "titles": [{"t0": round(t_["t0"], 2), "dur": t_["dur"]} for t_ in titles]},
              open(os.path.join(BUILD, "timeline.json"), "w"), indent=1)
    print("done", out, f"{TOTAL:.2f}s")


if __name__ == "__main__":
    main()
