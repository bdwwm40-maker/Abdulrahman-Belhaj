#!/usr/bin/env python3
"""Build a "circle match cut on ticks" edit from your own clips.

Style source: montage/preset_circle_match_cut.json
Usage:   python3 make_montage.py project.json
Needs:   ffmpeg on PATH.

project.json example: see montage/project_example.json
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("+", " ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(project_path):
    preset = load(os.path.join(HERE, "preset_circle_match_cut.json"))
    proj = load(project_path)
    base = os.path.dirname(os.path.abspath(project_path))
    p = lambda f: f if os.path.isabs(f) else os.path.join(base, f)

    W, H = proj.get("resolution", [1920, 1080])
    fps = proj.get("fps", 23.976)
    beat = 60.0 / proj.get("bpm", 120)
    intro_len = proj.get("intro_duration", preset["editing_rules"]["intro"]["duration_s"])
    reveal = proj.get("reveal_duration", preset["editing_rules"]["intro"]["transition_duration_s"])
    reveal_kind = proj.get("reveal_transition", "wipeleft")
    fade_end = preset["editing_rules"]["outro"]["fade_s"]
    grade = proj.get("grade", preset["color_grade"]["ffmpeg_filter"])
    out = p(proj.get("output", "montage_out.mp4"))

    shots = [dict(proj["intro"], role="intro", dur=intro_len)]
    for s in proj["match_shots"]:
        shots.append(dict(s, role="match", dur=s.get("beats", 1) * beat))
    if proj.get("outro"):
        shots.append(dict(proj["outro"], role="outro", dur=proj["outro"].get("beats", 1) * beat))

    tmp = tempfile.mkdtemp(prefix="montage_")
    segs = []
    for i, s in enumerate(shots):
        d = s["dur"] + (reveal if s["role"] == "intro" else 0)
        zoom = s.get("zoom", 1.0)  # scale up so the circle matches the previous shot
        vf = (f"scale={int(W*zoom)}:{int(H*zoom)}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={fps},{grade},setsar=1,format=yuv420p")
        if s.get("eye_detail"):
            vf += ",unsharp=7:7:1.2,eq=contrast=1.08"
        seg = os.path.join(tmp, f"s{i:02d}.mp4")
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(s.get("in", 0)), "-i", p(s["file"]),
             "-t", f"{d:.4f}", "-vf", vf, "-an", "-c:v", "libx264", "-crf", "16",
             "-preset", "fast", seg])
        segs.append(seg)

    # ---- video: intro --(mask reveal)--> first match, then hard cuts on every tick
    n = len(segs)
    inputs = sum((["-i", s] for s in segs), [])
    fc = [f"[0:v][1:v]xfade=transition={reveal_kind}:duration={reveal}:offset={intro_len:.4f}[x1]"]
    chain = "[x1]" + "".join(f"[{k}:v]" for k in range(2, n))
    fc.append(f"{chain}concat=n={n-1}:v=1:a=0[cat]")
    total = intro_len + sum(s["dur"] for s in shots[1:])
    fc.append(f"[cat]fade=t=out:st={total-fade_end:.4f}:d={fade_end}[v]")
    if proj.get("vertical"):  # 9:16 export with the 16:9 edit centred
        fc[-1] = fc[-1].replace("[v]", "[h]")
        fc.append("[h]scale=1080:-2,pad=1080:1920:0:(oh-ih)/2:black[v]")

    # ---- audio: riser + ticks on each cut + user SFX/music
    cut_times = [intro_len]
    t = intro_len
    for s in shots[1:]:
        t += s["dur"]
        cut_times.append(t)
    cut_times = [c for c in cut_times if c < total - 0.05]

    a_in, a_fc, labels = [], [], []
    idx = n

    def add(src_args, filt, label):
        nonlocal idx
        a_in.extend(src_args)
        a_fc.append(f"[{idx}:a]{filt}[{label}]")
        labels.append(f"[{label}]")
        idx += 1

    if proj.get("synth_riser", True):
        r = f"0.25*sin(2*PI*(80*t+90*t*t/{total}))*pow(t/{total},2)+0.05*(random(0)-0.5)*t/{total}"
        add(["-f", "lavfi", "-t", f"{total}", "-i", f"aevalsrc='{r}':s=48000:c=stereo"],
            f"afade=t=out:st={total-0.15}:d=0.15", "riser")
    if proj.get("synth_ticks", True):
        for k, c in enumerate(cut_times):
            add(["-f", "lavfi", "-t", "0.09", "-i",
                 "aevalsrc='0.7*sin(2*PI*2800*t)*exp(-70*t)+0.4*sin(2*PI*1200*t)*exp(-90*t)':s=48000:c=stereo"],
                f"adelay={int(c*1000)}|{int(c*1000)}", f"tk{k}")
    start = 0.0
    for k, s in enumerate(shots):
        if s.get("sfx"):
            ms = int((start + s.get("sfx_offset", 0)) * 1000)
            add(["-i", p(s["sfx"])], f"aresample=48000,volume={s.get('sfx_gain', 1.0)},adelay={ms}|{ms}", f"sx{k}")
        start += s["dur"] if s["role"] != "intro" else intro_len
    if proj.get("music"):
        add(["-i", p(proj["music"])], f"aresample=48000,volume={proj.get('music_gain', 0.6)}", "mus")

    if labels:
        a_fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,"
                    f"atrim=0:{total},loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    cmd = ["ffmpeg", "-v", "error", "-y"] + inputs + a_in + [
        "-filter_complex", ";".join(fc + a_fc), "-map", "[v]"]
    if labels:
        cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-movflags", "+faststart", out]
    run(cmd)
    print(f"\nDone: {out}  ({total:.2f}s, cuts at {[round(c, 2) for c in cut_times]})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
