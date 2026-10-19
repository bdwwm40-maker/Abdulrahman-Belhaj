"""Generate the Libyan-Arabic voiceover, one clip per scene, with word timings.

Uses the Microsoft neural voice ar-LY-OmarNeural (Libyan Arabic, male) through
edge-tts. Writes audio/<scene>.mp3 and audio/timings.json (scene durations and
per-word offsets for subtitles).

usage: python3 voice.py [--rate -6%] [--pitch +0Hz]
"""
import argparse
import asyncio
import json
import os
import ssl
import subprocess
from pathlib import Path

import edge_tts
import edge_tts.communicate
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VOICE = "ar-LY-OmarNeural"

# edge-tts pins certifi's bundle; behind a TLS-inspecting proxy use the system CA file instead
if os.environ.get("SSL_CERT_FILE"):
    edge_tts.communicate._SSL_CTX = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
PROXY = os.environ.get("HTTPS_PROXY")


def clean(text):
    # guillemets and ellipses are for the reader; the voice reads a comma pause better
    return text.replace("«", "").replace("»", "").replace("…", "، ")


async def synth(text, out, rate, pitch):
    com = edge_tts.Communicate(clean(text), VOICE, rate=rate, pitch=pitch, boundary="WordBoundary", proxy=PROXY)
    words = []
    with open(out, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"t": chunk["offset"] / 1e7, "d": chunk["duration"] / 1e7, "w": chunk["text"]})
    return words


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


SR = 24000


def tighten(mp3, wav, words, keep=0.32, min_gap=0.45, tail=0.25):
    """Shorten pauses longer than `min_gap` to `keep` seconds and shift word times to match."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-f", "s16le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32)
    hop = int(SR * 0.01)
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode="same"))
    quiet = rms < 10 ** (-40 / 20) * 32768
    # find quiet runs between the first and last word
    start, end = int(words[0]["t"] * SR), int((words[-1]["t"] + words[-1]["d"]) * SR)
    cuts, i = [], start
    while i < end:
        if quiet[i]:
            j = i
            while j < end and quiet[j]:
                j += 1
            if (j - i) / SR > min_gap:
                pad = int(keep * SR / 2)
                cuts.append((i + pad, j - pad))
            i = j
        else:
            i += 1
    keep_parts, last = [], max(0, start - int(0.08 * SR))
    for a, b in cuts:
        keep_parts.append(x[last:a])
        last = b
    keep_parts.append(x[last:min(len(x), end + int(tail * SR))])
    y = np.concatenate(keep_parts)
    offset0 = max(0, start - int(0.08 * SR)) / SR

    def remap(t):
        s = t * SR
        removed = sum(b - a for a, b in cuts if b <= s)
        return (s - removed) / SR - offset0

    for w in words:
        w["t"] = round(remap(w["t"]), 3)
    import wave
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(np.clip(y, -32768, 32767).astype(np.int16).tobytes())
    return len(y) / SR


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", default="-6%")
    ap.add_argument("--pitch", default="+0Hz")
    a = ap.parse_args()

    script = json.loads((ROOT / "script.json").read_text())
    audio = ROOT / "audio"
    audio.mkdir(exist_ok=True)
    timings = {}
    for s in script["scenes"]:
        out = audio / f"{s['id']}.mp3"
        words = await synth(s["voice"], out, a.rate, a.pitch)
        dur = tighten(out, audio / f"{s['id']}.wav", words)
        timings[s["id"]] = {"duration": round(dur, 3), "raw": duration(out), "words": words}
        print(f"{s['id']}: {dur:.2f}s (raw {timings[s['id']]['raw']:.2f}s), {len(words)} words")
    (audio / "timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=1))
    print("total", round(sum(t["duration"] for t in timings.values()), 2), "s")


if __name__ == "__main__":
    asyncio.run(main())
