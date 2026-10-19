"""Lay the scene voice clips on one timeline and export everything the stage needs.

Inputs : ../script.json, ../audio/<scene>.wav, ../audio/timings.json
Outputs: ../build/voice.wav      full narration track
         ../build/music.wav      quiet procedural pad (optional bed under the voice)
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
        out.append({"text": p, "t": words[j]["t"]})
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


def main():
    script = json.loads((ROOT / "script.json").read_text())
    timings = json.loads((ROOT / "audio" / "timings.json").read_text())
    build = ROOT / "build"
    build.mkdir(exist_ok=True)

    scenes, captions, clips = [], [], []
    t = INTRO
    for s in script["scenes"]:
        tm = timings[s["id"]]
        x = read_wav(ROOT / "audio" / f"{s['id']}.wav")
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
    print(f"duration {total:.2f}s, {len(scenes)} scenes, {len(captions)} captions, {n} frames")


if __name__ == "__main__":
    main()
