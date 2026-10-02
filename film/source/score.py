"""Original cinematic score + sound design, synthesized to the film timeline."""
import numpy as np, subprocess, math
from scipy.signal import butter, sosfilt, fftconvolve
import timeline as T

SR = 48000
DUR = T.FILM_END + 1.0
N = int(DUR * SR)
rng = np.random.default_rng(3)
L = np.zeros(N); R = np.zeros(N)
BEAT = T.BARLEN / 4

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)

def env_adsr(n, a, d, s, r):
    e = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n); e[:na] = np.linspace(0, 1, na)
    if nd > 0 and na + nd < n: e[na:na + nd] = np.linspace(1, s, nd)
    if nr > 0: e[-nr:] *= np.linspace(1, 0, nr)
    return e

def lp(x, f, order=2):
    return sosfilt(butter(order, min(f, SR / 2 - 100) / (SR / 2), 'low', output='sos'), x)

def hp(x, f, order=2):
    return sosfilt(butter(order, f / (SR / 2), 'high', output='sos'), x)

def add(buf_l, buf_r, sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= N: return
    sig = sig[:N - i]
    gl, gr = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
    buf_l[i:i + len(sig)] += sig * gain * gl
    buf_r[i:i + len(sig)] += sig * gain * gr

# separate busses so we can shape them
bus = {k: (np.zeros(N), np.zeros(N)) for k in ['piano', 'str', 'low', 'perc', 'brass', 'fx', 'amb']}

# ---------- instruments ----------
def piano(m, dur, vel=1.0):
    f = hz(m); n = int((dur + 2.5) * SR); t = np.arange(n) / SR
    s = np.zeros(n)
    for k, (amp, dec) in enumerate([(1, 1.6), (0.45, 1.0), (0.22, 0.7), (0.12, 0.5), (0.06, 0.35)], 1):
        inh = f * k * (1 + 0.0004 * k * k)
        s += amp * np.sin(2 * np.pi * inh * t) * np.exp(-t * (1.0 / dec) * (0.6 + 0.25 * k))
    s *= np.minimum(1, t / 0.004)
    rel = np.ones(n); ri = int(dur * SR)
    if ri < n: rel[ri:] = np.exp(-(t[ri:] - dur) * 6)
    return s * rel * vel * 0.25

def strings(m, dur, att=1.5, rel=1.8, bright=2500, voices=5):
    f = hz(m); n = int((dur + rel) * SR); t = np.arange(n) / SR
    s = np.zeros(n)
    for v in range(voices):
        det = 1 + (v - voices // 2) * 0.0035
        vib = 1 + 0.003 * np.sin(2 * np.pi * (5.0 + v * 0.3) * t + v)
        ph = np.cumsum(f * det * vib) / SR
        saw = 2 * (ph % 1) - 1
        s += saw
    s = lp(s / voices, bright, 2)
    e = env_adsr(n, att, 0.0, 1.0, rel)
    return s * e * 0.18

def sub_drone(m, dur, att=3, rel=3):
    f = hz(m); n = int((dur + rel) * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2 * t + 0.3)
    return s * env_adsr(n, att, 0, 1, rel) * 0.22

def taiko(gain=1.0, pitch=58):
    n = int(1.6 * SR); t = np.arange(n) / SR
    f = pitch * (1 + 1.4 * np.exp(-t * 28))
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5.0)
    skin = lp(rng.normal(0, 1, n), 1800) * np.exp(-t * 30) * 0.5
    return (body + skin) * gain * 0.7

def boom(gain=1.0):
    n = int(5 * SR); t = np.arange(n) / SR
    f = 42 * (1 + 2.5 * np.exp(-t * 9))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 0.9)
    s += lp(rng.normal(0, 1, n), 900) * np.exp(-t * 5) * 0.35
    return s * gain * 0.9

