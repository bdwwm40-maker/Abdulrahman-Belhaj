#!/usr/bin/env python3
"""PINK HOPE — sound design.

Everything here is synthesised in code (no third-party music or samples):
  score   : soft piano arpeggios -> string pad -> low strings swell -> piano resolve
  sfx     : soft whooshes on title entries, short risers, two soft low hits
  ambience: the real room sound of each shot, very low, with short J-cut lead-ins
Writes 03_audio/{score,sfx,ambience,mix}.wav (44.1 kHz stereo).
"""
import json, os, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "03_audio")
os.makedirs(OUT, exist_ok=True)
SR = 44100
E = json.load(open(os.path.join(HERE, "edit.json"), encoding="utf-8"))
FPS = E["fps"]
SRC = os.path.normpath(os.path.join(HERE, E["source_dir"]))
rng = np.random.default_rng(7)

# ---- timeline (same rule as render.py)
t = 0.0
for s in E["shots"]:
    s["start"] = t
    s["ov"] = s.get("xf", 0) / FPS if s["out"] in ("xfade", "card") else 0.0
    t += s["dur"] - s["ov"]
CARD = t
TOTAL = CARD + E["card_dur"]
N = int(TOTAL * SR) + SR
by_id = {s["id"]: s for s in E["shots"]}
CH3 = by_id["S05"]["start"]
CH4 = by_id["S08"]["start"]
title_t = [by_id[ti["shot"]]["start"] + ti["at"] for ti in E["titles"]]


def hz(note):
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    n = names[note[0]] + (1 if "#" in note else 0)
    octv = int(note[-1])
    return 440.0 * 2 ** ((n + 12 * (octv + 1) - 69) / 12)


def env_adsr(n, a, r):
    e = np.ones(n, np.float32)
    na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, 1, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e


def piano(f, dur=3.2, vel=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    y = np.zeros(n, np.float32)
    for k in range(1, 9):
        fk = f * k * np.sqrt(1 + 0.0004 * k * k)
        if fk > 12000: break
        y += (1 / k ** 1.4) * np.sin(2 * np.pi * fk * tt) * np.exp(-tt * (1.2 + 0.9 * k))
    y *= env_adsr(n, 0.004, 0.3)
    return y * vel * 0.22


def pad(freqs, dur, level):
    n = int(dur * SR); tt = np.arange(n) / SR
    y = np.zeros(n, np.float32)
    for f in freqs:
        for det in (-0.12, 0.0, 0.13):
            ff = f * 2 ** (det / 12)
            ph = rng.uniform(0, 6.28)
            for k in range(1, 6):
                y += (0.5 / k ** 1.6) * np.sin(2 * np.pi * ff * k * tt + ph * k)
    y *= (1 + 0.08 * np.sin(2 * np.pi * 0.25 * tt))  # slow bowing motion
    return y * env_adsr(n, min(1.2, dur / 3), min(1.2, dur / 3)) * level / (len(freqs) * 3)


def cello(f, dur, level):
    n = int(dur * SR); tt = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * tt) * np.clip(tt / 0.8, 0, 1)
    phase = 2 * np.pi * f * np.cumsum(vib) / SR
    y = sum((1 / k ** 1.2) * np.sin(k * phase) for k in range(1, 8))
    return (y * env_adsr(n, 0.6, 0.8) * level).astype(np.float32)


def add(buf, sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= buf.shape[0]: return
    sig = sig[: buf.shape[0] - i]
    lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:i + len(sig), 0] += sig * gain * lg * 1.414
    buf[i:i + len(sig), 1] += sig * gain * rg * 1.414


def reverb(x, secs=2.6, mix=0.28):
    n = int(secs * SR)
    tt = np.arange(n) / SR
    out = np.empty_like(x)
    for c in range(2):
        ir = rng.standard_normal(n).astype(np.float32) * np.exp(-tt / 0.75)
        ir[: int(0.012 * SR)] = 0
        ir /= np.sqrt((ir ** 2).sum())
        L = len(x) + n
        nf = 1 << (L - 1).bit_length()
        wet = np.fft.irfft(np.fft.rfft(x[:, c], nf) * np.fft.rfft(ir, nf), nf)[: len(x)]
        out[:, c] = x[:, c] * (1 - mix) + wet * mix * 1.6
    return out


