# Original score synthesised from scratch: ambient piano -> warm strings -> soft cinematic
# percussion -> orchestral rise -> silence -> piano + strings. Hope, not fear.
import json
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
TL = json.load(open("timeline.json"))
C = TL["cues"]
N = int((C["total"] + 4) * SR)
rng = np.random.default_rng(7)
BPM = 72.0
BEAT = 60 / BPM
BAR = 4 * BEAT
T0 = C["first"]


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def env_curve(points):
    """piecewise-linear gain curve over the whole timeline: [(t, g), ...]"""
    t = np.arange(N) / SR
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def section(t):
    order = ["first", "ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "climax", "stop", "ending", "endcard"]
    cur = "pre"
    for k in order:
        if t >= C[k] - 0.05:
            cur = k
    return cur


VOI = {
    "C": [48, 55, 60, 64, 67], "G": [43, 50, 59, 62, 67], "Am": [45, 52, 57, 60, 64],
    "F": [41, 48, 57, 60, 65], "Em": [40, 47, 55, 59, 64], "Dm": [38, 50, 57, 60, 65],
    "Fmaj7": [41, 48, 57, 60, 64], "Csus": [48, 55, 60, 62, 67],
}
PROG = {
    "pre": ["Am", "Fmaj7", "C", "G"], "first": ["Am", "Fmaj7", "C", "G"],
    "ch1": ["Am", "Fmaj7", "C", "G"], "ch2": ["F", "C", "G", "Am"],
    "ch3": ["C", "G", "Am", "F"], "ch4": ["C", "G", "Am", "F"], "ch5": ["F", "C", "G", "Am"],
    "ch6": ["Fmaj7", "C", "Am", "G"], "climax": ["F", "G", "C", "Am"],
    "stop": ["Am", "Am", "Fmaj7", "Fmaj7", "C", "C", "G", "G"],
    "ending": ["F", "G", "Am", "F", "C", "G"], "endcard": ["F", "G", "Am", "Fmaj7", "F", "G", "Csus", "C", "C"],
}

# bar grid
bars = []
t = T0
counter = {}
while t < C["total"] + BAR:
    sec = section(t + 0.3)
    k = counter.get(sec, 0)
    counter[sec] = k + 1
    p = PROG[sec]
    ch = p[min(k, len(p) - 1)] if sec == "endcard" else p[k % len(p)]
    bars.append((t, sec, ch))
    t += BAR
# force final resolution to C on the last bars
L = len(bars)

piano = np.zeros(N); pad = np.zeros(N); hi_str = np.zeros(N); low_str = np.zeros(N)
perc = np.zeros(N); fx = np.zeros(N)


def add(buf, start, sig):
    i = int(start * SR)
    if i >= N or i + len(sig) <= 0:
        return
    j = min(N, i + len(sig))
    if i < 0:
        sig = sig[-i:]; i = 0
    buf[i:j] += sig[: j - i]


def piano_note(m, vel=0.5, length=4.0):
    f = mtof(m)
    n = int(length * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    B = 0.00035
    for h in range(1, 14):
        fh = h * f * np.sqrt(1 + B * h * h)
        if fh > 9000:
            break
        amp = (1 / h ** 1.25) * (0.6 + 0.4 * vel) ** (h * 0.35)
        dec = np.exp(-t * (0.55 + 0.35 * h) * (0.6 + f / 900))
        out += amp * dec * np.sin(2 * np.pi * fh * t + rng.uniform(0, 6.28))
    atk = np.minimum(1, t / 0.004)
    rel = np.minimum(1, (length - t) / 0.4).clip(0)
    hammer = lp(rng.standard_normal(n) * np.exp(-t * 90), 2500) * 0.08
    return (out * atk * rel + hammer) * vel * 0.22


def saw_voice(f, n, detune_cents=(-7, 0, 6), vib=0.0035):
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for dc in detune_cents:
        fr = f * 2 ** (dc / 1200) * (1 + vib * np.sin(2 * np.pi * (4.8 + rng.uniform(-.4, .4)) * t + rng.uniform(0, 6)))
        ph = np.cumsum(fr) / SR + rng.uniform(0, 1)
        sig += 2 * (ph % 1.0) - 1
    return sig / len(detune_cents)


def string_chord(notes, dur, atk=1.2, rel=1.8, cutoff=2200, gain=0.12):
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in notes:
        s += saw_voice(mtof(m), n)
    s = lp(s, cutoff, 2)
    s = hp(s, 70, 1)
    e = np.minimum(1, t / atk) * np.clip((dur + rel - t) / rel, 0, 1) ** 1.5
    return s * e * gain / np.sqrt(len(notes))


# ---------------- writing the parts
for bi, (bt, sec, ch) in enumerate(bars):
    v = VOI[ch]
    last = bi == L - 1
    # warm pad (from first, everywhere except the stop gap)
    pad_notes = v[1:]
    add(pad, bt, string_chord(pad_notes, BAR + 0.3, atk=1.6, rel=2.2, cutoff=1500, gain=0.10))
    # high strings (ch3 onwards, ending)
    if sec in ("ch3", "ch4", "ch5", "ch6", "climax", "ending", "endcard"):
        top = [v[3] + 12, v[4] + 12] if sec != "ch6" else [v[4] + 12]
        add(hi_str, bt, string_chord(top, BAR + 0.2, atk=0.9, rel=1.6, cutoff=3800, gain=0.09))
    if sec in ("ch3", "ch4", "ch5", "climax", "ending", "endcard"):
        add(low_str, bt, string_chord([v[0], v[0] - 12], BAR + 0.1, atk=0.4, rel=1.2, cutoff=900, gain=0.16))
    # piano
    if sec in ("pre", "first"):
        # sparse, high, spacious single notes
        for k, (b, m) in enumerate([(0, v[4] + 12), (2, v[3] + 12)]):
            add(piano, bt + b * BEAT, piano_note(m, 0.32, 5.0))
    elif sec in ("ch1", "ch2", "ch6", "ending"):
        pat = [v[0], v[2], v[3] + 12, v[2] + 12]
        add(piano, bt, piano_note(v[0] - 12 if v[0] > 40 else v[0], 0.38, 5))
        for k, m in enumerate(pat):
            add(piano, bt + k * BEAT, piano_note(m + 12 if k else m + 12, 0.33 + 0.05 * (k == 2), 4.0))
    elif sec in ("ch3", "ch4", "ch5", "climax"):
        pat = [v[2], v[3], v[4], v[3] + 12, v[4] + 12, v[3] + 12, v[4], v[3]]
        add(piano, bt, piano_note(v[0], 0.45, 4))
        vel = 0.42 if sec != "climax" else 0.55
        for k, m in enumerate(pat):
            add(piano, bt + k * BEAT / 2, piano_note(m + 12, vel * (1.0 if k % 2 == 0 else 0.8), 2.5))
    elif sec == "stop":
        # after the silence: one quiet chord per two bars, very soft
        if bt > C["stop"] + 1.2 and (bi % 2 == 0):
            for k, m in enumerate([v[0], v[2] + 12, v[3] + 12, v[4] + 12]):
                add(piano, bt + 0.06 * k, piano_note(m, 0.30, 6.0))
    elif sec == "endcard":
        if last:
            for k, m in enumerate([36, 48, 55, 64, 67, 72, 76]):
                add(piano, bt + 0.05 * k, piano_note(m, 0.4, 8.0))
        else:
            pat = [v[0], v[2], v[3] + 12, v[2] + 12]
            for k, m in enumerate(pat):
                add(piano, bt + k * BEAT, piano_note(m + 12, 0.36, 4.0))


# ---------------- percussion
def drum(f0=58, dec=7.0, vel=1.0, length=1.6):
    n = int(length * SR); t = np.arange(n) / SR
    f = f0 * (1 + 1.4 * np.exp(-t * 28))
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * dec)
    skin = lp(rng.standard_normal(n), 900) * np.exp(-t * 35) * 0.35
    return (body + skin) * vel * 0.5


def shaker(vel=1.0):
    n = int(0.12 * SR); t = np.arange(n) / SR
    return bp(rng.standard_normal(n), 5000, 11000) * np.exp(-t * 45) * np.minimum(1, t / 0.01) * vel * 0.05


for bi, (bt, sec, ch) in enumerate(bars):
    if sec in ("ch3", "ch4", "ch5"):
        add(perc, bt, drum(55, 6, 0.55))
        add(perc, bt + 2 * BEAT, drum(55, 6, 0.4))
        add(perc, bt + 3.5 * BEAT, drum(70, 9, 0.18))
        if sec != "ch3":
            for k in range(8):
                add(perc, bt + k * BEAT / 2, shaker(0.6 if k % 2 else 1.0))
    elif sec == "climax":
        for k in range(4):
            add(perc, bt + k * BEAT, drum(52, 5.5, 0.75 if k % 2 == 0 else 0.5))
        for k in range(8):
            add(perc, bt + k * BEAT / 2, shaker(1.0))
        for k in range(4):
            add(perc, bt + 3 * BEAT + k * BEAT / 4, drum(85 - 6 * k, 10, 0.25 + 0.06 * k))
    elif sec in ("ending", "endcard") and bt < C["endcard"] + 10:
        add(perc, bt, drum(50, 4.5, 0.35))


# ---------------- sound design: whooshes, riser, impacts
def whoosh(length=1.6, vel=1.0):
    n = int(length * SR); t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    e = np.sin(np.pi * t / length) ** 2.2
    dark = bp(noise, 250, 1400, 2); bright = bp(noise, 1400, 6500, 2)
    return (dark * e + bright * e ** 3) * vel * 0.2


def riser(length):
    n = int(length * SR); t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    p = t / length
    x = bp(noise, 300, 1500, 2) * p ** 1.5 + bp(noise, 1500, 9000, 2) * p ** 4
    tone = sum(np.sin(2 * np.pi * np.cumsum(mtof(m) * (1 + 0.5 * p ** 2)) / SR) for m in (60, 67, 72)) / 3
    return (x * 0.5 + tone * 0.08 * p ** 2.2) * 0.35


def impact(vel=1.0):
    n = int(4.0 * SR); t = np.arange(n) / SR
    f = 42 * (1 + 0.8 * np.exp(-t * 12))
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    air = lp(rng.standard_normal(n), 2500) * np.exp(-t * 4) * 0.25
    return (sub + air) * vel * 0.45


for w in TL["whoosh"]:
    add(fx, w - 0.8, whoosh(1.6, 0.8))
add(fx, C["stop"] - 4.0, riser(4.0))
add(fx, C["climax"] - 0.02, impact(0.55))
add(fx, C["title"] - 0.05, impact(0.7))
add(fx, C["first"] + 0.3, whoosh(3.5, 0.35))

# ambient "air" bed
air = lp(hp(rng.standard_normal(N), 200), 1800) * 0.025

# ---------------- dynamics / arrangement automation (gain curves)
s, e = C["stop"], C["total"]
mute = [(s - 0.02, 1), (s + 0.02, 0)]
G = {}
G["piano"] = env_curve([(0, 1), (C["ch3"], 1), (C["climax"], 1.1)] + [(s - 0.02, 1.1), (s + 0.02, 0),
                                                                          (s + 1.1, 0), (s + 1.3, 0.9), (e, 0.9)])
G["pad"] = env_curve([(0, 0), (C["first"] + 0.5, 0), (C["first"] + 6, 0.7), (C["ch1"], 0.9), (C["ch3"], 1.0),
                      (C["climax"], 1.2), (s - 0.02, 1.25), (s + 0.02, 0), (s + 3, 0), (s + 7, 0.55),
                      (C["ending"], 0.8), (C["endcard"], 1.0), (e - 3, 1.0), (e, 0)])
G["hi"] = env_curve([(0, 0), (C["ch3"] - 1, 0), (C["ch3"] + 3, 0.8), (C["ch5"], 1.0), (C["ch6"], 0.7),
                     (C["climax"] - 3, 1.0), (C["climax"], 1.4), (s - 0.02, 1.5), (s + 0.02, 0),
                     (C["ending"], 0), (C["ending"] + 4, 0.8), (C["endcard"], 1.1), (C["title"], 1.3),
                     (e - 4, 1.0), (e, 0)])
G["low"] = env_curve([(0, 0), (C["ch3"], 0), (C["ch3"] + 2, 0.8), (C["ch6"], 0.8), (C["ch6"] + 1, 0),
                      (C["climax"] - 0.5, 0), (C["climax"], 1.2), (s - 0.02, 1.2), (s + 0.02, 0),
                      (C["ending"] + 2, 0), (C["ending"] + 6, 0.8), (C["title"], 1.1), (e - 4, 0.8), (e, 0)])
G["perc"] = env_curve([(0, 1), (s - 0.02, 1), (s + 0.02, 0), (C["ending"], 0), (C["ending"] + 0.1, 1), (e, 1)])
G["air"] = env_curve([(0, 0), (C["first"], 0), (C["first"] + 3, 1.0), (C["ch3"], 0.6), (s - 0.02, 0.5),
                      (s + 0.02, 0), (s + 1.5, 0), (s + 4, 0.8), (C["ending"], 0.5), (e, 0)])

dry = (piano * G["piano"] + pad * G["pad"] + hi_str * G["hi"] + low_str * G["low"] +
       perc * G["perc"] + air * G["air"])


# ---------------- stereo hall reverb (convolution, decorrelated L/R)
def ir(seconds=3.6, seed=0):
    r = np.random.default_rng(seed)
    n = int(seconds * SR); t = np.arange(n) / SR
    x = r.standard_normal(n) * np.exp(-t * 6.9 / seconds)
    x = lp(x, 7000) * np.minimum(1, t / 0.015)
    return x / np.sqrt(np.sum(x ** 2))


wetL = fftconvolve(dry, ir(3.6, 1))[:N]
wetR = fftconvolve(dry, ir(3.6, 2))[:N]
fxL = fftconvolve(fx, ir(2.2, 3))[:N] * 0.4 + fx
fxR = fftconvolve(fx, ir(2.2, 4))[:N] * 0.4 + fx
# gentle stereo: piano slightly left, strings slightly right
L_ = dry * 0.62 + piano * G["piano"] * 0.08 + wetL * 0.55 + fxL
R_ = dry * 0.62 + (hi_str * G["hi"]) * 0.08 + wetR * 0.55 + fxR
st = np.stack([L_, R_], 1)
st = st / (np.max(np.abs(st)) + 1e-9) * 0.7
np.save("music.npy", st.astype(np.float32))
print("music done", st.shape[0] / SR, "s")
