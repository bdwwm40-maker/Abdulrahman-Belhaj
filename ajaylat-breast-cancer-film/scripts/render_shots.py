import os, subprocess, sys, json
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
from plan import SHOTS, SRC

W, H, FPS = 1080, 1920, 30
OUT = "shots"
os.makedirs(OUT, exist_ok=True)

# Unified grade: clean, warm, human. Gentle filmic curve, tamed saturation (keeps pinks soft),
# warm highlights / slightly cool shadows, natural skin.
GRADE = ("eq=contrast=1.06:saturation=0.88:gamma=1.0,"
         "colorbalance=rs=-0.02:gs=0.0:bs=0.025:rm=0.01:bm=-0.01:rh=0.03:gh=0.012:bh=-0.02,"
         "curves=master='0/0.035 0.25/0.235 0.5/0.51 0.75/0.79 1/0.965'")


def card_bg(path):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.zeros((H, W, 3), np.float32)
    top = np.array([16, 12, 15], np.float32); bot = np.array([8, 6, 8], np.float32)
    t = (y / H)[..., None]
    base[:] = top * (1 - t) + bot * t
    # soft rose glow, very subtle
    d = np.sqrt(((x - W * 0.5) / (W * 0.75)) ** 2 + ((y - H * 0.46) / (H * 0.38)) ** 2)
    glow = np.exp(-d ** 2 * 2.2)[..., None]
    base += glow * np.array([46, 22, 32], np.float32)
    Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).save(path)


def render(i, s):
    out = f"{OUT}/{i:02d}.mp4"
    n = int(round(s["dur"] * FPS))
    z0, z1 = s["z"]; D = s["dur"]
    zexpr = f"({z0}+({z1}-{z0})*(t/{D})*(t/{D})*(3-2*t/{D}))"  # eased zoom
    if s["src"] is None:
        if s.get("kind") == "black":
            cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}",
                   "-frames:v", str(n)]
        else:
            if not os.path.exists("card_bg.png"):
                card_bg("card_bg.png")
            vf = (f"scale=w='trunc({W}*{zexpr}/2)*2':h=-2:eval=frame:flags=bicubic,"
                  f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2,format=yuv420p")
            cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", "card_bg.png",
                   "-vf", vf, "-frames:v", str(n)]
    else:
        sp = s["speed"]
        src = SRC[s["src"]]
        need = D * sp + 0.6
        f = ["setpts=PTS-STARTPTS"]
        if s.get("crop"):
            cw, ch, cx, cy = s["crop"]; f.append(f"crop={cw}:{ch}:{cx}:{cy}")
        f.append("hqdn3d=2:1.5:4:3")
        if s["src"] == "0036":
            f.append(f"setpts=PTS/{sp},fps={FPS}")
        elif sp < 0.97:
            f.append(f"minterpolate=fps={round(FPS/sp)}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
                     f"setpts=PTS/{sp},fps={FPS}")
        elif sp > 1.03:
            f.append(f"setpts=PTS/{sp},fps={FPS}")
        else:
            f.append(f"fps={FPS}")
        if s.get("bright"):
            f.append(f"eq=brightness={s['bright']}")
        f.append(GRADE)
        # base fill size, then eased push-in (per-frame resample = smooth sub-pixel motion)
        f.append(f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}")
        f.append(f"scale=w='trunc({W}*{zexpr}/2)*2':h=-2:eval=frame:flags=lanczos")
        py = s.get("py", 0.0)
        f.append(f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2*(1-{py}*2)")
        f.append("unsharp=5:5:0.45:5:5:0,format=yuv420p")
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(s["ss"]), "-t", f"{need:.3f}", "-i", src,
               "-vf", ",".join(f), "-frames:v", str(n)]
    cmd += ["-an", "-c:v", "libx264", "-preset", "medium", "-crf", "13", "-r", str(FPS), out]
    subprocess.run(cmd, check=True)
    got = int(subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                       "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", out]).strip())
    return i, s["name"], n, got


only = set(int(a) for a in sys.argv[1:])
jobs = [(i, s) for i, s in enumerate(SHOTS) if not only or i in only]
with ThreadPoolExecutor(4) as ex:
    for i, name, n, got in ex.map(lambda a: render(*a), jobs):
        print(i, name, n, got, "" if n == got else "  <-- FRAME MISMATCH", flush=True)
