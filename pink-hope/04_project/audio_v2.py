#!/usr/bin/env python3
"""PINK HOPE v2 — 120 BPM soundtrack, synthesised in code (no samples, no third-party music).

Structure follows the edit (edit_v2.json, in beats):
  intro (plucks open up, typing ticks, flash hit) -> groove (kick, clap, hats, bass, plucks)
  -> riser -> breakdown under the slow motion (pad + piano) -> snare roll -> drop
  -> big impact into the end card -> pad tail.
SFX are placed on the actual cuts: whooshes on whips/rolls, hits on punches, shimmer on flashes.
Writes 03_audio/mix_v2.wav at -14 LUFS / -1.5 dBTP.
"""
import json, os, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "03_audio")
os.makedirs(OUT, exist_ok=True)
SR = 44100
E = json.load(open(os.path.join(HERE, "edit_v2.json"), encoding="utf-8"))
BEAT = 60 / E["bpm"]
TOTAL = (E["card"]["b"] + E["card"]["len"]) * BEAT
N = int(TOTAL * SR) + SR
rng = np.random.default_rng(11)
B = lambda b: b * BEAT

BREAK0, BREAK1 = 29, 35          # slow-motion breakdown
CARD = E["card"]["b"]


def hz(n):
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    return 440 * 2 ** ((names[n[0]] + 12 * (int(n[-1]) + 1) - 69) / 12)


def add(buf, sig, t, g=1.0, pan=0.0):
    i = int(t * SR)
    if i < 0:
        sig, i = sig[-i:], 0
    if i >= len(buf):
        return
    sig = sig[:len(buf) - i]
    buf[i:i + len(sig), 0] += sig * g * np.cos((pan + 1) * np.pi / 4) * 1.414
    buf[i:i + len(sig), 1] += sig * g * np.sin((pan + 1) * np.pi / 4) * 1.414


def lp(x, cut):
    """One-pole low-pass, scalar or per-sample cutoff (vectorised via cumulative trick for scalar)."""
    cut = np.broadcast_to(np.asarray(cut, np.float32), x.shape)
    a = np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x); z = 0.0
    for i in range(len(x)):
        z = (1 - a[i]) * x[i] + a[i] * z; y[i] = z
    return y


def noise(d):
    return rng.standard_normal(int(d * SR)).astype(np.float32)


T = lambda d: np.arange(int(d * SR)) / SR

# ---------------------------------------------------------------- instruments
def kick():
    t = T(0.42)
    f = 46 + 110 * np.exp(-t * 32)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)
    y[:200] += np.linspace(0.5, 0, 200) * lp(rng.standard_normal(200).astype(np.float32), 3500.0)
    return (np.tanh(y * 1.6) * 0.9).astype(np.float32)


def clap():
    n = noise(0.25); t = T(0.25)
    env = np.exp(-t * 22)
    for o in (0.0, 0.011, 0.022):
        env += 0.6 * np.exp(-np.clip(t - o, 0, None) * 120) * (t >= o)
    y = n - lp(n, 900.0)
    y = lp(y, 5000.0)
    return (y * env * 0.5).astype(np.float32)


def hat(open_=False):
    d = 0.22 if open_ else 0.05
    n = noise(d)
    y = lp(n - lp(n, 6500.0), 13000.0)          # band-limited: no fizz at Nyquist
    return (y * np.exp(-T(d) * (14 if open_ else 70)) * 0.35).astype(np.float32)


def saw(f, d, harm=10):
    t = T(d)
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, harm + 1) if f * k < 14000).astype(np.float32)


def bass(f, d=0.22):
    y = saw(f, d, 6) * np.exp(-T(d) * 5)
    y[:200] *= np.linspace(0, 1, 200)
    y[-300:] *= np.linspace(1, 0, 300)
    return np.tanh(y * 1.2) * 0.32


def pluck(f, d=0.32, bright=1.0):
    t = T(d)
    y = sum(np.sin(2 * np.pi * f * k * t) * np.exp(-t * (9 + 6 * k / bright)) / k ** 1.2 for k in range(1, 9) if f * k < 14000)
    y[:60] *= np.linspace(0, 1, 60)
    return (y * 0.16).astype(np.float32)


def pad(freqs, d, lvl):
    t = T(d); y = np.zeros(len(t), np.float32)
    for f in freqs:
        for det in (-0.1, 0, 0.11):
            ff = f * 2 ** (det / 12)
            y += sum(np.sin(2 * np.pi * ff * k * t + rng.uniform(0, 6)) / k ** 1.7 for k in range(1, 6))
    a = int(min(0.5, d / 3) * SR)
    env = np.ones(len(t)); env[:a] = np.linspace(0, 1, a); env[-a:] *= np.linspace(1, 0, a)
    return (y * env * lvl / (len(freqs) * 3)).astype(np.float32)


