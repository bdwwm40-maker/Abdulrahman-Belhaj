# Film timeline: all times in seconds (film time). Windows are (cx, cy, h) in source px.
FPS = 25
OUT_W, OUT_H = 1920, 804          # 2.39:1 picture area
FRAME_H = 1080
BAR = (FRAME_H - OUT_H) // 2

# Music grid (87 bpm, 4/4) anchored on the banner reveal
T0 = 43.9
BARLEN = 4 * 60 / 87.0

def bar(n):
    return T0 + n * BARLEN

# clip: dict(src, t (film start), dur, sin (source in), speed, w0, w1, look, tin (dissolve-in), mode)
CLIPS = []

def C(src, t, dur, sin, speed, w0, w1=None, look=None, tin=0.0, mode='blend', **kw):
    d = dict(src=src, t=t, dur=dur, sin=sin, speed=speed, w0=w0, w1=w1 or w0,
             look=look or ('hist' if src == 'v1' else 'now'), tin=tin, mode=mode)
    d.update(kw)
    CLIPS.append(d)

FULL = (640, 360, 720)

# ---------------- ACT I / II : history ----------------
C('v1', 2.5, 8.0, 5.2, 0.85, FULL, (645, 335, 590), tin=1.8, fade_from_black=True)          # Mabrouka
C('v1', 9.3, 7.6, 14.6, 0.85, FULL, (615, 355, 600), tin=1.2)                              # Zaima
C('v1', 15.7, 8.0, 23.3, 0.85, (640, 360, 700), (635, 320, 590), tin=1.2)                   # Hamida
C('v1', 22.5, 8.5, 32.0, 0.85, FULL, (600, 300, 470), tin=1.2)                             # Khadija
C('v1', 30.0, 6.4, 41.0, 0.80, (640, 360, 700), (640, 360, 630), tin=1.0)                   # collage

# ---------------- bridge: memory -> present ----------------
C('v2', 34.8, 5.2, 114.9, 0.48, (715, 200, 230), (650, 262, 520), look='bridge', tin=1.6,
  mode='mci', leak=True)                                                                    # projector
C('v2', 39.0, 5.4, 107.0, 0.80, (600, 262, 500), (690, 262, 520), tin=1.0)                  # dark hall
C('v2', bar(0) - 0.5, 4.6, 0.2, 0.72, (620, 240, 470), (620, 292, 360), tin=0.9, bloom=True) # banner

# ---------------- ACT III : Al-Ajaylat 2026 ----------------
t = bar(0) - 0.5 + 4.6 - 0.6
C('v2', t, 3.3, 3.75, 1.0, (630, 250, 470), (650, 240, 430), tin=0.6); t += 3.3 - 0.6        # speaker
C('v2', t, 4.6, 7.3, 0.9, (600, 250, 500), (690, 252, 500), tin=0.6); t += 4.6 - 0.5         # women audience
NAJLA_T = t
C('v2', t, 3.9, 60.15, 1.0, (640, 262, 470), (640, 258, 440), tin=0.5); t += 3.9 - 0.5       # Najla on camera
C('v2', t, 3.4, 118.6, 1.0, (700, 282, 500), (725, 270, 455), tin=0.5); t += 3.4 - 0.5       # certificate 1
ZAHRA_T = t
C('v2', t, 4.0, 100.3, 1.0, (650, 262, 470), (650, 255, 430), tin=0.5); t += 4.0 - 0.5       # Zahra Rajal
C('v2', t, 4.4, 122.4, 1.0, (660, 272, 450), (660, 258, 380), tin=0.5); t += 4.4 - 0.5       # honoree smiling
C('v2', t, bar(10) - t + 0.3, 127.3, 0.9, (640, 265, 530), (640, 262, 495), tin=0.5)          # group line-up

# ---------------- climax montage (on the bar grid) ----------------
t = bar(10)
for (src, sin, dur, w0, w1) in [
    ('v1', 9.0, 1.6, (640, 225, 340), (640, 222, 310)),      # Mabrouka
    ('v2', 9.0, 1.4, (640, 255, 430), (660, 255, 420)),      # audience
    ('v1', 18.0, 1.4, (590, 372, 400), (590, 370, 370)),     # Zaima
    ('v2', 119.8, 1.4, (820, 262, 380), (820, 258, 350)),    # honoree receives
    ('v1', 27.0, 1.4, (625, 205, 380), (625, 200, 350)),     # Hamida
    ('v2', 105.2, 1.4, (650, 250, 420), (650, 248, 390)),    # Zahra smiles
]:
    C(src, t, dur, sin, 1.0, w0, w1, tin=0.25)
    t += dur
C('v1', t, bar(14) - t, 36.0, 0.9, (585, 255, 380), (582, 248, 300), tin=0.25)                # Khadija -> eyes
MATCH_T = bar(14)
C('v2', MATCH_T, 3.0, 123.6, 1.0, (660, 255, 300), (660, 262, 390), tin=0.0, flash=True)      # MATCH CUT honoree
t = MATCH_T + 3.0
C('v2', t, 2.1, 128.6, 1.0, (640, 262, 520), (640, 262, 490), tin=0.3); t += 2.1
C('v2', t, 2.0, 137.0, 1.0, (700, 270, 500), (720, 265, 455), tin=0.3); t += 2.0
C('v2', t, 2.0, 9.6, 1.0, (620, 250, 500), (700, 250, 500), tin=0.3); t += 2.0

# ---------------- resolution ----------------
END_T = t - 0.9
C('v2', END_T, 13.5, 139.0, 0.30, (690, 255, 470), (640, 230, 330), tin=0.9, mode='mci', send=141.1,
  fade_to_black=(END_T + 12.0, END_T + 13.5))                                                 # last honoree, slow
TITLE_T = END_T + 14.2
FILM_END = TITLE_T + 12.5

# ---------------- sound bites (src audio of v2) ----------------
BITES = [
    # (film t, src in, src out, gain dB)
    (40.6, 33.95, 38.95, -1.0),                 # Najla V.O. "...in the service of spreading knowledge"
    (NAJLA_T + 0.05, 60.3, 63.75, 0.0),          # Najla sync "to remember and thank them"
    (ZAHRA_T + 0.25, 100.35, 105.5, 0.0),        # Zahra "a great joy... that they remember us"
    (END_T + 1.2, 78.75, 80.55, -0.5),          # Zahra "thank you, children, you remember us"
]

# ---------------- titles ----------------
TEXTS = dict(
    t1=(11.2, 15.6), t2=(17.6, 22.0), t3=(31.4, 36.0),
    najla=(NAJLA_T + 0.4, NAJLA_T + 3.3),
    zahra=(ZAHRA_T + 0.4, ZAHRA_T + 3.7),
    e1=(END_T + 3.4, END_T + 7.8),
    e2=(END_T + 8.0, END_T + 12.6),
    e3=(TITLE_T, TITLE_T + 5.6),
    seal=(TITLE_T + 6.2, FILM_END - 0.6),
)
