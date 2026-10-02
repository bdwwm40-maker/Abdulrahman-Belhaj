#!/usr/bin/env python3
"""Original documentary score for the opening of "قصص كفاح المرأة".

Everything is synthesised from scratch with numpy (no samples, no copyrighted
material): a distant heartbeat pulse and projector clatter, a single quiet
note, then low piano, strings, a deep drone and soft percussion that build
with the four portraits and peak on "بل كنَّ جزءًا من صناعته." (t = 50.5 s).

Writes output/score.wav (48 kHz, 24-bit stereo) and stems for the editor.
"""
import os
import wave

import numpy as np

SR = 48000
DUR = 60.0
TAIL = 2.0
N = int((DUR + TAIL) * SR)
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
rng = np.random.default_rng(7)
T = np.arange(N) / SR


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def sl(t0, t1):
    a, b = max(0, int(t0 * SR)), min(N, int(t1 * SR))
    return slice(a, b)


def fft_filter(x, lo=None, hi=None, order=2):
    """Zero-phase Butterworth-shaped band filter applied in the frequency domain."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if hi:
        g /= np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        g /= np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * g, len(x))


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def curve(points):
    """Piecewise-linear automation curve over the whole timeline."""
    ts, vs = zip(*points)
    return np.interp(T, ts, vs)


def pan(mono, p):
    """Equal-power pan, p in [-1, 1]."""
    a = (p + 1) * np.pi / 4
    return np.stack([mono * np.cos(a), mono * np.sin(a)])


# ---------------------------------------------------------------- instruments
def piano(buf, t0, m, vel, p=0.0, length=6.0):
    f0 = midi(m)
    s = sl(t0, t0 + length)
    t = T[s] - t0
    B = 0.00035
    x = np.zeros_like(t)
    for n in range(1, 11):
        fn = n * f0 * np.sqrt(1 + B * n * n)
        if fn > 12000:
            break
        amp = (1 / n ** 1.15) * (1.0 if n > 1 else 1.2)
        dec = np.exp(-t * (0.45 + 0.35 * n) * (0.6 + f0 / 900))
        x += amp * dec * np.sin(2 * np.pi * fn * t + rng.uniform(0, 6.28))
    att = smoothstep(t / 0.006)
    hammer = rng.standard_normal(len(t)) * np.exp(-t * 90) * 0.04
    x = (x * att + hammer) * vel * 0.22
    x[-2000:] *= np.linspace(1, 0, 2000)
    buf[:, s] += pan(x, p)


def strings(buf, t0, t1, notes, amp, attack=1.6, release=2.2, bright=1.0):
    s = sl(t0, t1 + release)
    t = T[s] - t0
    env = smoothstep(t / attack) * np.clip(1 - (t - (t1 - t0)) / release, 0, 1) ** 1.5
    for i, m in enumerate(notes):
        f0 = midi(m)
        for v, (det, p) in enumerate([(-7, -0.7), (0, 0.0), (6, 0.7)]):
            f = f0 * 2 ** (det / 1200)
            vib = 1 + 0.0028 * np.sin(2 * np.pi * (4.6 + 0.3 * v) * t + v) * smoothstep((t - 0.8) / 1.5)
            phase = 2 * np.pi * np.cumsum(f * vib) / SR
            x = np.zeros_like(t)
            for h in range(1, 24):
                if h * f > 9000:
                    break
                x += np.sin(h * phase + rng.uniform(0, 6.28)) / h ** (1.9 - 0.4 * bright)
            # slow bow-pressure swell per voice
            x *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.13 * t + i + v)
            buf[:, s] += pan(x * env * amp / (len(notes) ** 0.6) * 0.33, p * (0.4 + 0.12 * i))


def pure_tone(buf, t0, t1, m, amp, attack=3.0, release=3.0):
    s = sl(t0, t1 + release)
    t = T[s] - t0
    f = midi(m)
    env = smoothstep(t / attack) * np.clip(1 - (t - (t1 - t0)) / release, 0, 1) ** 2
    trem = 1 + 0.12 * np.sin(2 * np.pi * 0.35 * t)
    x = (np.sin(2 * np.pi * f * t) + 0.18 * np.sin(4 * np.pi * f * t + 1) + 0.05 * np.sin(6 * np.pi * f * t)) * env * trem * amp
    buf[:, s] += np.stack([x * 0.95, x])


def hit(buf, t0, vel, p=0.0):
    s = sl(t0, t0 + 3.0)
    t = T[s] - t0
    f = 46 + 42 * np.exp(-t * 9)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    skin = fft_filter(rng.standard_normal(len(t)), hi=260) * np.exp(-t * 14) * 0.9
    click = rng.standard_normal(len(t)) * np.exp(-t * 300) * 0.05
    x = (body + skin + click) * smoothstep(t / 0.004) * vel * 0.55
    buf[:, s] += pan(x, p)


def heartbeat(buf, t0, t1, every=1.55):
    t = t0
    while t < t1:
        for dt, a in ((0, 1.0), (0.29, 0.65)):
            s = sl(t + dt, t + dt + 0.6)
            u = T[s] - (t + dt)
            f = 48 + 20 * np.exp(-u * 30)
            x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-u * 11) * smoothstep(u / 0.008) * a
            buf[:, s] += np.stack([x, x])
        t += every


def projector(n):
    """Film-projector clatter: band-limited noise gated at 24 Hz with jitter."""
    noise = fft_filter(rng.standard_normal(n), lo=900, hi=5200)
    t = np.arange(n) / SR
    ph = (t * 24 + 0.02 * np.sin(2 * np.pi * 0.7 * t)) % 1.0
    gate = np.exp(-ph * 26) + 0.25 * np.exp(-((ph - 0.5) % 1.0) * 40)
    hum = 0.25 * np.sin(2 * np.pi * 48 * t) * fft_filter(rng.standard_normal(n), hi=3) * 4
    return noise * gate + hum * 0.2


def reverb(x, rt60=3.4, mix=0.32):
    L = int(4.5 * SR)
    t = np.arange(L) / SR
    out = np.zeros_like(x)
    for c in range(2):
        ir = rng.standard_normal(L) * np.exp(-6.9 * t / rt60)
        ir = fft_filter(ir, lo=120, hi=5500)
        ir[: int(0.025 * SR)] = 0
        ir /= np.sqrt(np.sum(ir ** 2))
        n = len(x[c]) + L
        nfft = 1 << (n - 1).bit_length()
        wet = np.fft.irfft(np.fft.rfft(x[c], nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x[c])]
        out[c] = x[c] * (1 - mix) + wet * mix * 1.6
    return out


# ---------------------------------------------------------------- the score
def build():
    st = {k: np.zeros((2, N)) for k in ("pulse", "tone", "piano", "strings", "drone", "perc", "fx")}

    # 0 s — darkness: a distant pulse and the projector starting up
    heartbeat(st["pulse"], 0.6, 14.0)
    st["pulse"] *= curve([(0, 0), (2.5, 0.32), (9, 0.3), (13.5, 0), (DUR + TAIL, 0)])
    proj = projector(N) * curve([(0, 0), (1.0, 0.05), (4.5, 0.045), (8, 0.012), (40, 0.008),
                                 (55, 0.008), (58.5, 0.03), (60, 0.0), (DUR + TAIL, 0)])
    st["fx"] += np.stack([proj, np.roll(proj, 300)])

    # 1.5 s — one quiet, held note
    pure_tone(st["tone"], 1.5, 22.0, 74, 0.05, attack=3.5, release=4.0)

    # piano: sparse motif following the four women (D minor)
    P = [(4.6, 50, .55, -.2), (4.6, 57, .38, -.1), (5.9, 69, .34, .15), (7.2, 65, .30, .1), (8.5, 64, .28, .05),
         (9.8, 62, .32, 0), (11.1, 57, .24, -.1), (12.2, 65, .22, .1),
         (13.0, 46, .48, -.2), (13.0, 53, .30, -.1), (14.3, 74, .30, .2), (15.5, 72, .27, .15), (16.7, 70, .27, .1),
         (17.6, 43, .45, -.2), (17.6, 50, .30, -.1), (18.8, 70, .28, .1), (20.0, 69, .26, .15), (21.2, 67, .26, .1),
         (22.3, 41, .50, -.2), (22.3, 48, .32, -.1), (23.5, 69, .30, .1), (24.7, 72, .30, .15), (25.9, 77, .30, .2),
         (26.6, 48, .45, -.2), (26.6, 55, .30, -.1), (27.8, 76, .28, .15), (29.0, 74, .28, .1), (30.2, 72, .26, .05),
         (31.0, 38, .62, -.25), (31.0, 45, .45, -.15), (31.0, 62, .32, .1), (32.2, 77, .32, .2), (33.4, 76, .30, .15),
         (34.6, 74, .30, .1), (35.5, 34, .55, -.25), (35.5, 46, .40, -.1), (36.7, 74, .30, .1), (37.9, 77, .32, .15),
         (39.1, 79, .30, .2),
         (40.6, 43, .55, -.25), (40.6, 50, .40, -.1), (41.6, 70, .30, .1), (42.6, 74, .30, .15), (43.6, 45, .55, -.25),
         (43.6, 52, .40, -.1), (44.6, 73, .30, .1), (45.6, 76, .30, .15), (46.6, 81, .22, .2),
         (47.5, 46, .55, -.2), (47.5, 53, .40, -.1), (48.0, 74, .28, .1), (49.0, 48, .60, -.2), (49.0, 55, .42, -.1),
         (50.5, 38, .95, -.3), (50.5, 50, .75, -.15), (50.5, 57, .6, 0), (50.5, 65, .55, .1), (50.5, 69, .55, .15),
         (50.5, 74, .55, .25), (52.0, 69, .32, .1), (53.4, 65, .26, 0),
         (55.0, 50, .40, -.15), (55.0, 57, .30, 0), (56.3, 69, .24, .1), (57.6, 74, .18, .15), (58.8, 62, .14, 0)]
    for t0, m, v, p in P:
        piano(st["piano"], t0, m, v, p)

    # strings: enter with the second portrait and grow with each generation
    S = [(13.0, 17.8, [46, 53, 62], .10), (17.5, 22.5, [43, 50, 58, 62], .12),
         (22.2, 26.8, [41, 48, 57, 65], .14), (26.5, 31.2, [48, 55, 64, 67], .16),
         (31.0, 35.7, [38, 50, 57, 65, 69], .19), (35.5, 40.7, [34, 46, 62, 65, 70], .21),
         (40.5, 43.8, [43, 50, 58, 67, 70], .23), (43.5, 47.7, [45, 52, 61, 64, 69], .25),
         (47.5, 49.2, [46, 53, 62, 65, 70], .27), (49.0, 50.7, [48, 55, 64, 67, 72], .31)]
    for t0, t1, notes, a in S:
        strings(st["strings"], t0, t1, notes, a)
    # climax and resolution
    strings(st["strings"], 50.5, 54.2, [38, 50, 57, 62, 65, 69, 74, 77, 81], .50, attack=0.35, release=3.2, bright=1.4)
    strings(st["strings"], 54.8, 59.0, [50, 57, 62, 69], .13, attack=2.0, release=2.6)

    # deep drone (D pedal)
    d = np.zeros(N)
    for f, a in ((midi(26), 1.0), (midi(38), 0.7), (midi(45), 0.35)):
        d += a * np.sin(2 * np.pi * f * T + 0.3 * np.sin(2 * np.pi * 0.07 * T))
    d = fft_filter(np.tanh(d * 1.4) + fft_filter(rng.standard_normal(N), hi=140) * 1.2, lo=32)
    d *= curve([(0, 0), (21.5, 0), (25, .10), (31, .16), (40.5, .19), (47.5, .22), (50.3, .30), (51.5, .26),
                (54.5, .10), (58, .05), (60, 0), (DUR + TAIL, 0)])
    st["drone"] += np.stack([d, np.roll(d, 480)])

    # soft percussion: generations, prints, climax
    for t0, v in ((31.0, .35), (35.5, .35), (40.6, .45), (41.6, .28), (42.6, .3), (43.6, .34), (45.6, .34),
                  (47.5, .42), (49.0, .5), (49.8, .42), (50.5, 1.0), (55.0, .26)):
        hit(st["perc"], t0, v)
    sw = fft_filter(rng.standard_normal(N), lo=2500, hi=9000)
    sw *= curve([(0, 0), (48.4, 0), (50.45, 0.07), (50.55, 0.0), (DUR + TAIL, 0)])
    st["fx"] += np.stack([sw, np.roll(sw, 200)])

    gains = {"pulse": 1.0, "tone": 1.0, "piano": 1.0, "strings": 1.0, "drone": 0.6, "perc": 0.9, "fx": 1.0}
    stems = {k: reverb(v * gains[k], mix=0.18 if k in ("pulse", "fx") else 0.33) for k, v in st.items()}
    mix = sum(stems.values())
    master = curve([(0, 1), (DUR - 1.0, 1), (DUR + 1.5, 0), (DUR + TAIL, 0)])
    mix *= master
    peak = np.max(np.abs(mix))
    norm = 0.89 / peak  # -1 dBFS
    return mix * norm, {k: v * master * norm for k, v in stems.items()}


def write_wav(path, x):
    x = x[:, : int(DUR * SR)]
    x = np.clip(x + rng.uniform(-1, 1, x.shape) / 2 ** 23, -1, 1)
    i = (x.T * (2 ** 23 - 1)).astype(np.int32).reshape(-1)
    b = np.zeros((len(i), 3), np.uint8)
    b[:, 0], b[:, 1], b[:, 2] = i & 255, (i >> 8) & 255, (i >> 16) & 255
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(b.tobytes())


if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "stems"), exist_ok=True)
    mix, stems = build()
    write_wav(os.path.join(OUT, "score.wav"), mix)
    for k, v in stems.items():
        write_wav(os.path.join(OUT, "stems", f"{k}.wav"), v)
    print("wrote", os.path.join(OUT, "score.wav"))
