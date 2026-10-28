"""Narration in the client's own voice: voice conversion of the vowelized MSA narration.

The neural MSA narration (voice.py, script-fusha.json) carries the correct
pronunciation and timing; Seed-VC (zero-shot voice conversion, run locally on CPU)
re-voices every clip with the timbre of the client's recording. Clip lengths are
kept, so timings.json / phones.json of the source stay valid (captions and lip sync).

The conversion is stochastic, so several takes are made and `pick` keeps, per scene,
the take Whisper transcribes most accurately phrase by phrase (ties: closest to the client's voice);
the takes are time-aligned, so the chosen phrases are spliced in the pauses between them.

  python3 my_voice.py convert SEEDVC_DIR REF.wav --src audio-fusha --out build/vc/take1 --seed 1
  python3 my_voice.py pick REF.wav --takes build/vc/take* --src audio-fusha --out audio-myvoice

SEEDVC_DIR: code of the Hugging Face space "Plachta/Seed-VC" (weights download on first run).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import types
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def convert(a):
    # only dac.nn.quantize is needed; register the packages without running their __init__ (needs audiotools)
    for name, sub in (("dac", "dac"), ("dac.nn", "dac/nn")):
        m = types.ModuleType(name)
        m.__path__ = [str(Path(a.seedvc) / sub)]
        sys.modules[name] = m
    sys.path.insert(0, a.seedvc)
    src_dir, out = (ROOT / a.src).resolve(), (ROOT / a.out).resolve()
    ref_path = Path(a.ref).resolve()
    import os
    os.chdir(a.seedvc)
    import librosa
    import torch
    import torchaudio
    import yaml
    from huggingface_hub import hf_hub_download
    from hf_utils import load_custom_model_from_hf
    from modules.audio import mel_spectrogram
    from modules.bigvgan import bigvgan
    from modules.campplus.DTDNN import CAMPPlus
    from modules.commons import build_model, load_checkpoint, recursive_munch
    from transformers import AutoFeatureExtractor, WhisperModel
    torch.set_num_threads(4)

    ckpt, cfgp = load_custom_model_from_hf("Plachta/Seed-VC", "DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth",
                                           "config_dit_mel_seed_uvit_whisper_small_wavenet.yml")
    cfg = yaml.safe_load(open(cfgp))
    mp = recursive_munch(cfg["model_params"])
    model = build_model(mp, stage="DiT")
    model, _, _, _ = load_checkpoint(model, None, ckpt, load_only_params=True, ignore_modules=[], is_distributed=False)
    for k in model:
        model[k].eval()
    model.cfm.estimator.setup_caches(max_batch_size=1, max_seq_length=8192)
    sp, SR = cfg["preprocess_params"]["spect_params"], cfg["preprocess_params"]["sr"]

    def to_mel(x):
        return mel_spectrogram(x, n_fft=sp["n_fft"], win_size=sp["win_length"], hop_size=sp["hop_length"],
                               num_mels=sp["n_mels"], sampling_rate=SR, fmin=0, fmax=None, center=False)

    wname = getattr(mp.speech_tokenizer, "whisper_name", "openai/whisper-small")
    whisper = WhisperModel.from_pretrained(wname, torch_dtype=torch.float32)
    del whisper.decoder
    fe = AutoFeatureExtractor.from_pretrained(wname)
    camp = CAMPPlus(feat_dim=80, embedding_size=192)
    camp.load_state_dict(torch.load("campplus_cn_common.bin", map_location="cpu"))
    camp.eval()
    # BigVGAN's hub mixin does not match huggingface_hub 2.x; load config + weights directly
    voc = bigvgan.BigVGAN(bigvgan.load_hparams_from_json(hf_hub_download("nvidia/bigvgan_v2_22khz_80band_256x", "config.json")),
                          use_cuda_kernel=False)
    voc.load_state_dict(torch.load(hf_hub_download("nvidia/bigvgan_v2_22khz_80band_256x", "bigvgan_generator.pt"),
                                   map_location="cpu")["generator"])
    voc.remove_weight_norm()
    voc.eval()

    def wfeat(x16):
        inp = fe([x16.squeeze(0).numpy()], return_tensors="pt", return_attention_mask=True, sampling_rate=16000)
        f = whisper._mask_input_features(inp.input_features, attention_mask=inp.attention_mask)
        h = whisper.encoder(f, return_dict=True).last_hidden_state
        return h[:, :x16.size(-1) // 320 + 1]

    ref = torch.tensor(librosa.load(ref_path, sr=SR)[0][:SR * 25])[None]   # the model uses up to 25 s of reference
    ref16 = torchaudio.functional.resample(ref, SR, 16000)
    with torch.inference_mode():
        mel2 = to_mel(ref)
        fb = torchaudio.compliance.kaldi.fbank(ref16, num_mel_bins=80, dither=0, sample_frequency=16000)
        style = camp((fb - fb.mean(0, keepdim=True))[None])
        prompt, *_ = model.length_regulator(wfeat(ref16), ylens=torch.LongTensor([mel2.size(2)]), n_quantizers=3, f0=None)

    out.mkdir(parents=True, exist_ok=True)
    for src in sorted(src_dir.glob("*.wav")):
        t0 = time.time()
        torch.manual_seed(a.seed)
        x = torch.tensor(librosa.load(src, sr=SR)[0])[None]
        with torch.inference_mode():
            mel = to_mel(x)
            cond, *_ = model.length_regulator(wfeat(torchaudio.functional.resample(x, SR, 16000)),
                                              ylens=torch.LongTensor([mel.size(2)]), n_quantizers=3, f0=None)
            cat = torch.cat([prompt, cond], 1)
            y = model.cfm.inference(cat, torch.LongTensor([cat.size(1)]), mel2, style, None, a.steps, inference_cfg_rate=a.cfg)
            y = voc(y[:, :, mel2.size(-1):].float())[0][0].numpy()
        with wave.open(str(src)) as f:
            n, sr = f.getnframes(), f.getframerate()
        y = librosa.resample(y, orig_sr=SR, target_sr=sr)
        y = np.pad(y, (0, max(0, n - len(y))))[:n]                          # same length as the source clip
        with wave.open(str(out / src.name), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sr)
            f.writeframes(np.clip(y / (np.abs(y).max() + 1e-9) * 0.89 * 32767, -32768, 32767).astype(np.int16).tobytes())
        print(f"{src.stem}: {n / sr:.2f}s in {time.time() - t0:.0f}s", flush=True)


def norm(t):
    t = re.sub(r"[ً-ْـ]", "", t)
    t = re.sub(r"[إأآ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
    return "".join(re.sub(r"[^ء-ي ]", "", t).split())


def letter_error(ref, hyp):
    d = np.arange(len(hyp) + 1)
    for i, r in enumerate(ref, 1):
        prev = d.copy()
        d[0] = i
        for j, h in enumerate(hyp, 1):
            d[j] = min(prev[j] + 1, d[j - 1] + 1, prev[j - 1] + (r != h))
    return d[-1] / max(1, len(ref))


def phrases(text, words, x, sr):
    """Cut points (samples) between the punctuation phrases of a line, placed at the quietest spot of the pause."""
    parts = [q.strip() for q in re.split(r"(?<=[،,.!؟?…])\s+", text.replace("«", "").replace("»", "")) if q.strip()]
    n_txt, n_tts = sum(len(q.split()) for q in parts), len(words)
    first, i = [], 0
    for q in parts:
        first.append(min(n_tts - 1, round(i * n_tts / max(n_txt, 1))))
        i += len(q.split())
    hop = int(sr * 0.01)
    rms = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, mode="same"))
    cuts = [0]
    for j in first[1:]:
        a = int((words[j - 1]["t"] + words[j - 1]["d"]) * sr) if j > 0 else 0
        b = int(words[j]["t"] * sr)
        a, b = min(a, b), max(a, b)
        cuts.append(a + int(np.argmin(rms[a:b + 1])) if b > a else b)
    cuts.append(len(x))
    return parts, cuts


def pick(a):
    """Per scene, per phrase: keep the take that Whisper transcribes most accurately, splice in the pauses."""
    from faster_whisper import WhisperModel
    from resemblyzer import VoiceEncoder, preprocess_wav
    script = {s["id"]: s["voice"] for s in json.loads((ROOT / a.script).read_text())["scenes"]}
    timings = json.loads((ROOT / a.src / "timings.json").read_text())
    enc = VoiceEncoder("cpu")
    me = enc.embed_utterance(preprocess_wav(load(a.ref), 16000))
    asr = WhisperModel("medium", device="cpu", compute_type="int8")
    out = ROOT / a.out
    out.mkdir(exist_ok=True)
    SR = 24000
    report = {}
    for sid, text in script.items():
        src = load(ROOT / a.src / f"{sid}.wav", SR)
        parts, cuts = phrases(text, timings[sid]["words"], src, SR)
        takes = []
        for d in a.takes:
            p = Path(d) / f"{sid}.wav"
            if p.exists():
                y = load(p, SR)[:len(src)]
                y = np.pad(y, (0, len(src) - len(y)))
                loud = y[np.abs(y) > 0.02]
                y = y * (0.12 / (np.sqrt(np.mean(loud ** 2)) + 1e-9))      # same speech level in every take
                sim = float(np.dot(me, enc.embed_utterance(preprocess_wav(load(p), 16000))))
                takes.append((str(d), y, sim))
        rows, chosen = [], []
        for k, q in enumerate(parts):
            a0, b0 = cuts[k], cuts[k + 1]
            cand = []
            for name, y, sim in takes:
                seg = y[max(0, a0 - 1200):b0 + 1200]                       # a little context on both sides
                seg16 = load_np(seg, SR)
                heard = " ".join(s.text for s in asr.transcribe(seg16, language="ar", beam_size=5)[0]).strip()
                cand.append({"take": name, "error": round(letter_error(norm(q), norm(heard)), 4),
                             "similarity": round(sim, 3), "heard": heard})
            best = min(cand, key=lambda r: (r["error"], -r["similarity"]))
            chosen.append(best["take"])
            rows.append({"phrase": q, "chosen": best["take"], "takes": cand})
        # splice: crossfade 20 ms at each cut (cuts sit in pauses)
        y_out = np.zeros(len(src), np.float32)
        fade = int(0.02 * SR)
        for k in range(len(parts)):
            y = next(t[1] for t in takes if t[0] == chosen[k])
            a0, b0 = cuts[k], cuts[k + 1]
            w = np.zeros(len(src), np.float32)
            w[a0:b0] = 1
            if k > 0:
                w[a0 - fade:a0 + fade] = np.linspace(0, 1, 2 * fade)
            if k + 1 < len(parts):
                w[b0 - fade:b0 + fade] = np.linspace(1, 0, 2 * fade)
            y_out += y * w
        y_out = y_out / (np.abs(y_out).max() + 1e-9) * 0.89
        with wave.open(str(out / f"{sid}.wav"), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(SR)
            f.writeframes((y_out * 32767).astype(np.int16).tobytes())
        err = np.mean([min(c["error"] for c in r["takes"]) for r in rows])
        report[sid] = rows
        print(f"{sid}: {len(parts)} phrases from takes {[Path(c).name for c in chosen]}  mean phrase error {err * 100:.1f}%", flush=True)
    for f in ("timings.json", "phones.json"):                                  # same clip lengths as the source
        shutil.copy(ROOT / a.src / f, out / f)
    (out / "takes.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))


def load_np(y, sr):
    """Resample a float clip to 16 kHz for Whisper."""
    import librosa
    return librosa.resample(y.astype(np.float32), orig_sr=sr, target_sr=16000)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert")
    c.add_argument("seedvc")
    c.add_argument("ref")
    c.add_argument("--src", default="audio-fusha")
    c.add_argument("--out", required=True)
    c.add_argument("--steps", type=int, default=15)
    c.add_argument("--cfg", type=float, default=0.7)
    c.add_argument("--seed", type=int, default=0)
    p = sub.add_parser("pick")
    p.add_argument("ref")
    p.add_argument("--takes", nargs="+", required=True)
    p.add_argument("--src", default="audio-fusha")
    p.add_argument("--script", default="script-fusha.json")
    p.add_argument("--out", default="audio-myvoice")
    a = ap.parse_args()
    convert(a) if a.cmd == "convert" else pick(a)


if __name__ == "__main__":
    main()
