"""Phone-level timing for lip sync: vowelized Arabic -> phones -> forced alignment on the voice clips.

Each scene line in the script is fully vowelized, so its pronunciation can be read
off the text: every letter becomes a consonant phone, every short-vowel mark a vowel,
long vowels / shadda / tanween / sun letters / pausal endings are handled. The phones
are romanized and aligned to <audio>/<scene>.wav with torchaudio's MMS forced aligner
(multilingual wav2vec2, CTC), which gives each phone a start and end time.

Writes <audio>/phones.json: {scene: [{"p": phone, "v": viseme, "l": letter, "t": start, "e": end}, ...]}
(l is the written consonant for consonant phones, empty for vowels)

Visemes: A open vowel, I spread vowel, U rounded vowel, M closed lips (b m),
F lip-to-teeth (f), W rounded glide (w), S teeth (s z t d n l r ...), K back consonant.

usage: python3 lipsync.py --script script-fusha.json --audio audio-fusha
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import torch
import torchaudio

ROOT = Path(__file__).resolve().parents[1]

FATHA, DAMMA, KASRA = "َ", "ُ", "ِ"
TANWEEN = {"ً": FATHA, "ٌ": DAMMA, "ٍ": KASRA}
SHADDA, SUKUN = "ّ", "ْ"
VOWEL_OF = {FATHA: "a", DAMMA: "u", KASRA: "i"}
SUN = set("تثدذرزسشصضطظلن")
# consonant -> (romanization for the aligner, viseme)
CONS = {
    "ب": ("b", "M"), "م": ("m", "M"), "ف": ("f", "F"), "و": ("w", "W"),
    "ت": ("t", "S"), "ث": ("th", "S"), "د": ("d", "S"), "ذ": ("dh", "S"), "ر": ("r", "S"), "ز": ("z", "S"),
    "س": ("s", "S"), "ش": ("sh", "S"), "ص": ("s", "S"), "ض": ("d", "S"), "ط": ("t", "S"), "ظ": ("z", "S"),
    "ل": ("l", "S"), "ن": ("n", "S"), "ي": ("y", "I"), "ج": ("j", "S"),
    "ك": ("k", "K"), "ق": ("q", "K"), "خ": ("kh", "K"), "غ": ("gh", "K"), "ح": ("h", "K"), "ه": ("h", "K"),
    "ع": ("'", "K"), "ء": ("'", "K"), "أ": ("'", "K"), "إ": ("'", "K"), "ؤ": ("'", "K"), "ئ": ("'", "K"),
    "آ": ("'", "K"), "ة": ("t", "S"),
}
VIS_OF_VOWEL = {"a": "A", "i": "I", "u": "U"}
# loanwords (program names), written without full vowel marks in the script
LOAN = {
    "وورد": [("w", "W"), ("o", "U"), ("r", "S"), ("d", "S")],
    "إكسل": [("'", "K"), ("e", "I"), ("k", "K"), ("s", "S"), ("e", "I"), ("l", "S")],
    "باور": [("b", "M"), ("a", "A"), ("w", "W"), ("a", "A"), ("r", "S")],
    "بوينت": [("b", "M"), ("o", "U"), ("y", "I"), ("n", "S"), ("t", "S")],
}


def tokens(word):
    """[(letter, set_of_marks)] for one written word."""
    out = []
    for ch in word:
        if "ً" <= ch <= "ْ":
            if out:
                out[-1][1].add(ch)
        elif ch == "ـ":
            continue
        else:
            out.append([ch, set()])
    return out


def word_phones(word, first_in_phrase):
    """Phones [(roman, viseme)] of one vowelized word."""
    bare = re.sub(r"[ً-ْ]", "", word)
    for k, v in LOAN.items():
        if bare in (k, "و" + k):
            return ([("w", "W"), ("a", "A")] if bare != k else []) + v   # with the conjunction وَ
    ph = []
    tk = tokens(word)
    for i, (ch, marks) in enumerate(tk):
        prev = tk[i - 1] if i else None
        nxt = tk[i + 1] if i + 1 < len(tk) else None
        vowel = next((VOWEL_OF[m] for m in marks if m in VOWEL_OF), None)
        tanw = next((TANWEEN[m] for m in marks if m in TANWEEN), None)
        if ch == "ا":
            if i == 1 and tk[0][0] in "وفبكل" and nxt and (nxt[0] == "ل" or SUKUN in nxt[1]):
                continue                              # wasl of the article after a one-letter prefix (وَال، بِال)
            if prev and (FATHA in prev[1] or "ً" in prev[1]):
                if "ً" in prev[1]:
                    continue                          # seat of fathatan: silent
                ph.append(("a", "A"))                 # long aa
            elif i == 0:
                if first_in_phrase:
                    ph.append(("a", "A"))             # hamzat al-wasl, pronounced only at a phrase start
            elif i == 2 and tk[0][0] == "ا" and tk[1][0] == "ل" and not marks:
                ph.append(("i", "I"))                 # al- + wasl verbal noun: al-ijtima'
            else:
                ph.append(("a", "A"))
            continue
        if ch == "ى":
            ph.append(("a", "A"))
            continue
        if ch == "آ":
            ph += [("'", "K"), ("a", "A")]
            continue
        if ch == "ل" and not marks and nxt and nxt[0] in SUN and SHADDA in nxt[1]:
            continue                                  # sun letter: the l assimilates
        if ch in "وي" and not vowel and not tanw and SHADDA not in marks and prev:
            pv = next((VOWEL_OF[m] for m in prev[1] if m in VOWEL_OF), None)
            bare_prev = not (prev[1] & {FATHA, DAMMA, KASRA, SUKUN, SHADDA})
            if SUKUN not in marks and (pv == ("u" if ch == "و" else "i") or bare_prev):
                ph.append(("u", "U") if ch == "و" else ("i", "I"))   # long uu / ii
                continue
        if ch == "ة" and not vowel and not tanw:
            continue                                  # pausal ta marbuta: (almost) silent h
        rom, vis = CONS.get(ch, ("", "S"))
        if not rom:
            continue
        ph.append((rom, vis, ch))
        if SHADDA in marks:
            ph.append((rom, vis, ch))                 # geminate
        if vowel:
            ph.append((vowel, VIS_OF_VOWEL[vowel]))
        elif tanw:
            v = VOWEL_OF[tanw]
            ph += [(v, VIS_OF_VOWEL[v]), ("n", "S")]
    return ph


def line_phones(text):
    """Words of a line -> list of phone lists (one per spoken word)."""
    text = text.replace("«", "").replace("»", "").replace("…", "،")
    words, first = [], True
    for w in text.split():
        core = re.sub(r"[^ء-ْ]", "", w)
        if core:
            words.append((w, word_phones(core, first)))
        first = bool(re.search(r"[.!؟?،,:]$", w))
    return words


def load(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return torch.from_numpy(np.frombuffer(raw, np.int16).astype(np.float32) / 32768)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="script-fusha.json")
    ap.add_argument("--audio", default="audio-fusha")
    a = ap.parse_args()

    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=False).eval()
    tokenizer, aligner = bundle.get_tokenizer(), bundle.get_aligner()
    script = json.loads((ROOT / a.script).read_text())
    out = {}
    for s in script["scenes"]:
        words = [(w, ph) for w, ph in line_phones(s["voice"]) if ph]
        roman = ["".join(r for r, *_ in ph) for _, ph in words]
        x = load(ROOT / a.audio / f"{s['id']}.wav")
        with torch.inference_mode():
            em, _ = model(x[None])
            em = torch.log_softmax(em, dim=-1)
        spans = aligner(em[0], tokenizer(roman))
        sec = x.shape[0] / 16000 / em.shape[1]
        phones = []
        for (w, ph), sp in zip(words, spans):
            k = 0
            for r, v, *letter in ph:
                chunk = sp[k:k + len(r)]
                k += len(r)
                phones.append({"p": r, "v": v, "l": letter[0] if letter else "",
                               "t": round(chunk[0].start * sec, 3), "e": round(chunk[-1].end * sec, 3)})
        out[s["id"]] = phones
        score = float(np.mean([t.score for sp in spans for t in sp]))
        print(f"{s['id']}: {len(phones)} phones, {len(words)} words, align score {score:.2f}")
    (ROOT / a.audio / "phones.json").write_text(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
