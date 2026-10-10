import json, subprocess, os
from plan import SHOTS

FPS = 30
# --- timeline (frame-quantised so xfade offsets are exact)
starts, t = [], 0.0
for i, s in enumerate(SHOTS):
    if i > 0:
        t = t - s["tr"][1]
    starts.append(round(t * FPS) / FPS)
    t = starts[-1] + round(s["dur"] * FPS) / FPS
TOTAL = t

# --- processed VO lengths
os.makedirs("vo_p", exist_ok=True)
VOF = ("silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.05,areverse,"
       "silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.12,areverse,"
       "highpass=f=85,equalizer=f=220:t=q:w=1.2:g=-1.5,equalizer=f=3200:t=q:w=1.2:g=2,"
       "equalizer=f=9000:t=h:w=1:g=1,acompressor=threshold=-22dB:ratio=3:attack=8:release=160:makeup=2,"
       "aresample=48000,aformat=channel_layouts=mono")
vo_len = {}
for s in SHOTS:
    for off, vid in s["vo"]:
        out = f"vo_p/{vid}.wav"
        if not os.path.exists(out):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"vo/{vid}.mp3", "-af", VOF, out], check=True)
        vo_len[vid] = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                     "-of", "csv=p=0", out]))

vo_events, text_events = [], []
for i, s in enumerate(SHOTS):
    for off, vid in s["vo"]:
        vo_events.append((starts[i] + off, vid, vo_len[vid]))
    for off, d, st, txt in s["text"]:
        text_events.append((starts[i] + off, d, st, txt))
vo_events.sort()
prev_end = 0
for st, vid, ln in vo_events:
    flag = "  <-- OVERLAP" if st < prev_end + 0.25 else ""
    print(f"VO {vid} {st:7.2f} -> {st+ln:7.2f}{flag}")
    prev_end = st + ln

idx = {s["name"]: i for i, s in enumerate(SHOTS)}
cues = dict(
    first=starts[idx["lobby"]],
    ch1=starts[idx["hearts"]],
    ch2=starts[idx["banner_women"]],
    ch3=starts[idx["hands_write"]],
    ch4=starts[idx["team"]],
    ch5=starts[idx["scrubs"]],
    ch6=starts[idx["handing"]],
    climax=starts[idx["m_woman"]],
    stop=starts[idx["call"]],
    ending=starts[idx["final_group"]],
    endcard=starts[idx["end"]],
    title=starts[idx["end"]] + 7.2,
    total=TOTAL,
)
whoosh = [starts[idx[n]] for n in ("hands_write", "team", "scrubs", "final_group")]
prod = []
for i, s in enumerate(SHOTS):
    if s.get("audio"):
        prod.append(dict(src=s["src"], ss=s["ss"], start=starts[i], dur=s["dur"]))
json.dump(dict(starts=starts, total=TOTAL, cues=cues, vo=vo_events, whoosh=whoosh, prod=prod),
          open("timeline.json", "w"), indent=1, ensure_ascii=False)
for k, v in cues.items():
    print(f"{k:8s} {v:7.2f}")


# --- ASS subtitles (libass does Arabic shaping + bidi)
def ts(x):
    h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
    return f"{h}:{m:02d}:{s:05.2f}"

# colours are &HAABBGGRR
STY = {
    #        font            size bold  y     colour      outline/shadow
    "Hook":  ("Amiri",       215, 1, 1440, "&H00F4F2F6", 0, 3),
    "Hook2": ("Amiri",       185, 1, 1400, "&H00F4F2F6", 0, 3),
    "Sans":  ("Tajawal",      92, 1, 1440, "&H00F6F4F6", 0, 3),
    "Org":   ("Tajawal",      62, 1, 1470, "&H00FFFFFF", 0, 3),
    "Card":  ("Amiri",       250, 1,  930, "&H00F4F2F6", 0, 0),
    "Card2": ("Amiri",       210, 1,  930, "&H00F4F2F6", 0, 0),
    "Small": ("Tajawal",      66, 0,  690, "&H00C8B6E8", 0, 0),
    "OrgEnd":("Tajawal",      64, 1,  960, "&H00F2EEF2", 0, 0),
    "Title": ("Tajawal",     112, 1,  890, "&H00FFFFFF", 0, 0),
    "Year":  ("Amiri",       185, 1, 1170, "&H00C8B6E8", 0, 0),
}
lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 2",
         "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
         "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
         "Alignment, MarginL, MarginR, MarginV, Encoding"]
for n, (f, sz, b, y, col, o, sh) in STY.items():
    lines.append(f"Style: {n},{f},{sz},{col},&H000000FF,&H00000000,&H96000000,{-1 if b else 0},0,0,0,"
                 f"100,100,0,0,1,{o},{sh},5,60,60,0,-1")
lines += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
for st, d, sty, txt in sorted(text_events):
    txt = "\u200f" + txt.replace("\\N", "\u200f\\N\u200f") + "\u200f"
    y = STY[sty][3]
    fin, fout = (900, 900) if sty in ("Card", "Card2", "Title", "OrgEnd") else (700, 750)
    eff = (f"{{\\fad({fin},{fout})\\blur7\\t(0,{fin + 200},\\blur0.6)"
           f"\\move(540,{y + 16},540,{y},0,{int(d * 1000)})}}")
    if sty in ("Hook", "Hook2", "Sans", "Org"):
        eff = eff[:-1] + "\\4c&H000000&\\4a&H70&\\shad0\\bord0}"
        # soft glow shadow layer for legibility over footage
        lines.append(f"Dialogue: 0,{ts(st)},{ts(st + d)},{sty},,0,0,0,,"
                     f"{{\\fad({fin},{fout})\\blur16\\bord9\\3c&H000000&\\3a&H50&\\1a&HFF&"
                     f"\\move(540,{y + 16},540,{y},0,{int(d * 1000)})}}{txt}")
    lines.append(f"Dialogue: 1,{ts(st)},{ts(st + d)},{sty},,0,0,0,,{eff}{txt}")
    if sty in ("Title", "Card"):
        # thin rose accent line under key titles
        ly = y + (200 if sty == "Title" else 150)
        lines.append(f"Dialogue: 1,{ts(st + 0.35)},{ts(st + d)},{sty},,0,0,0,,"
                     f"{{\\an5\\pos(540,{ly})\\fad(900,750)\\1c&HB79BE0&\\bord0\\shad0\\blur0.8"
                     f"\\fscx0\\t(0,1400,\\fscx100)\\p1}}m -90 0 l 90 0 l 90 3 l -90 3{{\\p0}}")
open("titles.ass", "w").write("\n".join(lines) + "\n")

# --- video master: xfade chain
inputs, fc = [], []
for i in range(len(SHOTS)):
    inputs += ["-i", f"shots/{i:02d}.mp4"]
prev = "[0:v]"
acc = round(SHOTS[0]["dur"] * FPS) / FPS
for i in range(1, len(SHOTS)):
    tr, d = SHOTS[i]["tr"]
    off = starts[i]
    lab = f"[x{i}]"
    fc.append(f"{prev}[{i}:v]xfade=transition={tr}:duration={d}:offset={off:.4f}{lab}")
    prev = lab
fc.append(f"{prev}settb=AVTB,fps={FPS}[v]")
open("xfade.txt", "w").write(";\n".join(fc))
print("TOTAL", TOTAL)
if not os.environ.get("NOVIDEO"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex_script", "xfade.txt", "-map", "[v]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", "master_v.mp4"],
                   check=True)
