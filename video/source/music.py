"""Original inspirational score, timed to the film's scenes (56 s incl. end card)."""
import numpy as np
import wave

SR = 44100
DUR = 56.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(3)
L = np.zeros(N); Rch = np.zeros(N)


def mf(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(sig, start, pan=0.0, gain=1.0):
    i0 = int(start * SR)
    if i0 >= N:
        return
    sig = sig[: N - i0] * gain
    L[i0:i0 + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    Rch[i0:i0 + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def env(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na) ** 2
    e[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e


def pad_note(freq, dur, bright=6):
    n = int(dur * SR); x = np.arange(n) / SR
    out = np.zeros(n)
    for det in (-0.12, 0.0, 0.11):
        f = freq * 2 ** (det / 12)
        for h in range(1, bright + 1):
            out += np.sin(2 * np.pi * f * h * x + h * 1.3) / (h ** 1.6)
    return out / 3


def pluck(freq, dur=1.2):
    n = int(dur * SR); x = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * freq * h * x) * np.exp(-x * (3 + h * 2.2)) / h for h in range(1, 6))
    return s * np.minimum(1, x * 400)


def kick(power=1.0):
    n = int(0.9 * SR); x = np.arange(n) / SR
    f = 44 + 95 * np.exp(-x * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-x * (5.5 / power)) * power


def boom(length=4.0):
    n = int(length * SR); x = np.arange(n) / SR
    f = 34 + 70 * np.exp(-x * 9)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 1.4)
    noise = rng.standard_normal(n) * np.exp(-x * 3) * 0.15
    return s + np.convolve(noise, np.ones(30) / 30, 'same')


def riser(length):
    n = int(length * SR); x = np.arange(n) / SR
    noise = rng.standard_normal(n)
    hp = noise - np.convolve(noise, np.ones(40) / 40, 'same')
    tone = np.sin(2 * np.pi * np.cumsum(220 * 2 ** (x / length * 2)) / SR) * 0.25
    return (hp * 0.35 + tone) * (x / length) ** 2.5


# chord plan: (start, end, bass midi, voicing midis)
Am = (45, [57, 60, 64, 71]); F = (41, [53, 57, 60, 64]); C = (48, [55, 60, 64, 74]); G = (43, [55, 59, 62, 69])
plan = [(0, 7, Am), (7, 10.5, F), (10.5, 14, C), (14, 17.5, G), (17.5, 21, Am), (21, 23, F),
        (23, 27, F), (27, 31, G), (31, 35, C), (35, 39, G), (39, 43, Am), (43, 47.2, F), (47.2, 48, G), (48, 56, C)]


def level(s):  # overall dynamic arc of the story
    return np.interp(s, [0, 7, 14, 23, 25, 31, 39, 47.5, 48, 53, 56], [.6, .65, .7, .72, .55, .85, .9, 1.0, .9, .6, 0])


for a, b, (bass, voic) in plan:
    d = b - a + 0.8
    g = level(a)
    bright = 4 if a < 23 else 8
    for k, m in enumerate(voic):
        add(pad_note(mf(m), d, bright) * env(int(d * SR), 0.6, 0.9), a, pan=(-.5 + k / 3), gain=0.05 * g)
    add(pad_note(mf(bass), d, 3) * env(int(d * SR), 0.4, 0.9), a, gain=0.11 * g)
    if a >= 31:  # octave strings for the full sections
        for m in voic[:2]:
            add(pad_note(mf(m + 12), d, 5) * env(int(d * SR), 0.8, 0.9), a, pan=.2, gain=0.03 * g)

# arpeggio pulse from the moment volunteering begins
step = 60 / 90 / 2
for a, b, (bass, voic) in plan:
    if a < 7 or a >= 48:
        continue
    notes = [voic[0] + 12, voic[1] + 12, voic[2] + 12, voic[3]]
    s = a; i = 0
    while s < b - 0.01:
        add(pluck(mf(notes[i % 4])), s, pan=.35 * (1 if i % 2 else -1), gain=0.06 * level(s) * (0.4 if 23 <= s < 27 else 1))
        s += step; i += 1

# percussion
beat = 60 / 90
s = 14.0
while s < 23:
    add(kick(.7), s, gain=0.16); s += beat * 2
s = 31.0
while s < 47.2:
    add(kick(1.0), s, gain=0.17); s += beat
for hit in (31.0, 48.0):
    add(boom(), hit, gain=0.26)
add(riser(4.0), 27.0, gain=0.10)
add(riser(2.4), 45.6, gain=0.11)

# end-card bell motif over the resolved chord
for k, m in enumerate([76, 79, 84, 88]):
    add(pluck(mf(m), 3.0), 48.6 + k * 0.42, pan=-.3 + .2 * k, gain=0.05)

# simple stereo reverb (decaying noise impulse) via FFT convolution
ir_n = int(2.6 * SR); ir_t = np.arange(ir_n) / SR
nfft = 1 << int(np.ceil(np.log2(N + ir_n)))
mix = []
for ch, seed in ((L, 1), (Rch, 2)):
    ir = np.random.default_rng(seed).standard_normal(ir_n) * np.exp(-ir_t * 2.4)
    ir = np.convolve(ir, np.ones(8) / 8, 'same')
    wet = np.fft.irfft(np.fft.rfft(ch, nfft) * np.fft.rfft(ir, nfft), nfft)[:N]
    wet /= np.max(np.abs(wet)) + 1e-9
    dry = ch / (np.max(np.abs(ch)) + 1e-9)
    mix.append(0.62 * dry + 0.38 * wet)
out = np.stack(mix, 1)
fade = np.ones(N); fade[-int(2.5 * SR):] = np.linspace(1, 0, int(2.5 * SR)) ** 2
fade[:int(.5 * SR)] = np.linspace(0, 1, int(.5 * SR))
out *= fade[:, None]
out = np.tanh(out * 1.3) / np.tanh(1.3)
out *= 0.89 / np.max(np.abs(out))
with wave.open('score.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((out * 32767).astype('<i2').tobytes())
print('score.wav', DUR, 's')
