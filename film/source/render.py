import subprocess, sys, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import timeline as T

W, H = T.OUT_W, T.OUT_H
SW, SH = 1280, 720
FPS = T.FPS
SRC = {'v1': 'v1.mp4', 'v2': 'v2.mp4'}
rng = np.random.default_rng(7)
random.seed(7)

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)

def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

# ---------- effective clip ranges (outgoing clip continues under the next dissolve) ----------
CL = T.CLIPS
for i, c in enumerate(CL):
    end = c['t'] + c['dur']
    if i + 1 < len(CL):
        n = CL[i + 1]
        end = max(end, n['t'] + n['tin'] + 0.04)
    c['end'] = end

# ---------- looks ----------
x = np.linspace(0, 1, 256)

def curve_hist(v):
    v = 0.035 + v * 0.93
    v = v ** 1.05
    return np.clip(v, 0, 1)

def curve_now(v):
    # gentle S + highlight shoulder for the over-lit hall
    v = v ** 1.10
    s = 0.5 + (v - 0.5) * 1.10
    v = np.where(s > 0.72, 0.72 + (s - 0.72) * 0.62, s)
    v = 0.018 + v * 0.975
    return np.clip(v, 0, 1)

LUT = {
    'hist': np.stack([curve_hist(x) * 1.04, curve_hist(x) * 0.985, curve_hist(x) * 0.88], 1),
    'now': np.stack([curve_now(x) * 1.025, curve_now(x) * 1.0, curve_now(x) * 0.945], 1),
}
LUT = {k: np.clip(v, 0, 1).astype(np.float32) for k, v in LUT.items()}
SAT = {'hist': 0.55, 'now': 0.93}

def grade(img, look, m=None):
    """img uint8 HxWx3 -> float32 graded."""
    if look == 'bridge':
        a = grade(img, 'hist')
        b = grade(img, 'now')
        y = (a * np.float32([0.3, 0.59, 0.11])).sum(2, keepdims=True)
        a = y * np.float32([1.05, 0.97, 0.84]) * 0.92 + 0.02     # archive-tinted monochrome
        return a * (1 - m) + b * m
    lut = LUT[look]
    out = np.empty(img.shape, np.float32)
    for ch in range(3):
        out[..., ch] = lut[img[..., ch], ch]
    y = (out * np.float32([0.299, 0.587, 0.114])).sum(2, keepdims=True)
    out = y + (out - y) * SAT[look]
    if look == 'now':
        # slight warm highlights / neutral shadows
        out += (out - 0.5).clip(0, None) * np.float32([0.03, 0.01, -0.03])
    return out

# v1 edge feather (archive cards blend into the darkness of the frame)
fx = np.ones(SW, np.float32)
r = 150
fx[:r] = np.linspace(0, 1, r) ** 1.5
fx[-r:] = fx[:r][::-1]
fy = np.ones(SH, np.float32)
fy[:24] = np.linspace(0, 1, 24)
fy[-24:] = fy[:24][::-1]
FEATHER = (fy[:, None] * fx[None, :])[..., None]