def onepole_lp(x, cutoff):
    """Time-varying one-pole low-pass (cutoff array in Hz)."""
    a = np.exp(-2 * np.pi * np.asarray(cutoff) / SR)
    y = np.empty_like(x); z = 0.0
    for i in range(len(x)):
        z = (1 - a[i]) * x[i] + a[i] * z
        y[i] = z
    return y


# ---------------------------------------------------------------- score
score = np.zeros((N, 2), np.float32)
# A minor -> F -> C -> G  (i - VI - III - VII), resolving to C major at the end
prog = [("A", ["A2", "C4", "E4", "A4"]), ("F", ["F2", "A3", "C4", "F4"]),
        ("C", ["C3", "E4", "G4", "C5"]), ("G", ["G2", "B3", "D4", "G4"])]
BAR = 3.2
STEP = BAR / 8
nbars = int(np.ceil(CARD / BAR))
for b in range(nbars):
    t0 = b * BAR
    root, chord = prog[b % 4]
    intensity = 0.55 + 0.45 * np.clip((t0 - CH4 + 4) / 12, 0, 1)  # build into chapter 4
    pattern = [1, 2, 3, 2, 1, 2, 3, 2] if t0 < CH4 else [1, 2, 3, 4, 3, 2, 3, 2]
    notes = [chord[0]] + chord[1:] + [chord[-1][:-1] + str(int(chord[-1][-1]) + 1)]
    for i, p in enumerate(pattern):
        if t0 + i * STEP > CARD - 0.2: break
        v = (0.9 if i == 0 else 0.55 + 0.1 * (i % 2)) * intensity
        add(score, piano(hz(notes[p]), 2.6, v), t0 + i * STEP + rng.uniform(0, 0.008), pan=-0.25 + 0.12 * p)
    add(score, piano(hz(chord[0]), 3.4, 0.75 * intensity), t0, pan=-0.1)
    # string pad from chapter 3, louder in chapter 4
    if t0 + BAR > CH3 - 1.0:
        lvl = 0.10 if t0 < CH4 - 1 else 0.17 + 0.05 * np.clip((t0 - CH4) / 8, 0, 1)
        add(score, pad([hz(n_) for n_ in chord[1:]], BAR + 1.0, lvl), t0 - 0.4, pan=0.0)
    # low strings from chapter 4
    if t0 + BAR > CH4 - 0.5:
        add(score, cello(hz(chord[0]), BAR + 0.6, 0.05), t0 - 0.2, pan=0.15)
    # simple top-line melody in chapter 4
    if t0 >= CH4 - 0.5:
        add(score, piano(hz(chord[-1][:-1] + str(int(chord[-1][-1]) + 1)), 3.0, 0.5), t0 + 0.02, pan=0.3)
        add(score, piano(hz(chord[2][:-1] + str(int(chord[2][-1]) + 1)), 2.4, 0.38), t0 + BAR * 0.5, pan=0.3)
# closing: gentle resolve on C major with long decay
for i, nn in enumerate(["C3", "G3", "E4", "G4", "C5", "E5"]):
    add(score, piano(hz(nn), 6.0, 0.7 - 0.05 * i), CARD + 0.3 + i * 0.22, pan=-0.3 + 0.12 * i)
add(score, pad([hz("E4"), hz("G4"), hz("C5")], 5.6, 0.10), CARD + 0.1)
score = reverb(score, 2.8, 0.32)
fade = np.ones(N, np.float32)
fs = int((TOTAL - 2.2) * SR)
fade[fs:] = np.clip(1 - (np.arange(N - fs) / (2.2 * SR)), 0, 1) ** 1.5
fade[: int(0.4 * SR)] = np.linspace(0, 1, int(0.4 * SR))
score *= fade[:, None]

# ---------------------------------------------------------------- sfx
sfx = np.zeros((N, 2), np.float32)


def whoosh(d=0.55):
    n = int(d * SR); x = rng.standard_normal(n).astype(np.float32)
    k = np.linspace(0, 1, n)
    cut = 300 + 3500 * np.sin(np.pi * k) ** 2
    y = onepole_lp(x, cut) - onepole_lp(x, cut * 0.25)
    return y * np.sin(np.pi * k) ** 2 * 0.5


