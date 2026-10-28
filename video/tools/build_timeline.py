"""Lay the scene voice clips on one timeline and export everything the stage needs.

Inputs : ../script.json, ../audio/<scene>.wav, ../audio/timings.json
Outputs: ../build/voice.wav      full narration track
         ../build/music.wav      procedural music bed under the voice (--music upbeat|pad)
         ../build/timeline.js    window.TL = {fps, duration, scenes[], captions[], env[]}
"""
import json
import re
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FPS = 30
SR = 24000
INTRO = 3.4          # logo intro before the first line
GAP = {"s": 0.55, "c": 0.35}
OUTRO = 2.6          # hold on the end card after the last line


def read_wav(p):
    with wave.open(str(p)) as f:
        return np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32)


def write_wav(p, x, sr=SR, ch=1):
    with wave.open(str(p), "wb") as f:
        f.setnchannels(ch)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes())


def chunks(text, words):
    """Split a line into caption chunks at punctuation; time each from its first word."""
    parts = [p.strip() for p in re.split(r"(?<=[،,.!؟?…])\s+", text.replace("«", "").replace("»", "")) if p.strip()]
    out, i = [], 0
    n_tts = len(words)
    n_txt = sum(len(p.split()) for p in parts)
    for p in parts:
        k = len(p.split())
        # map text-word index to tts-word index (they normally match 1:1)
        j = min(n_tts - 1, round(i * n_tts / max(n_txt, 1)))
        # captions read cleaner without short-vowel marks; the shadda stays
        out.append({"text": re.sub(r"[ً-ِْ]", "", p), "t": words[j]["t"]})
        i += k
    return out


def pad_music(total, sr=SR):
    """Soft evolving pad: Am - F - C - G, slow attack, gentle shimmer. Very quiet bed."""
    t = np.arange(int(total * sr)) / sr
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    bar = 4.0
    y = np.zeros_like(t)
    for k, ch in enumerate(chords * int(np.ceil(total / (bar * 4)) + 1)):
        t0 = k * bar
        if t0 > total:
            break
        m = (t >= t0) & (t < t0 + bar + 1.5)
        tt = t[m] - t0
        env = np.minimum(1, tt / 1.2) * np.minimum(1, np.maximum(0, (bar + 1.5 - tt) / 1.5))
        for f in ch:
            y[m] += env * (np.sin(2 * np.pi * f * tt) * 0.5 + np.sin(2 * np.pi * f * 2 * tt) * 0.12
                           + np.sin(2 * np.pi * f * 0.5 * tt) * 0.25)
    shimmer = np.sin(2 * np.pi * 0.11 * t) * 0.5 + 0.5
    y *= 0.8 + 0.2 * shimmer
    fade = np.minimum(1, t / 2.0) * np.minimum(1, (total - t) / 2.5)
    y = y * fade
    return y / (np.abs(y).max() + 1e-9) * 32767 * 0.9


MSR = 44100  # music is rendered at full bandwidth so the shaker stays crisp