# ---------- readers ----------
class Reader:
    def __init__(self, c, lt0=0.0):
        self.c = c
        sin = c['sin'] + lt0 * c['speed']
        need = (c['end'] - c['t'] - lt0) * c['speed'] + 0.4
        if 'send' in c:
            need = min(need, c['send'] - sin)
        vf = []
        if c['src'] == 'v2':
            vf.append('delogo=x=1040:y=26:w=190:h=72')
        vf.append(f"setpts=(PTS-STARTPTS)/{c['speed']}")
        if c['mode'] == 'mci':
            vf.append('minterpolate=fps=25:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1')
        elif c['speed'] == 1.0 and c['src'] == 'v2':
            vf.append('fps=25')
        else:
            vf.append('framerate=fps=25')
        cmd = ['ffmpeg', '-v', 'error', '-ss', f"{sin:.3f}", '-t', f'{need:.3f}', '-i', SRC[c['src']],
               '-vf', ','.join(vf), '-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 8)
        self.idx = -1
        self.frame = None

    def get(self, k):
        while self.idx < k:
            buf = self.p.stdout.read(SW * SH * 3)
            if len(buf) < SW * SH * 3:
                break   # hold last frame (freeze)
            self.frame = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
            self.idx += 1
        return self.frame

    def close(self):
        try:
            self.p.kill()
        except Exception:
            pass

def still_frame(c, lt):
    s = c['sin'] + lt * c['speed']
    if 'send' in c:
        s = min(s, c['send'] - 0.05)
    vf = 'delogo=x=1040:y=26:w=190:h=72' if c['src'] == 'v2' else 'null'
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{s:.3f}', '-i', SRC[c['src']], '-frames:v', '1',
                          '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    return np.frombuffer(out, np.uint8).reshape(SH, SW, 3)

# ---------- geometry ----------
def window(c, lt):
    p = ease(lt / max(c['dur'], 1e-3)) * 0.85 + (lt / max(c['dur'], 1e-3)) * 0.15
    p = min(max(p, 0), 1.05)
    cx, cy, h = [a + (b - a) * p for a, b in zip(c['w0'], c['w1'])]
    w = h * W / H
    if c['src'] == 'v2':
        h = min(h, 532)
        w = h * W / H
        cx = min(max(cx, w / 2), SW - w / 2)
        cy = min(max(cy, h / 2), 532 - h / 2)
    return cx, cy, w, h

def place(img_f, c, lt):
    cx, cy, w, h = window(c, lt)
    im = Image.fromarray((np.clip(img_f, 0, 1) * 255 + 0.5).astype(np.uint8))
    a, e = w / W, h / H
    data = (a, 0, cx - w / 2, 0, e, cy - h / 2)
    return np.asarray(im.transform((W, H), Image.AFFINE, data, Image.BICUBIC, fillcolor=(0, 0, 0)), np.float32) / 255

# ---------- texture ----------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2 * 1.15)) ** 2)
VIG = (1 - 0.34 * np.clip(rr, 0, 1.6) ** 2.3).clip(0.45, 1)[..., None].astype(np.float32)

GRAIN = []
for i in range(10):
    n = rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
    im = Image.fromarray(((n * 40) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    GRAIN.append(((np.asarray(im, np.float32) - 128) / 40)[..., None])

LEAKS = [  # (center t, duration, strength, hue)
    (4.5, 5.0, 0.13, 0), (9.9, 2.2, 0.10, 1), (16.3, 2.2, 0.10, 0), (23.1, 2.2, 0.10, 1), (30.5, 2.0, 0.10, 0),
    (35.9, 4.2, 0.42, 0), (44.0, 2.6, 0.40, 2), (MATCH := T.MATCH_T, 1.4, 0.22, 0),
    (T.END_T + 6.0, 9.0, 0.10, 1), (T.TITLE_T + 2.5, 6.0, 0.10, 0),
]
HUES = [np.float32([1.0, 0.52, 0.18]), np.float32([1.0, 0.42, 0.30]), np.float32([1.0, 0.86, 0.62])]
LW, LH = 192, 80
lyy, lxx = np.mgrid[0:LH, 0:LW].astype(np.float32)

def leak(tf):
    acc = None
    for (tc, d, s, hue) in LEAKS:
        u = (tf - (tc - d / 2)) / d
        if not 0 <= u <= 1:
            continue
        env = math.sin(math.pi * u) ** 1.5 * s
        cx = LW * (-0.15 + 1.3 * u) if hue != 1 else LW * (1.15 - 1.3 * u)
        cy = LH * (0.35 + 0.15 * math.sin(tc))
        g = np.exp(-(((lxx - cx) / (LW * 0.32)) ** 2 + ((lyy - cy) / (LH * 0.9)) ** 2))
        g2 = np.exp(-(((lxx - cx * 0.6 - LW * 0.2) / (LW * 0.18)) ** 2 + ((lyy - LH * 0.8) / (LH * 0.5)) ** 2)) * 0.5
        l = (g + g2)[..., None] * HUES[hue] * env
        acc = l if acc is None else acc + l
    if acc is None:
        return None
    im = Image.fromarray((acc.clip(0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255

def dust(img, k, frame_no):
    if k <= 0.02:
        return img
    ov = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(ov)
    rs = random.Random(frame_no * 7919)
    for _ in range(rs.randint(0, 4)):
        x0, y0 = rs.uniform(0, W), rs.uniform(0, H)
        rad = rs.uniform(0.8, 2.6)
        d.ellipse([x0 - rad, y0 - rad, x0 + rad, y0 + rad], fill=rs.randint(120, 255))
    if rs.random() < 0.06:   # occasional hair
        x0, y0 = rs.uniform(0, W), rs.uniform(0, H)
        pts = [(x0 + i * 3 + 10 * math.sin(i / 4), y0 + i * 2.2) for i in range(rs.randint(8, 22))]
        d.line(pts, fill=rs.randint(120, 220), width=1)
    if rs.random() < 0.05:   # faint vertical scratch
        x0 = rs.uniform(W * 0.1, W * 0.9)
        d.line([(x0, 0), (x0 + rs.uniform(-6, 6), H)], fill=70, width=1)
    m = np.asarray(ov.filter(ImageFilter.GaussianBlur(0.7)), np.float32)[..., None] / 255 * k
    # specks are dark on bright areas, light on dark areas (like real print dust)
    lum = img.mean(2, keepdims=True)
    return img * (1 - m) + np.where(lum > 0.45, 0.08, 0.85) * m

# end card: municipal seal cropped from the real banner
SEAL = None
def seal():
    global SEAL
    if SEAL is None:
        f = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '1.0', '-i', 'v2.mp4', '-frames:v', '1', '-f', 'rawvideo',
                            '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
        a = np.frombuffer(f, np.uint8).reshape(SH, SW, 3)
        crop = Image.fromarray(a[48:174, 168:300].copy()).resize((264, 252), Image.LANCZOS)
        mk = Image.new('L', crop.size, 0)
        ImageDraw.Draw(mk).ellipse([8, 6, crop.size[0] - 8, crop.size[1] - 6], fill=255)
        mk = mk.filter(ImageFilter.GaussianBlur(6))
        SEAL = (np.asarray(crop, np.float32) / 255, np.asarray(mk, np.float32)[..., None] / 255)
    return SEAL

# scrim masks
_rx = ((xx - W) / (W * 0.62)) ** 2 + ((yy - H) / (H * 0.55)) ** 2
SCRIM_BR = np.exp(-_rx * 1.4)[..., None].astype(np.float32)
_cy = ((yy - H * 0.5) / (H * 0.42)) ** 2
SCRIM_C = (0.55 + 0.45 * np.exp(-_cy * 1.2))[..., None].astype(np.float32)
SCRIMS = [
    (T.TEXTS['najla'][0], T.TEXTS['najla'][1], SCRIM_BR, 0.75),
    (T.TEXTS['zahra'][0], T.TEXTS['zahra'][1], SCRIM_BR, 0.75),
    (T.TEXTS['e1'][0] - 0.4, T.TEXTS['e2'][1], SCRIM_C, 0.72),
]

def hist_weight(active):
    return sum(al for c, al in active if c['look'] == 'hist') + \
        sum(al * (1 - bridge_m(c, tf_glob - c['t'])) for c, al in active if c['look'] == 'bridge')

def bridge_m(c, lt):
    return smooth((lt / c['dur'] - 0.25) / 0.6)

tf_glob = 0.0

def render_frame(tf, fetch, frame_no):
    global tf_glob
    tf_glob = tf
    out = np.zeros((H, W, 3), np.float32)
    active = []
    for c in CL:
        if c['t'] <= tf < c['end']:
            lt = tf - c['t']
            al = 1.0 if c['tin'] <= 0 else ease(lt / c['tin'])
            if 'fade_to_black' in c:
                a, b = c['fade_to_black']
                al *= 1 - ease((tf - a) / (b - a))
            src = fetch(c, lt)
            if src is None:
                continue
            m = bridge_m(c, lt) if c['look'] == 'bridge' else None
            g = grade(src, c['look'], m)
            if c['src'] == 'v1':
                g = g * FEATHER
            p = place(g, c, lt)
            if c.get('bloom') and lt < 1.8:
                k = math.sin(math.pi * min(lt / 1.8, 1)) ** 2 * 0.55
                p = 1 - (1 - p) * (1 - k * np.float32([1.0, 0.9, 0.75]))
            out = out * (1 - al) + p * al
            active.append((c, al))
    hw = min(1.0, sum(al for c, al in active if c['look'] == 'hist') +
             sum(al * (1 - bridge_m(c, tf - c['t'])) for c, al in active if c['look'] == 'bridge'))
    # end card seal
    s0, s1 = T.TEXTS['seal']
    if s0 - 0.8 <= tf <= s1 + 0.8:
        a = ease((tf - s0 + 0.8) / 1.2) * (1 - ease((tf - s1) / 0.8))
        img, mk = seal()
        h_, w_ = img.shape[:2]
        y0, x0 = 170, (W - w_) // 2
        reg = out[y0:y0 + h_, x0:x0 + w_]
        out[y0:y0 + h_, x0:x0 + w_] = reg * (1 - mk * a) + grade((img * 255).astype(np.uint8), 'now') * mk * a
    # scrims behind lower-thirds and closing lines
    for (a, b, mask, depth) in SCRIMS:
        if a - 0.6 <= tf <= b + 0.6:
            k = ease((tf - a + 0.6) / 0.8) * (1 - ease((tf - b) / 0.6)) * depth
            out = out * (1 - mask * k)
    l = leak(tf)
    if l is not None:
        out = 1 - (1 - out) * (1 - l)
    out = dust(out, hw * 0.9, frame_no)
    lum = out.mean(2, keepdims=True)
    amp = 0.022 + 0.026 * hw
    out = out + GRAIN[frame_no % 10 if frame_no % 3 else (frame_no * 7) % 10] * amp * (0.35 + 0.65 * (1 - np.abs(lum - 0.45) * 1.6).clip(0, 1))
    # subtle gate weave on archive
    out = out * VIG
    return np.clip(out, 0, 1)

def main():
    mode = sys.argv[1]
    if mode == 'stills':
        times = [float(a) for a in sys.argv[2:]]
        for tf in times:
            fr = render_frame(tf, lambda c, lt: still_frame(c, lt), int(tf * FPS))
            full = np.zeros((T.FRAME_H, W, 3), np.uint8)
            full[T.BAR:T.BAR + H] = (fr * 255).astype(np.uint8)
            Image.fromarray(full).save(f'still_{tf:06.2f}.png')
            print('still', tf)
        return
    # full render -> raw rgb on stdout
    t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    t1 = float(sys.argv[3]) if len(sys.argv) > 3 else T.FILM_END
    readers = {}
    def fetch(c, lt):
        key = id(c)
        if key not in readers:
            readers[key] = Reader(c, lt)
            readers[key].start_lt = lt
        rd = readers[key]
        k = int(round((lt - rd.start_lt) * FPS))
        return rd.get(k)
    out = sys.stdout.buffer
    n0, n1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    for n in range(n0, n1):
        tf = n / FPS
        # clips that start before t0 must begin reading at their offset
        for c in CL:
            if id(c) not in readers and c['t'] < tf < c['end'] and tf - c['t'] > 0.001:
                pass
        fr = render_frame(tf, fetch, n)
        out.write((fr * 255 + 0.5).astype(np.uint8).tobytes())
        for c in CL:
            if id(c) in readers and tf >= c['end']:
                readers[id(c)].close()
                del readers[id(c)]
        if n % 50 == 0:
            print(f'frame {n}/{n1}', file=sys.stderr, flush=True)

if __name__ == '__main__':
    main()
