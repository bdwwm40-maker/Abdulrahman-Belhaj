#!/usr/bin/env python3
"""Build a 9:16 "Dark Cinematic Car Reel" from still photos.

Applies the saved preset: letterbox-squeeze intro, cuts on an 80 BPM grid
(0.75 s per beat), slow push-ins, macro detail crops, a dutch-angle shot,
2-frame flashes, dark matte grade that keeps reds, vignette, fade to black,
loudness at -14 LUFS.

Usage:
  python3 photos_to_reel.py shots.json output.mp4 [music.mp3]

shots.json is a list of shots, each:
  {"img": "path.jpg", "dur": 0.75, "cx": 0.5, "cy": 0.5, "zoom": 1.0,
   "push": 0.08, "rotate": 0, "intro": false}
  cx/cy  = centre of the crop (0..1 of the photo)
  zoom   = 1 crops the full photo height; 2 = 2x macro detail
  push   = how much the camera pushes in during the shot
Without a music file a synthetic dark 80 BPM beat is generated.
"""
import json, os, subprocess, sys, tempfile

W, H, FPS, BEAT = 1080, 1920, 30, 0.75


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def probe_size(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                   "-show_entries", "stream=width,height", "-of", "csv=p=0", path])
    w, h = out.decode().strip().split(",")
    return int(w), int(h)


def probe_dur(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", path])
    return float(out.decode().strip())


def render_shot(i, s, tmp):
    out = os.path.join(tmp, f"shot{i:02d}.mp4")
    frames = max(1, round(s["dur"] * FPS))
    iw, ih = probe_size(s["img"])
    is_video = s["img"].lower().endswith((".mp4", ".mov"))
    if is_video:
        # Video clip: take the middle part (or "start") and push in per input frame.
        start = s.get("start", max(0.0, (probe_dur(s["img"]) - s["dur"]) / 2))
        inputs = ["-ss", f"{start:.3f}", "-i", s["img"]]
        zp_z, zp_d = "in", 1
    else:
        inputs = ["-loop", "1", "-i", s["img"]]
        zp_z, zp_d = "on", frames
    if s.get("intro"):
        # Wide photo in a letterbox strip; bars squeeze in, hold, then open.
        strip = round(W * ih / iw / 2) * 2
        top = (H - strip) // 2
        squeeze = 120
        bar = (f"{top}+{squeeze}*if(lt(t,0.35),t/0.35,if(lt(t,1.1),1,"
               f"max(0,1-(t-1.1)/0.35)))")
        vf = (f"[0:v]scale={W*2}:-2,zoompan=z='1+0.06*{zp_z}/{frames}':x='iw/2-iw/zoom/2':"
              f"y='ih/2-ih/zoom/2':d={zp_d}:s={W}x{strip}:fps={FPS},"
              f"pad={W}:{H}:0:{top}:black[img];"
              f"color=black:s={W}x{H}:r={FPS}[b];"
              f"[img][b]overlay=y='-{H}+{bar}':eval=frame[t1];"
              f"color=black:s={W}x{H}:r={FPS}[b2];"
              f"[t1][b2]overlay=y='{H}-({bar})':eval=frame,format=yuv420p[v]")
    else:
        zoom = s.get("zoom", 1.0)
        rot = s.get("rotate", 0)
        extra = 1.25 if rot else 1.0  # hide rotated corners
        ch = ih / zoom / extra
        cw = ch * W / H
        if cw > iw:
            cw, ch = iw, iw * H / W
        x = min(max(s.get("cx", 0.5) * iw - cw / 2, 0), iw - cw)
        y = min(max(s.get("cy", 0.5) * ih - ch / 2, 0), ih - ch)
        push = s.get("push", 0.06)
        chain = (f"[0:v]crop={int(cw)}:{int(ch)}:{int(x)}:{int(y)},scale={W*2}:{H*2},"
                 f"zoompan=z='1+{push}*{zp_z}/{frames}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':"
                 f"d={zp_d}:s={W}x{H}:fps={FPS}")
        if rot:
            chain += f",scale={int(W*extra)//2*2}:{int(H*extra)//2*2},rotate={rot}*PI/180:ow={W}:oh={H}"
        vf = chain + ",format=yuv420p[v]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", vf, "-map", "[v]",
         "-frames:v", str(frames), "-r", str(FPS), "-c:v", "libx264", "-crf", "14",
         "-preset", "fast", out])
    return out


def synth_beat(dur, path):
    """Dark 80 BPM beat: sub pad, pitched kick from the first cut, offbeat hats."""
    b = BEAT
    expr = (
        f"0.18*sin(2*PI*41.2*t)*(0.6+0.4*sin(2*PI*t/{b*4}))"
        f"+0.08*sin(2*PI*82.4*t+sin(2*PI*0.5*t))"
        f"+gte(t,1.5)*0.9*sin(2*PI*(45*mod(t,{b})+3*(1-exp(-mod(t,{b})*30))))*exp(-mod(t,{b})*7)"
        f"+gte(t,1.5)*0.12*(random(0)*2-1)*exp(-mod(t+{b/2},{b})*70)"
        f"+lt(t,1.5)*0.25*(random(1)*2-1)*pow(t/1.5,3)*0.4"
    )
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}|{expr}':s=44100:d={dur}",
         "-af", f"lowpass=f=9000,acompressor=threshold=-18dB:ratio=6:attack=5:release=80,"
                f"afade=t=out:st={dur-1.5}:d=1.5", "-c:a", "pcm_s16le", path])


def main():
    shots = json.load(open(sys.argv[1]))
    base = os.path.dirname(os.path.abspath(sys.argv[1]))
    for s in shots:
        s["img"] = os.path.join(base, s["img"])
    out = sys.argv[2]
    music = sys.argv[3] if len(sys.argv) > 3 else None
    total = sum(s["dur"] for s in shots)
    with tempfile.TemporaryDirectory() as tmp:
        parts = [render_shot(i, s, tmp) for i, s in enumerate(shots)]
        lst = os.path.join(tmp, "list.txt")
        open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        audio = os.path.join(tmp, "beat.wav")
        if music:
            run(["ffmpeg", "-y", "-i", music, "-t", str(total), "-af",
                 f"afade=t=out:st={total-1.5}:d=1.5", audio])
        else:
            synth_beat(total, audio)
        # Flash frames on the two stutter beats (preset: ~8.4 s and ~9.2 s).
        t = 0.0
        flashes = []
        for s in shots:
            if s.get("flash"):
                flashes.append(t)
            t += s["dur"]
        flash = "".join(
            f",drawbox=x=0:y=0:w=iw:h=ih:color=white@0.55:t=fill:enable='between(t,{f:.3f},{f+2/FPS:.3f})'"
            for f in flashes)
        grade = (
            "eq=brightness=-0.07:contrast=1.25:gamma=0.82:saturation=1.1,"
            "huesaturation=saturation=-0.85:colors=y+g+c+b+m:strength=1,"
            "huesaturation=saturation=0.2:colors=r,"
            "colorbalance=bs=0.06:bm=0.02:rh=-0.02,"
            "curves=master='0/0 0.12/0.04 0.5/0.42 1/0.95',"
            "vignette=PI/4.5"
            f"{flash},"
            f"fade=t=in:st=0:d=0.25,fade=t=out:st={total-1.0:.2f}:d=1.0,format=yuv420p"
        )
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", audio,
             "-vf", grade, "-af", "loudnorm=I=-14:TP=-1:LRA=4", "-r", str(FPS),
             "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest",
             "-movflags", "+faststart", out])
    print(f"done: {out} ({total:.2f}s)")


if __name__ == "__main__":
    main()
