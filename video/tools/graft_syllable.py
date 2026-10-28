"""Replace one syllable of a recorded take with another syllable of the same speaker.

Used to turn «أنتي» (feminine) into «أنتَ» (masculine) in the ElevenLabs take: the «تي»
of the word is replaced by the speaker's own «تا» (from «وتابعنا»), with the original
duration, pitch contour (PSOLA, Praat) and loudness contour of the replaced syllable.

  python3 graft_syllable.py TAKE.wav OUT.wav --target 78.105 78.240 --donor 73.545 73.660

target: t burst .. end of the vowel to replace; donor: burst .. end of the donor vowel.
"""
import argparse

import numpy as np
import parselmouth
from parselmouth.praat import call


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("take")
    ap.add_argument("out")
    ap.add_argument("--target", type=float, nargs=2, required=True)
    ap.add_argument("--donor", type=float, nargs=2, required=True)
    a = ap.parse_args()
    (T0, T1), (D0, D1) = a.target, a.donor

    snd = parselmouth.Sound(a.take)
    sr = snd.sampling_frequency
    donor = snd.extract_part(D0, D1, preserve_times=False)
    target = snd.extract_part(T0, T1, preserve_times=False)
    dd, td = donor.duration, target.duration

    # length: keep the 20 ms burst, stretch / squeeze the vowel
    k = (td - 0.025) / (dd - 0.025)
    m = call(donor, "To Manipulation", 0.005, 75, 600)
    dur = call("Create DurationTier", "dur", 0, dd)
    for t, v in ((0, 1.0), (0.02, 1.0), (0.03, k), (dd, k)):
        call(dur, "Add point", t, v)
    call([m, dur], "Replace duration tier")
    d2 = call(m, "Get resynthesis (overlap-add)")

    # pitch: the contour of the replaced syllable
    pt = call(call(target, "To Manipulation", 0.005, 75, 600), "Extract pitch tier")
    scale = d2.duration / td
    newpt = call("Create PitchTier", "p", 0, d2.duration)
    for i in range(1, call(pt, "Get number of points") + 1):
        call(newpt, "Add point", call(pt, "Get time from index", i) * scale, call(pt, "Get value at index", i))
    m2 = call(d2, "To Manipulation", 0.005, 75, 600)
    call([m2, newpt], "Replace pitch tier")
    d3 = call(m2, "Get resynthesis (overlap-add)")

    # loudness contour (10 ms frames, smoothed)
    x = target.values[0]
    y = np.pad(d3.values[0], (0, max(0, len(x) - d3.values.shape[1])))[:len(x)]
    hop = int(sr * 0.01)

    def env(s):
        e = np.sqrt(np.convolve(s ** 2, np.ones(hop) / hop, mode="same") + 1e-12)
        return np.convolve(e, np.ones(3 * hop) / (3 * hop), mode="same")

    y = y * np.clip(env(x) / env(y), 0.25, 4.0)

    # splice: 4 ms fade in (inside the stop closure), 12 ms fade out
    full = snd.values[0].copy()
    i0 = int(T0 * sr)
    f0, f1 = int(0.004 * sr), int(0.012 * sr)
    w = np.ones(len(y))
    w[:f0] = np.linspace(0, 1, f0)
    w[-f1:] = np.linspace(1, 0, f1)
    full[i0:i0 + len(y)] = full[i0:i0 + len(y)] * (1 - w) + y * w
    parselmouth.Sound(full, sr).save(a.out, "WAV")
    print(f"donor {dd:.3f}s -> {d3.duration:.3f}s into {td:.3f}s at {T0:.3f}")


if __name__ == "__main__":
    main()