def upbeat_music(total, sr=MSR, bpm=112):
    """Bright pop bed: C-G-Am-F in C major, plucked 8th-note arpeggio, bass, soft kick/clap/shaker."""
    n = int(total * sr)
    y = np.zeros(n)
    beat = 60 / bpm
    bar = 4 * beat
    rng = np.random.default_rng(3)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    chords = [(48, [60, 64, 67, 72]), (43, [59, 62, 67, 71]), (45, [57, 60, 64, 69]), (41, [57, 60, 65, 69])]

    def add(sig, t0, gain):
        i = int(t0 * sr)
        if i >= n:
            return
        j = min(n, i + len(sig))
        y[i:j] += sig[:j - i] * gain

    def tone(f, dur, decay, harm=(1, 0.35, 0.12)):
        t = np.arange(int(dur * sr)) / sr
        s = sum(a * np.sin(2 * np.pi * f * (k + 1) * t) for k, a in enumerate(harm))
        return s * np.exp(-t / decay) * np.minimum(1, t / 0.004)

    kick_t = np.arange(int(0.28 * sr)) / sr
    kick = np.sin(2 * np.pi * (50 * kick_t + 70 * 0.04 * (1 - np.exp(-kick_t / 0.04)))) * np.exp(-kick_t / 0.11)
    clap = rng.normal(0, 1, int(0.18 * sr)) * np.exp(-np.arange(int(0.18 * sr)) / sr / 0.045)
    clap = np.convolve(clap, [1, -0.95], mode="same")  # crude high-pass
    shake = rng.normal(0, 1, int(0.05 * sr)) * np.exp(-np.arange(int(0.05 * sr)) / sr / 0.012)
    shake = np.convolve(shake, [1, -1], mode="same")

    nbars = int(np.ceil(total / bar))
    for b in range(nbars):
        root, notes = chords[b % 4]
        t0 = b * bar
        # pad chord (soft, sustained)
        for m in notes[:3]:
            add(tone(hz(m), bar + 0.4, 1.6, (1, 0.2)), t0, 0.05)
        # bass on the beat, octave pop on the off-beat
        for k in range(8):
            f = hz(root - 12 if k % 2 == 0 else root)
            add(tone(f, beat * 0.5, 0.18, (1, 0.5, 0.25)), t0 + k * beat / 2, 0.20 if k % 2 == 0 else 0.11)
        # plucked arpeggio, up-down pattern
        pattern = [0, 1, 2, 3, 2, 1, 2, 3]
        for k, p in enumerate(pattern):
            add(tone(hz(notes[p] + 12), 0.5, 0.16), t0 + k * beat / 2, 0.075)
        # drums
        for k in range(4):
            add(kick, t0 + k * beat, 0.32 if k % 2 == 0 else 0.18)
            if k % 2 == 1:
                add(clap, t0 + k * beat, 0.08)
        for k in range(16):
            add(shake, t0 + k * beat / 4, 0.035 if k % 2 else 0.02)

    t = np.arange(n) / sr
    y *= np.minimum(1, t / 1.5) * np.minimum(1, np.maximum(0, (total - t) / 2.5))
    return y / (np.abs(y).max() + 1e-9) * 32767 * 0.9


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="script.json")
    ap.add_argument("--audio", default="audio")
    ap.add_argument("--music", default="upbeat", choices=["upbeat", "pad"])
    a = ap.parse_args()

    script = json.loads((ROOT / a.script).read_text())
    timings = json.loads((ROOT / a.audio / "timings.json").read_text())
    build = ROOT / "build"
    build.mkdir(exist_ok=True)

    scenes, captions, clips = [], [], []
    t = INTRO
    for s in script["scenes"]:
        tm = timings[s["id"]]
        x = read_wav(ROOT / a.audio / f"{s['id']}.wav")
        start = t
        end = start + len(x) / SR
        clips.append((start, x))
        scenes.append({"id": s["id"], "start": round(start, 3), "end": round(end, 3),
                       "title": s["title"], "subtitle": s.get("subtitle", ""),
                       "words": [{"t": round(start + w["t"], 3), "w": w["w"]} for w in tm["words"]]})
        for c in chunks(s["voice"], tm["words"]):
            captions.append({"t": round(start + c["t"], 3), "text": c["text"], "scene": s["id"]})
        t = end + GAP[s["id"][0]]
    total = scenes[-1]["end"] + OUTRO
    # caption end = next caption start (or its scene end + 0.4s)
    for i, c in enumerate(captions):
        sc = next(s for s in scenes if s["id"] == c["scene"])
        nxt = captions[i + 1]["t"] if i + 1 < len(captions) and captions[i + 1]["scene"] == c["scene"] else sc["end"] + 0.25
        c["end"] = round(nxt, 3)

    voice = np.zeros(int(total * SR) + SR)
    for start, x in clips:
        i = int(start * SR)
        voice[i:i + len(x)] += x
    voice = voice[:int(total * SR)]
    write_wav(build / "voice.wav", voice)
    if a.music == "upbeat":
        write_wav(build / "music.wav", upbeat_music(total), sr=MSR)
    else:
        write_wav(build / "music.wav", pad_music(total))

    # per-frame loudness envelope (0..1), lightly smoothed, drives the character's "talking" motion
    hop = SR // FPS
    n = int(total * FPS)
    rms = np.array([np.sqrt(np.mean(voice[i * hop:(i + 1) * hop] ** 2) + 1e-9) for i in range(n)])
    env = np.clip(rms / (np.percentile(rms[rms > 50], 95) + 1e-9), 0, 1)
    sm = np.convolve(env, np.ones(3) / 3, mode="same")

    tl = {"fps": FPS, "duration": round(total, 3), "intro": INTRO, "scenes": scenes,
          "captions": captions, "env": [round(float(v), 3) for v in sm]}
    (build / "timeline.js").write_text("window.TL = " + json.dumps(tl, ensure_ascii=False) + ";\n")
    # face patches belong to the previous timeline; face_frames.py writes a new set
    (build / "face.js").unlink(missing_ok=True)
    print(f"duration {total:.2f}s, {len(scenes)} scenes, {len(captions)} captions, {n} frames")


if __name__ == "__main__":
    main()
