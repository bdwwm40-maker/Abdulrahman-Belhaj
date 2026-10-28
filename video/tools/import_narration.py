"""Import a continuous narration (one recorded / generated take) and split it into the scene clips.

The whole take is force-aligned (torchaudio MMS aligner) against the romanized words of
every scene (script "roman" field, same word count as "voice"). Scene cuts are put at the
quietest point between the last word of a scene and the first word of the next, so the
clips, laid end to end (build_timeline.py --gap 0), give back the take unchanged.

Writes <out>/<scene>.wav (--sr, default 24 kHz), <out>/timings.json (word times, as voice.py) and
<out>/phones.json (visemes for face_frames.py, as lipsync.py).

usage: python3 import_narration.py TAKE.wav --script script-libya-v4.json --out audio-libya
"""
import argparse
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
import torch
import torchaudio

ROOT = Path(__file__).resolve().parents[1]
SR = 24000
UNIT = re.compile(r"sh|kh|gh|th|dh|[a-z']")
VIS = {"a": "A", "e": "I", "i": "I", "o": "U", "u": "U", "b": "M", "m": "M", "p": "M", "f": "F", "v": "F",
       "w": "W", "y": "I", "k": "K", "g": "K", "q": "K", "h": "K", "'": "K", "kh": "K", "gh": "K"}


def load(path, sr):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("take")
    ap.add_argument("--script", default="script-libya-v4.json")
    ap.add_argument("--out", default="audio-libya")
    ap.add_argument("--sr", type=int, default=24000)
    a = ap.parse_args()
    global SR
    SR = a.sr

    script = json.loads((ROOT / a.script).read_text())["scenes"]
    words = [(s["id"], w) for s in script for w in s["roman"].split()]
    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=False).eval()
    tok, aligner = bundle.get_tokenizer(), bundle.get_aligner()
    x16 = torch.from_numpy(load(a.take, 16000))
    with torch.inference_mode():
        em = torch.log_softmax(model(x16[None])[0], dim=-1)
    spans = aligner(em[0], tok([w for _, w in words]))
    sec = x16.shape[0] / 16000 / em.shape[1]

    # per word: start / end and the timed phone units
    W = []
    for (sid, w), sp in zip(words, spans):
        units, k = [], 0
        for u in UNIT.findall(w):
            ch = sp[k:k + len(u)]
            k += len(u)
            units.append({"p": u, "v": VIS.get(u, "S"), "t": ch[0].start * sec, "e": ch[-1].end * sec})
        W.append({"scene": sid, "w": w, "t": sp[0].start * sec, "e": sp[-1].end * sec, "units": units,
                  "score": float(np.mean([s.score for s in sp]))})

    x = load(a.take, SR)
    hop = int(SR * 0.01)
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode="same"))
    ids = [s["id"] for s in script]
    cuts = [0]
    for prev, nxt in zip(ids, ids[1:]):
        last = max(w["e"] for w in W if w["scene"] == prev)
        first = min(w["t"] for w in W if w["scene"] == nxt)
        lo, hi = int(last * SR), int(first * SR)
        if hi <= lo:                                          # no pause (the words run on): cut at the boundary
            cuts.append(lo)
        else:
            cuts.append(lo + int(np.argmin(rms[lo:hi + 1])))
    cuts.append(len(x))

    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    timings, phones = {}, {}
    for i, sid in enumerate(ids):
        c0, c1 = cuts[i], cuts[i + 1]
        with wave.open(str(out / f"{sid}.wav"), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(SR)
            f.writeframes(np.clip(x[c0:c1] * 32767, -32768, 32767).astype(np.int16).tobytes())
        t0 = c0 / SR
        ws = [w for w in W if w["scene"] == sid]
        timings[sid] = {"duration": round((c1 - c0) / SR, 3), "start_in_take": round(t0, 3),
                        "words": [{"t": round(w["t"] - t0, 3), "d": round(w["e"] - w["t"], 3), "w": v}
                                  for w, v in zip(ws, next(s["voice"] for s in script if s["id"] == sid).split())]}
        phones[sid] = [{"p": u["p"], "v": u["v"], "t": round(u["t"] - t0, 3), "e": round(u["e"] - t0, 3)}
                       for w in ws for u in w["units"]]
        print(f"{sid}: {t0:6.2f} - {c1 / SR:6.2f}s  {len(ws)} words  align {np.mean([w['score'] for w in ws]):.2f}")
    (out / "timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=1))
    (out / "phones.json").write_text(json.dumps(phones, ensure_ascii=False))


if __name__ == "__main__":
    main()