def piano(f, d=2.5, v=1.0):
    t = T(d)
    y = sum((1 / k ** 1.4) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (1.3 + 0.9 * k)) for k in range(1, 9) if f * k < 12000)
    y[:150] *= np.linspace(0, 1, 150)
    return (y * 0.2 * v).astype(np.float32)


def whoosh(d=0.35):
    n = noise(d); k = np.linspace(0, 1, len(n))
    cut = 400 + 5000 * np.sin(np.pi * k) ** 2
    y = lp(n, cut) - lp(n, cut * 0.2)
    y = y * np.sin(np.pi * k) ** 1.5
    return (y * 0.55).astype(np.float32)


def impact(d=1.4, low=52, amt=1.0):
    t = T(d)
    f = low * (1 + 1.2 * np.exp(-t * 20))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3)
    y += 0.35 * lp(noise(d), 1500.0) * np.exp(-t * 10)
    return (np.tanh(y * 1.4) * 0.7 * amt).astype(np.float32)


def riser(d):
    k = np.linspace(0, 1, int(d * SR))
    y = lp(noise(d), 300 + 7000 * k ** 2) * 0.4 + 0.12 * np.sin(2 * np.pi * np.cumsum(200 + 900 * k ** 2) / SR)
    y = y * k ** 2
    y[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))
    return y.astype(np.float32)


def shimmer(d=0.8):
    t = T(d)
    y = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (2093, 2637, 3136, 4186)) * np.exp(-t * 4)
    return (y * 0.05).astype(np.float32)


def tick():
    t = T(0.03)
    return (np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 220) * 0.25).astype(np.float32)


def buzz(d=0.6):
    t = T(d)
    y = np.sign(np.sin(2 * np.pi * 100 * t)) * 0.5 + 0.3 * rng.standard_normal(len(t))
    gate = (np.sin(2 * np.pi * 9 * t) > 0.2) * np.exp(-t * 3)
    return (lp(y.astype(np.float32), 3000.0) * gate * 0.12).astype(np.float32)


# ---------------------------------------------------------------- arrangement
drums = np.zeros((N, 2), np.float32)
music = np.zeros((N, 2), np.float32)
sfx = np.zeros((N, 2), np.float32)
prog = [("A", ["A3", "C4", "E4", "A4"]), ("F", ["F3", "A3", "C4", "F4"]),
        ("C", ["C4", "E4", "G4", "C5"]), ("G", ["G3", "B3", "D4", "G4"])]
roots = {"A": "A1", "F": "F1", "C": "C2", "G": "G1"}
KICK, CLAP, HAT, OHAT = kick(), clap(), hat(), hat(True)
kicks = []
groove = lambda b: (8 <= b < BREAK0) or (BREAK1 <= b < CARD)

