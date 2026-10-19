"""Turn the neural MSA narration into the client's own voice (voice conversion).

Every scene clip in <dir>/<scene>.wav (made by voice.py) is converted with
OpenVoice v2 (MIT licence, run locally through coqui-tts) so it takes the timbre of
the reference recording, while the delivery, pronunciation and timing of the
source stay the same. Because the length of each clip is kept, the word timings in
<dir>/timings.json still match and the subtitles stay in sync.

The originals are kept as <scene>.src.wav.

usage: python3 clone_voice.py REF.wav [--dir audio-msa] [--model openvoice_v2]
"""
import argparse
import json
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SR = 24000
MODELS = {
    "openvoice_v2": "voice_conversion_models/multilingual/multi-dataset/openvoice_v2",
    "openvoice_v1": "voice_conversion_models/multilingual/multi-dataset/openvoice_v1",
}


def load(path, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32)


def save(path, x, sr=SR):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("--dir", default="audio-msa")
    ap.add_argument("--model", default="openvoice_v2", choices=MODELS)
    a = ap.parse_args()

    from TTS.api import TTS
    vc = TTS(MODELS[a.model])

    d = ROOT / a.dir
    timings = json.loads((d / "timings.json").read_text())
    for sid in timings:
        src = d / f"{sid}.src.wav"
        if not src.exists():
            shutil.copy(d / f"{sid}.wav", src)
        tmp = d / f"{sid}.vc.wav"
        vc.voice_conversion_to_file(source_wav=str(src), target_wav=a.ref, file_path=str(tmp))
        x, y = load(src), load(tmp)
        # keep the exact source length so the word timings stay valid
        y = y[:len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))
        # match loudness of the source clip
        rx, ry = np.sqrt(np.mean(x ** 2)) + 1e-9, np.sqrt(np.mean(y ** 2)) + 1e-9
        save(d / f"{sid}.wav", y * (rx / ry))
        tmp.unlink()
        print(sid, f"{len(x) / SR:.2f}s")


if __name__ == "__main__":
    main()
