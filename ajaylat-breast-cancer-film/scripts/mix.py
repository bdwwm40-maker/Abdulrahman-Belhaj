import json, subprocess
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
from plan import SRC

SR = 48000
TL = json.load(open("timeline.json"))
TOTAL = TL["total"]
N = int(TOTAL * SR)


def dec(path, ss=None, dur=None, ch=1):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", str(ss), "-t", str(dur)]
    cmd += ["-i", path, "-f", "f32le", "-ac", str(ch), "-ar", str(SR), "-"]
    return np.frombuffer(subprocess.check_output(cmd), np.float32).astype(np.float64)


def add(buf, start, sig):
    i = int(round(start * SR)); j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += sig[: j - i]


music = np.load("music.npy").astype(np.float64)[:N] * 0.7
if len(music) < N:
    music = np.pad(music, ((0, N - len(music)), (0, 0)))

# ---- voice-over: warm, close, a touch of room
vo = np.zeros(N)
for st, vid, ln in TL["vo"]:
    add(vo, st, dec(f"vo_p/{vid}.wav"))
vo = vo / (np.max(np.abs(vo)) + 1e-9) * 0.5
r = np.random.default_rng(11)
n = int(1.4 * SR); t = np.arange(n) / SR
ir = r.standard_normal(n) * np.exp(-t * 6.9 / 1.4)
ir = sosfilt(butter(2, 5000, "low", fs=SR, output="sos"), ir); ir /= np.sqrt(np.sum(ir ** 2))
voL = vo + fftconvolve(vo, ir)[:N] * 0.10
voR = vo + fftconvolve(vo, np.roll(ir, 331))[:N] * 0.10

# ---- ducking: music dips ~6.5 dB under the voice, smooth attack/release
act = np.zeros(N)
for st, vid, ln in TL["vo"]:
    a = int((st - 0.35) * SR); b = int((st + ln + 0.25) * SR)
    act[max(0, a):b] = 1
k = int(0.45 * SR)
win = np.hanning(2 * k); win /= win.sum()
act = np.convolve(act, win, mode="same")
duck = 1 - act * (1 - 10 ** (-8 / 20))
music *= duck[:, None]

# ---- production sound from the real footage (room tone, footsteps, paper, people)
prod = np.zeros(N)
hpf = butter(2, 120, "high", fs=SR, output="sos")
for p in TL["prod"]:
    a = dec(SRC[p["src"]], p["ss"], p["dur"])
    a = sosfilt(hpf, a)
    rms = np.sqrt(np.mean(a ** 2)) + 1e-9
    a = a / rms * 0.02                    # equalise, sits well under music/VO
    f = int(0.3 * SR); e = np.ones(len(a))
    e[:f] = np.linspace(0, 1, f); e[-f:] = np.linspace(1, 0, f)
    add(prod, p["start"], a * e)
prod *= (1 - act * 0.5)                   # also tuck it under the voice

L = music[:, 0] + voL + prod
R = music[:, 1] + voR + prod
# global fades: 1.2 s of true silence at the head, fade to black at the tail
head = int(1.2 * SR)
g = np.ones(N); g[:head] = 0; g[head:head + int(1.0 * SR)] = np.linspace(0, 1, int(1.0 * SR))
tail = int(2.5 * SR); g[-tail:] *= np.linspace(1, 0, tail) ** 1.5
out = np.stack([L * g, R * g], 1)
out = out / np.max(np.abs(out)) * 0.89
out.astype(np.float32).tofile("mix.f32")
print("mix", N / SR)