def riser(d=1.3):
    n = int(d * SR); k = np.linspace(0, 1, n); tt = np.arange(n) / SR
    x = rng.standard_normal(n).astype(np.float32)
    y = onepole_lp(x, 400 + 6000 * k ** 2) * 0.35
    y += 0.12 * np.sin(2 * np.pi * np.cumsum(220 + 660 * k ** 2) / SR)
    y = y * k ** 2.2
    y[-int(0.06 * SR):] *= np.linspace(1, 0, int(0.06 * SR)) ** 2  # short release, no hard stop
    return y.astype(np.float32)


def hit():
    n = int(2.0 * SR); tt = np.arange(n) / SR
    f = 62 * (1 + 0.6 * np.exp(-tt * 18))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 2.6)
    y += 0.25 * onepole_lp(rng.standard_normal(n).astype(np.float32), np.full(n, 900.0)) * np.exp(-tt * 9)
    return (y * 0.55).astype(np.float32)


for i, tt in enumerate(title_t):
    if i == 0: continue
    add(sfx, whoosh(), tt - 0.3, 0.19, pan=(-0.4 if i % 2 else 0.4))
add(sfx, riser(1.2), CH3 - 1.2, 0.35)
add(sfx, riser(1.6), CARD - 1.6 + 0.35, 0.30)
add(sfx, hit(), title_t[0] - 0.02, 0.42)
add(sfx, hit(), CARD + 0.35, 0.45)
sfx = reverb(sfx, 1.8, 0.25)

# ---------------------------------------------------------------- ambience (real room sound)
amb = np.zeros((N, 2), np.float32)
LEAD = 0.25  # J-cut: next room is heard slightly before the picture cuts
for s in E["shots"]:
    if s.get("slowmo"):
        continue  # slow-motion moment is music only
    lead = LEAD if s["start"] > 0 else 0.0
    ss = max(0.0, s["in"] - lead)
    d = s["dur"] + lead
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(ss), "-t", str(d), "-i", os.path.join(SRC, s["src"]),
                          "-vn", "-ac", "2", "-ar", str(SR), "-af", "highpass=f=90,lowpass=f=9000",
                          "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    if not len(x): continue
    rms = np.sqrt((x ** 2).mean()) + 1e-9
    x *= (10 ** (-34 / 20)) / rms                      # normalise every room to the same low bed
    e = env_adsr(len(x), 0.2, 0.3)[:, None]
    i = int((s["start"] - lead) * SR)
    i = max(i, 0)
    amb[i:i + len(x)] += (x * e)[: N - i]
amb = np.tanh(amb / 0.12) * 0.12  # soft-limit sudden room noises (a voice spike, a chair)
amb[int(CARD * SR):] *= np.linspace(1, 0, N - int(CARD * SR))[:, None] ** 3

# ---------------------------------------------------------------- write
def wav(name, x):
    p = os.path.join(OUT, name)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", p], input=np.clip(x, -1, 1).astype(np.float32).tobytes(), check=True)
    return p


n_total = int(TOTAL * SR)
score, sfx, amb = score[:n_total], sfx[:n_total], amb[:n_total]
wav("score.wav", score); wav("sfx.wav", sfx); wav("ambience.wav", amb)
mix = score * 1.0 + sfx * 0.8 + amb * 1.0
mix /= max(1e-6, np.abs(mix).max()) / 0.7
pre = wav("mix_pre.wav", mix)
# two-pass loudness normalisation to -14 LUFS / -1.5 dBTP (social-video standard)
m = subprocess.run(["ffmpeg", "-hide_banner", "-i", pre, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                    "-f", "null", "-"], capture_output=True, text=True).stderr
st = json.loads(m[m.rfind("{"):m.rfind("}") + 1])
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", pre, "-af",
                f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
                f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}:linear=true",
                "-ar", str(SR), os.path.join(OUT, "mix.wav")], check=True)
os.remove(pre)
print(f"audio done: {TOTAL:.2f}s  card@{CARD:.2f}  ch3@{CH3:.2f}  ch4@{CH4:.2f}")