for b16 in range(0, CARD * 4):            # 16th-note grid
    b = b16 / 4
    bar = int(b // 4)
    name, chord = prog[bar % 4]
    on_beat = b16 % 4 == 0
    # drums
    if groove(b):
        if on_beat:
            add(drums, KICK, B(b), 1.0); kicks.append(B(b))
            if int(b) % 2 == 1:
                add(drums, CLAP, B(b), 0.8, 0.05)
        if b16 % 2 == 0:
            add(drums, HAT, B(b), 0.9 if b16 % 4 == 2 else 0.5, 0.3)
        elif b >= BREAK1:
            add(drums, HAT, B(b), 0.35, 0.3)
        if b16 % 4 == 2 and b >= 21:
            add(drums, OHAT, B(b), 0.45, -0.2)
    elif 4 <= b < 8 and b16 % 2 == 0:
        add(drums, HAT, B(b), 0.4, 0.3)
    if b < 8 and on_beat:                    # intro pulse: soft sub on every beat
        add(music, bass(hz(roots[name]), 0.3), B(b), 0.5)
    # bass (8ths)
    if groove(b) and b16 % 2 == 0:
        add(music, bass(hz(roots[name]) * (2 if b16 % 4 == 2 else 1)), B(b), 0.9)
    # pluck arpeggio (16ths), opens up through the intro
    if b < BREAK0 or BREAK1 <= b < CARD:
        note = chord[[0, 1, 2, 3, 2, 1, 2, 3][b16 % 8]]
        bright = 0.5 + min(1.0, b / 8) * 1.2
        v = 0.7 if b < 8 else 0.8
        add(music, pluck(hz(note) * 2, 0.3, bright), B(b), v, (-0.35 if b16 % 2 else 0.35))
    # chord pad every bar except intro's first bar
    if b16 % 16 == 0 and b < CARD:
        lvl = 0.10 if not (BREAK0 <= b < BREAK1) else 0.18
        lvl = 0.13 if b < 8 else lvl
        add(music, pad([hz(n) for n in chord], 4 * BEAT + 0.3, lvl), B(b))

# breakdown: piano chords under the slow motion
for i, b in enumerate(range(BREAK0, BREAK1, 2)):
    name, chord = prog[(int(b // 4)) % 4]
    for j, n in enumerate(chord):
        add(music, piano(hz(n), 2.5, 0.8), B(b) + j * 0.06, 1.0, -0.2 + 0.13 * j)
# snare roll + riser into the drop
for i in range(16):
    bb = BREAK1 - 2 + i * 0.125
    add(drums, CLAP, B(bb), 0.15 + 0.5 * i / 16)
add(sfx, riser(2.0), B(BREAK1) - 2.0, 0.5)
add(sfx, riser(1.4), B(BREAK0) - 1.4, 0.35)
add(sfx, impact(2.0, 46), B(BREAK0), 0.7)
add(sfx, impact(1.4, 55), B(BREAK1), 0.6)
# end card: big hit + resolve
add(sfx, impact(2.6, 42, 1.2), B(CARD), 0.9)
add(sfx, shimmer(1.6), B(CARD), 1.2)
for j, n in enumerate(["C3", "G3", "C4", "E4", "G4", "C5"]):
    add(music, piano(hz(n), 5.0, 0.8), B(CARD) + 0.02 * j, 1.0, -0.3 + 0.12 * j)
add(music, pad([hz("C4"), hz("E4"), hz("G4")], B(E["card"]["len"]), 0.14), B(CARD))
for b in range(CARD, CARD + 8):           # light pluck echo on the card
    add(music, pluck(hz(["C5", "E5", "G5", "E5"][b % 4]), 0.4, 0.8), B(b), 0.35 * (1 - (b - CARD) / 8), 0.3)

# SFX on the edit itself
for s in E["shots"]:
    t = B(s["b"]); tr = s.get("tr", "cut")
    if tr in ("whip_l", "whip_r", "roll"):
        add(sfx, whoosh(0.3 if tr != "roll" else 0.4), t - 0.16, 0.55, -0.6 if tr == "whip_l" else 0.6)
    elif tr == "punch":
        add(sfx, impact(0.5, 70, 0.6), t, 0.45)
    elif tr in ("flash", "circle"):
        add(sfx, shimmer(), t, 1.0)
    if s.get("neon"):
        add(sfx, buzz(0.7), t, 1.0)
    for fb in s.get("flash", []):
        add(sfx, shimmer(1.0), B(fb), 1.2); add(sfx, impact(1.0, 60, 0.7), B(fb), 0.5)
for g in E["typing"]:
    n = sum(1 for c in g["text"] if c != " ")
    for i in range(n):
        add(sfx, tick(), B(g["b"] + i * g["step"]), 0.7 if g["where"] == "film" else 0.4)

# sidechain: duck music under every kick (the pumping feel of the reference)
duck = np.ones(N, np.float32)
for kt in kicks:
    i = int(kt * SR); n = int(0.25 * SR)
    seg = 1 - 0.55 * np.exp(-np.arange(n) / SR / 0.07)
    duck[i:i + n] = np.minimum(duck[i:i + n], seg[:max(0, N - i)])
music *= duck[:, None]

# simple stereo room on music + sfx
def room(x, secs=1.6, mix=0.18):
    n = int(secs * SR); t = np.arange(n) / SR; out = np.empty_like(x)
    for c in range(2):
        ir = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.4); ir /= np.sqrt((ir ** 2).sum())
        nf = 1 << (len(x) + n - 1).bit_length()
        wet = np.fft.irfft(np.fft.rfft(x[:, c], nf) * np.fft.rfft(ir, nf), nf)[:len(x)]
        out[:, c] = x[:, c] * (1 - mix) + wet * mix * 1.5
    return out

mix = drums * 0.9 + room(music) * 1.0 + room(sfx, 1.2, 0.15) * 0.8
n_total = int(TOTAL * SR)
mix = mix[:n_total]
fade = np.ones(n_total, np.float32)
fs = int((TOTAL - 2.0) * SR); fade[fs:] = np.linspace(1, 0, n_total - fs) ** 1.6
mix *= fade[:, None]
mix = np.tanh(mix / max(1e-6, np.abs(mix).max()) * 1.3) * 0.7     # gentle glue saturation


def wav(path, x):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", path], input=x.astype(np.float32).tobytes(), check=True)


pre = os.path.join(OUT, "mix_v2_pre.wav"); wav(pre, mix)
m = subprocess.run(["ffmpeg", "-hide_banner", "-i", pre, "-af", "loudnorm=I=-14:TP=-2.5:LRA=11:print_format=json",
                    "-f", "null", "-"], capture_output=True, text=True).stderr
st = json.loads(m[m.rfind("{"):m.rfind("}") + 1])
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", pre, "-af",
                f"loudnorm=I=-14:TP=-2.5:LRA=11:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
                f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}:linear=true",
                "-ar", str(SR), os.path.join(OUT, "mix_v2.wav")], check=True)
os.remove(pre)
print(f"audio v2 done: {TOTAL:.2f}s")
