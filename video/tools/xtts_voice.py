"""Narrate the script directly in the client's cloned voice with XTTS v2 (run locally).

XTTS is stochastic, so every scene is generated --takes times; each take is
transcribed with Whisper and the take with the fewest word errors against the
script wins (ties go to the take closest to the reference voice). Word timings for
the subtitles come from Whisper's word timestamps on the chosen take.

Writes <out>/<scene>.wav, <out>/timings.json (same layout as voice.py) and
<out>/takes.json (scores of every take).

XTTS v2 weights are under the Coqui Public Model License (non-commercial use).

usage: python3 xtts_voice.py REF.wav [--script script-msa.json] [--out audio-msa-xtts] [--takes 3]
"""
import argparse
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SR = 24000


def load(path, sr):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def save(path, x, sr=SR):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(np.clip(x * 32767, -32768, 32767).astype(np.int16).tobytes())


def norm(t):
    t = re.sub(r"[ً-ْـ]", "", t)
    t = re.sub(r"[إأآ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"[^ء-ي ]", "", t).split()


def wer(ref, hyp):
    """Letter error rate with spaces removed, so Whisper's word splitting doesn't count as an error."""
    ref, hyp = "".join(ref), "".join(hyp)
    d = np.arange(len(hyp) + 1)
    for i, r in enumerate(ref, 1):
        prev = d.copy()
        d[0] = i
        for j, h in enumerate(hyp, 1):
            d[j] = min(prev[j] + 1, d[j - 1] + 1, prev[j - 1] + (r != h))
    return d[-1] / max(1, len(ref))


def trim(x, sr=SR, thr_db=-42, pad=0.15, tail=0.25):
    """Cut leading/trailing silence."""
    hop = int(sr * 0.01)
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode="same"))
    loud = np.nonzero(rms > 10 ** (thr_db / 20))[0]
    if not len(loud):
        return x, 0.0
    a = max(0, loud[0] - int(pad * sr))
    b = min(len(x), loud[-1] + int(tail * sr))
    return x[a:b], a / sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("--script", default="script-msa.json")
    ap.add_argument("--out", default="audio-msa-xtts")
    ap.add_argument("--takes", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--only", nargs="*", help="regenerate just these scenes, keep the rest")
    a = ap.parse_args()

    from TTS.api import TTS
    from faster_whisper import WhisperModel
    from resemblyzer import VoiceEncoder, preprocess_wav

    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    asr = WhisperModel("small", device="cpu", compute_type="int8")
    enc = VoiceEncoder("cpu")
    ref_emb = enc.embed_utterance(preprocess_wav(load(a.ref, 16000), 16000))

    out = ROOT / a.out
    out.mkdir(exist_ok=True)
    script = json.loads((ROOT / a.script).read_text())
    timings, report = {}, {}
    if a.only:
        timings = json.loads((out / "timings.json").read_text())
        report = json.loads((out / "takes.json").read_text())
    for s in script["scenes"]:
        if a.only and s["id"] not in a.only:
            continue
        text = s["voice"].replace("«", "").replace("»", "").replace("…", "، ")
        ref_words = norm(s["voice"])
        best = None
        report[s["id"]] = []
        for k in range(a.takes):
            tmp = out / f"{s['id']}.take{k}.wav"
            tts.tts_to_file(text=text, speaker_wav=a.ref, language="ar", file_path=str(tmp),
                            temperature=a.temperature)
            x16 = load(tmp, 16000)
            segs, _ = asr.transcribe(x16, language="ar", beam_size=5)
            heard = " ".join(seg.text for seg in segs)
            err = wer(ref_words, norm(heard))
            sim = float(np.dot(ref_emb, enc.embed_utterance(preprocess_wav(x16, 16000))))
            report[s["id"]].append({"take": k, "wer": round(err, 3), "similarity": round(sim, 3), "heard": heard.strip()})
            if best is None or (err, -sim) < (best[0], -best[1]):
                best = (err, sim, tmp)
        x, cut = trim(load(best[2], SR))
        x = x / (np.abs(x).max() + 1e-9) * 0.89
        save(out / f"{s['id']}.wav", x)
        segs, _ = asr.transcribe(load(out / f"{s['id']}.wav", 16000), language="ar", beam_size=5, word_timestamps=True)
        words = [{"t": round(w.start, 3), "d": round(w.end - w.start, 3), "w": w.word.strip()}
                 for seg in segs for w in (seg.words or [])]
        if not words:
            words = [{"t": 0.0, "d": len(x) / SR, "w": text}]
        timings[s["id"]] = {"duration": round(len(x) / SR, 3), "words": words}
        for p in out.glob(f"{s['id']}.take*.wav"):
            p.unlink()
        print(f"{s['id']}: {len(x) / SR:.2f}s  best take wer {best[0] * 100:.0f}%  similarity {best[1]:.3f}", flush=True)
    timings = {s["id"]: timings[s["id"]] for s in script["scenes"]}  # keep script order
    (out / "timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=1))
    (out / "takes.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    total = sum(t["duration"] for t in timings.values())
    print("total", round(total, 2), "s")


if __name__ == "__main__":
    main()