def riser(dur, gain=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    noise = rng.normal(0, 1, n)
    out = np.zeros(n); seg = SR // 20
    for i in range(0, n, seg):
        fc = 300 + 7000 * (u[i] ** 2.2)
        out[i:i + seg] = lp(noise[i:i + seg + 200], fc)[:len(out[i:i + seg])]
    tone = np.sin(2 * np.pi * np.cumsum(110 * 2 ** (u * 2)) / SR) * 0.25
    return (out * 0.5 + tone) * (u ** 2.5) * gain

def whoosh(dur=1.4, gain=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    noise = rng.normal(0, 1, n)
    e = np.sin(np.pi * u) ** 2
    out = np.zeros(n); seg = SR // 25
    for i in range(0, n, seg):
        fc = 400 + 3500 * math.sin(math.pi * u[i])
        out[i:i + seg] = lp(noise[i:i + seg + 100], fc)[:len(out[i:i + seg])]
    return out * e * gain * 0.35

def cymbal_swell(dur, gain=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    return hp(rng.normal(0, 1, n), 4000) * (u ** 3) * gain * 0.12

def breath(gain=1.0):
    n = int(2.6 * SR); t = np.arange(n) / SR
    e = np.sin(np.pi * np.clip(t / 1.2, 0, 1)) ** 2 * (t < 1.2) + 0.7 * np.sin(np.pi * np.clip((t - 1.35) / 1.2, 0, 1)) ** 2 * (t > 1.35)
    s = sosfilt(butter(2, [500 / (SR / 2), 2500 / (SR / 2)], 'band', output='sos'), rng.normal(0, 1, n))
    return s * e * gain * 0.06

# ---------- harmony (D harmonic minor; augmented 2nd gives a North-African colour) ----------
# chord roots/voicings (midi)
Dm = [50, 57, 62, 65]; Bb = [46, 58, 62, 65]; Gm = [43, 58, 62, 67]; A = [45, 57, 61, 64]
F = [41, 57, 60, 65]; C = [48, 55, 60, 64]; Dm2 = [38, 57, 62, 65]
PROG = [Dm, Bb, Gm, A]

def place_chords(t_start, t_end, chord_len, prog, fn, bus_name, **kw):
    t = t_start; i = 0
    while t < t_end - 0.01:
        d = min(chord_len, t_end - t)
        for j, m in enumerate(prog[i % len(prog)]):
            s = fn(m, d, **kw)
            add(*bus[bus_name], s, t, pan=(j - 1.5) * 0.35)
        t += chord_len; i += 1

# Act I: drone + breath
add(*bus['low'], sub_drone(38, 34, att=4, rel=4), 0.0, gain=0.8)
add(*bus['fx'], breath(1.0), 0.6)
add(*bus['fx'], breath(0.7), 18.0)

# piano motif (hijaz-flavoured: A Bb C# D ... ) over Act I/II
motif = [(69, 1), (70, 1), (73, 1), (74, 2), (72, 1), (70, 1), (69, 3)]  # beats
motif2 = [(74, 1), (76, 1), (77, 2), (76, 1), (74, 1), (73, 1), (74, 3)]
def play_motif(t, mot, oct=0, vel=0.9):
    for m, b in mot:
        add(*bus['piano'], piano(m + oct, b * BEAT * 1.6, vel), t, pan=0.15)
        t += b * BEAT * 1.6   # slow, rubato-like
    return t

tp = 3.0
for i in range(3):
    add(*bus['piano'], piano(PROG[i % 4][0] + 12, 3.0, 0.6), tp, pan=-0.2)
    tp = play_motif(tp, motif if i % 2 == 0 else motif2, 0, 0.8 - i * 0.05) + 0.6
# soft strings join
place_chords(15.5, 34.8, BEAT * 4 * 1.6 * 1.0, PROG, strings, 'str', att=2.5, rel=2.5, bright=1400)

# bridge: rising strings, pulse and riser
place_chords(34.8, T.bar(0), (T.bar(0) - 34.8) / 2, [Gm, A], strings, 'str', att=2.0, rel=1.0, bright=2200)
for k in range(12):
    tt = 37.0 + k * BEAT
    if tt < T.bar(0) - 0.2:
        add(*bus['perc'], taiko(0.18 + 0.03 * k, 50), tt)
add(*bus['fx'], riser(T.bar(0) - 39.5, 0.8), 39.5)
add(*bus['fx'], cymbal_swell(3.5, 1.2), T.bar(0) - 3.5)
add(*bus['fx'], whoosh(1.8, 0.9), 34.6)

# Act III: strings + deep percussion
add(*bus['perc'], boom(1.0), T.bar(0))
place_chords(T.bar(0), T.bar(10), T.BARLEN * 2, [Dm, Bb, F, A], strings, 'str', att=1.2, rel=2.0, bright=2600)
place_chords(T.bar(0), T.bar(10), T.BARLEN * 2, [[38], [34], [41], [33]], sub_drone, 'low', att=0.6, rel=1.5)
for b in range(10):
    t0 = T.bar(b)
    add(*bus['perc'], taiko(0.5, 52), t0)
    add(*bus['perc'], taiko(0.28, 60), t0 + 2.5 * BEAT)
    if b >= 6:
        add(*bus['perc'], taiko(0.22, 66), t0 + 3.5 * BEAT)
# gentle piano echoes of the motif in ceremony section
play_motif(T.bar(2), motif, 12, 0.45)
play_motif(T.bar(6), motif2, 12, 0.45)
add(*bus['fx'], riser(T.bar(10) - T.bar(8.5), 0.9), T.bar(8.5))
add(*bus['fx'], cymbal_swell(T.BARLEN * 1.5, 1.4), T.bar(8.5))

# CLIMAX
add(*bus['perc'], boom(1.1), T.bar(10))
place_chords(T.bar(10), T.bar(17), T.BARLEN, [Dm, Bb, Gm, A, Dm, F, C], strings, 'str', att=0.5, rel=1.8, bright=4200, voices=7)
place_chords(T.bar(10), T.bar(17), T.BARLEN, [[m + 12 for m in c] for c in [Dm, Bb, Gm, A, Dm, F, C]], strings, 'str', att=0.6, rel=1.8, bright=5000)
def brass(m, dur, **kw):
    return strings(m, dur, att=0.25, rel=1.2, bright=1500, voices=3) * 1.4
place_chords(T.bar(10), T.bar(17), T.BARLEN, [[50, 57], [46, 53], [43, 50], [45, 52], [50, 57], [41, 48], [48, 55]], brass, 'brass')
place_chords(T.bar(10), T.bar(17), T.BARLEN, [[26], [22], [31], [33], [26], [29], [36]], sub_drone, 'low', att=0.2, rel=1.0)
for b in range(10, 17):
    t0 = T.bar(b)
    for (bt, g, p) in [(0, 0.9, 50), (1.5, 0.45, 58), (2, 0.6, 54), (3, 0.45, 62), (3.5, 0.5, 66)]:
        add(*bus['perc'], taiko(g, p), t0 + bt * BEAT, pan=(p - 58) / 20)
# soaring motif on strings at the match cut
tm = T.MATCH_T
for m, b in motif2:
    add(*bus['str'], strings(m + 12, b * BEAT * 1.6, att=0.3, rel=1.0, bright=5000, voices=7) * 1.3, tm, pan=0.1)
    tm += b * BEAT * 1.6
add(*bus['fx'], riser(1.6, 0.6), T.MATCH_T - 1.6)
add(*bus['perc'], boom(1.2), T.MATCH_T)

# RESOLUTION: piano + soft strings
te = T.bar(17)
add(*bus['perc'], boom(0.6), te)
place_chords(te, T.FILM_END - 2, (T.FILM_END - 2 - te) / 4, [Bb, Gm, A, Dm2], strings, 'str', att=2.5, rel=4.0, bright=1500)
add(*bus['low'], sub_drone(38, T.FILM_END - te, att=3, rel=3), te, gain=0.7)
tp = te + 1.0
tp = play_motif(tp, motif, 0, 0.7)
tp = play_motif(tp + 0.8, motif2, -12, 0.55)
# final low hit for "العجيلات — 2026" and last chord
add(*bus['perc'], boom(0.55), T.TITLE_T)
for m in [50, 57, 62, 65, 69]:
    add(*bus['piano'], piano(m, 6.0, 0.55), T.TITLE_T + 0.05)
for m in [38, 50, 57, 62]:
    add(*bus['piano'], piano(m, 7.0, 0.5), T.TEXTS['seal'][0])
add(*bus['fx'], whoosh(1.2, 0.5), T.bar(0) - 0.6)
add(*bus['fx'], whoosh(0.9, 0.35), T.MATCH_T - 0.45)

# ---------- reverb ----------
def reverb(l, r, secs=3.2, wet=0.35, damp=5000):
    n = int(secs * SR); t = np.arange(n) / SR
    irl = lp(rng.normal(0, 1, n), damp) * np.exp(-t * 6.9 / secs)
    irr = lp(rng.normal(0, 1, n), damp) * np.exp(-t * 6.9 / secs)
    irl[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR)); irr[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    irl /= np.sqrt((irl ** 2).sum()); irr /= np.sqrt((irr ** 2).sum())
    wl = fftconvolve(l, irl)[:N]; wr = fftconvolve(r, irr)[:N]
    return l * (1 - wet) + wl * wet * 1.0, r * (1 - wet) + wr * wet

mixL = np.zeros(N); mixR = np.zeros(N)
for name, (g, rv) in dict(piano=(1.0, 0.45), str=(0.9, 0.45), low=(0.8, 0.2), perc=(0.85, 0.3),
                          brass=(0.6, 0.4), fx=(0.7, 0.35), amb=(1, 0)).items():
    l, r = bus[name]
    if rv > 0: l, r = reverb(l, r, wet=rv)
    mixL += l * g; mixR += r * g

music = np.stack([mixL, mixR], 1)
music /= np.abs(music).max() + 1e-9
music *= 0.7

# ---------- dialogue + room ambience from the ceremony ----------
def load(src, a, b):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(a), '-t', str(b - a), '-i', src, '-ac', '2', '-ar', str(SR),
                          '-af', 'highpass=f=90,afftdn=nf=-25', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)

dia = np.zeros((N, 2))
duck = np.zeros(N)
for (t, a, b, g) in T.BITES:
    x = load('v2.mp4', a, b)
    n = len(x); fade = int(0.06 * SR)
    e = np.ones(n); e[:fade] = np.linspace(0, 1, fade); e[-fade:] = np.linspace(1, 0, fade)
    x = x * e[:, None]
    x = x / (np.sqrt((x ** 2).mean()) + 1e-9) * 0.085 * 10 ** (g / 20)
    i = int(t * SR); dia[i:i + n] += x[:N - i]
    duck[max(0, i - int(0.3 * SR)):i + n + int(0.3 * SR)] = 1

# room tone of the hall under ceremony scenes (dark hall + audience)
amb = load('v2.mp4', 7.3, 12.2)
amb = np.concatenate([amb, amb[::-1], amb, amb[::-1], amb, amb[::-1]])
amb = amb / (np.sqrt((amb ** 2).mean()) + 1e-9) * 0.018
amb = np.stack([lp(amb[:, 0], 3000), lp(amb[:, 1], 3000)], 1)
ai = int(39.0 * SR); ae = min(int(T.bar(10) * SR), ai + len(amb))
ambfull = np.zeros((N, 2)); ambfull[ai:ae] = amb[:ae - ai]
ramp = np.ones(ae - ai); r_ = int(1.5 * SR); ramp[:r_] = np.linspace(0, 1, r_); ramp[-r_:] = np.linspace(1, 0, r_)
ambfull[ai:ae] *= ramp[:, None]

# smooth ducking envelope (-9 dB)
k = int(0.25 * SR)
duck = np.convolve(duck, np.ones(k) / k, 'same')
gain = 1 - duck * (1 - 10 ** (-9 / 20))
music *= gain[:, None]

mix = music + dia + ambfull
# fade in/out
fi = int(0.5 * SR); mix[:fi] *= np.linspace(0, 1, fi)[:, None]
fo = int(3.0 * SR); end = int((T.FILM_END) * SR); mix[end - fo:end] *= np.linspace(1, 0, fo)[:, None]; mix[end:] = 0
mix = np.tanh(mix * 1.1) / 1.1
mix = mix[:int(T.FILM_END * SR)]
import wave
pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open('mix_raw.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('ok', len(mix) / SR)
