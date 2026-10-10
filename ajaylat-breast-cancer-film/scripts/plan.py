# Edit decision list for the Al-Ajaylat breast-cancer screening awareness film.
U = "/root/.claude/uploads/43d4f1b0-5bb8-5d07-a10e-f639d5d13fb1/"
SRC = {
    "0036": U + "411965b3-VID-20261010-WA0036.mp4",
    "0039": U + "1fb71bf5-VID-20261010-WA0039.mp4",
    "0140": U + "fa2882b2-VID-20261010-WA0140.mp4",
    "0148": U + "c4237d2b-VID-20261010-WA0148.mp4",
    "0161": U + "de7c41ac-VID-20261010-WA0161.mp4",
    "0163": U + "23d8d05f-VID-20261010-WA0163.mp4",
    "0165": U + "16efa899-VID-20261010-WA0165.mp4",
    "0173": U + "ad08c7c2-VID-20261010-WA0173.mp4",
    "0181": U + "3e8d1158-VID-20261010-WA0181.mp4",
    "0186": U + "af02ef63-VID-20261010-WA0186.mp4",
    "0188": U + "c5bcad32-VID-20261010-WA0188.mp4",
    "0201": U + "0199170d-VID-20261010-WA0201.mp4",
}

def S(name, src, ss, dur, speed=1.0, z=(1.0, 1.06), tr=("dissolve", 0.8), py=0.0,
      bright=0.0, text=(), vo=(), audio=None, crop=None):
    return dict(name=name, src=src, ss=ss, dur=dur, speed=speed, z=z, tr=tr, py=py,
                bright=bright, text=list(text), vo=list(vo), audio=audio, crop=crop)

def C(name, dur, kind="card", tr=("fade", 0.6), text=(), vo=()):
    return dict(name=name, src=None, kind=kind, dur=dur, tr=tr, text=list(text), vo=list(vo),
                z=(1.0, 1.05), audio=False)

# text tuple: (offset, duration, style, string)
CUT = ("fade", 0.08)
SHOTS = [
    C("black", 2.6, kind="black", tr=None),
    # --- Opening
    S("lobby", "0140", 0.3, 5.6, 0.75, z=(1.0, 1.09), tr=("fade", 1.4),
      text=[(0.9, 4.0, "Hook", "لأن صحتها… تهمّنا.")]),
    S("arrive", "0036", 0.0, 5.4, 0.25, z=(1.06, 1.0), tr=("dissolve", 1.0),
      text=[(0.7, 4.3, "Hook", "ولأن الوعي… قد يصنع الفرق.")]),
    # --- Chapter 1: the human message
    S("hearts", "0201", 23.0, 6.6, 0.55, z=(1.14, 1.22), py=0.05, tr=("fadeblack", 1.3),
      text=[(1.0, 4.4, "Hook", "كل امرأة… لها حكاية.")], vo=[(0.7, "v01")]),
    S("lineup", "0201", 13.0, 6.0, 0.6, z=(1.16, 1.08), tr=("dissolve", 0.9),
      text=[(1.6, 3.8, "Hook", "ولها أحبّة ينتظرونها.")], vo=[(0.3, "v02")]),
    S("banner_woman", "0186", 0.6, 5.2, 0.6, z=(1.0, 1.08), tr=("dissolve", 0.9),
      text=[(1.4, 3.6, "Hook2", "ولها مستقبل يستحق\\Nأن تحافظ عليه.")]),
    # --- Chapter 2: awareness
    S("banner_women", "0186", 2.9, 4.6, 0.7, z=(1.04, 1.1), tr=("dissolve", 0.9),
      text=[(0.7, 3.4, "Sans", "الوعي يبدأ بالسؤال.")], vo=[(0.3, "v03")]),
    S("explain", "0165", 0.8, 4.6, 0.8, z=(1.08, 1.14), tr=("dissolve", 0.8),
      text=[(0.7, 3.4, "Sans", "والوقاية تبدأ بالاهتمام.")], vo=[(1.7, "v04")]),
    S("ribbons", "0148", 2.2, 4.4, 0.55, z=(1.0, 1.1), tr=("dissolve", 0.8),
      text=[(0.6, 3.4, "Sans", "والكشف المبكر خطوة مهمّة.")], vo=[(0.9, "v05")]),
    S("door", "0140", 9.2, 5.2, 1.0, z=(1.0, 1.05), tr=("dissolve", 0.9), audio=True),
    # --- Chapter 3: the campaign (match cuts on hands)
    S("hands_write", "0148", 0.0, 2.5, 1.0, z=(1.05, 1.1), tr=("fade", 0.35), audio=True,
      vo=[(0.4, "v06")]),
    S("pass_paper", "0181", 1.2, 2.4, 1.0, z=(1.06, 1.1), tr=("fade", 0.3), audio=True),
    S("luac_write", "0173", 0.2, 2.5, 1.0, z=(1.05, 1.1), tr=("fade", 0.3), audio=True),
    S("pass2", "0181", 9.6, 2.4, 1.0, z=(1.08, 1.12), tr=("fade", 0.3), audio=True),
    S("review", "0163", 4.6, 2.6, 1.0, z=(1.05, 1.1), tr=("fade", 0.3), audio=True),
    S("explain2", "0165", 3.0, 2.4, 1.0, z=(1.1, 1.14), tr=("fade", 0.3), audio=True),
    S("ultra", "0161", 0.0, 3.0, 1.0, z=(1.0, 1.06), tr=("fade", 0.3), audio=True),
    S("ultra_dark", "0161", 3.95, 2.0, 1.0, z=(1.06, 1.1), tr=("fade", 0.5), bright=0.03),
    # --- Chapter 4: partners
    S("team", "0201", 0.5, 4.2, 0.8, z=(1.04, 1.1), tr=("fadeblack", 1.0),
      text=[(0.7, 3.2, "Hook", "بمشاركة")], vo=[(0.5, "v07")]),
    S("vol_banner", "0039", 1.4, 3.8, 0.9, z=(1.0, 1.05), tr=("dissolve", 0.7), audio=True,
      text=[(0.4, 3.1, "Org", "الوكالة الوطنية للجهود التطوعية للشباب\\N{\\fs50}مكتب العجيلات")]),
    S("luac_vest", "0173", 4.3, 3.8, 0.9, z=(1.04, 1.1), tr=("dissolve", 0.7),
      text=[(0.4, 3.1, "Org", "الاتحاد الليبي لمكافحة السرطان")]),
    S("women_banner", "0188", 0.0, 3.8, 0.95, z=(1.0, 1.06), tr=("dissolve", 0.7),
      text=[(0.4, 3.1, "Org", "مكتب دعم المرأة ببلدية العجيلات")], vo=[(1.0, "v08")]),
    S("banners_top", "0186", 2.2, 4.8, 0.75, z=(1.0, 1.07), tr=("dissolve", 0.8),
      crop=(380, 676, 60, 0),
      text=[(0.6, 3.9, "Hook2", "معاً… من أجل وعيٍ أكبر…\\Nوصحةٍ أفضل.")]),
    # --- Chapter 5: volunteering
    S("scrubs", "0201", 30.5, 4.6, 0.85, z=(1.08, 1.14), tr=("fadeblack", 1.0),
      text=[(0.8, 3.5, "Hook", "بالتطوّع… نصنع أثراً.")], vo=[(1.2, "v09")]),
    S("scrubs2", "0201", 36.5, 4.2, 1.0, z=(1.1, 1.16), tr=("dissolve", 0.6), audio=True),
    S("talk", "0201", 4.0, 4.2, 0.85, z=(1.12, 1.18), tr=("dissolve", 0.6)),
    # --- Chapter 6: the human side (slow)
    S("handing", "0181", 13.0, 5.2, 0.65, z=(1.06, 1.12), tr=("dissolve", 1.0)),
    S("explain3", "0165", 5.9, 4.6, 0.7, z=(1.1, 1.16), tr=("dissolve", 0.9)),
    S("heart_slow", "0201", 24.8, 5.8, 0.5, z=(1.2, 1.28), py=0.05, tr=("dissolve", 0.9)),
    # --- Climax montage
    S("m_woman", "0201", 26.2, 1.0, 1.0, z=(1.3, 1.34), py=0.05, tr=("fade", 0.25)),
    S("m_doctor", "0165", 2.0, 0.9, 1.0, z=(1.15, 1.2), tr=CUT),
    S("m_vol", "0201", 33.0, 0.9, 1.0, z=(1.15, 1.2), tr=CUT),
    S("m_exam", "0161", 1.0, 0.9, 1.0, z=(1.1, 1.15), tr=CUT),
    S("m_smile", "0201", 22.0, 0.9, 1.0, z=(1.25, 1.3), py=0.05, tr=CUT),
    S("m_team", "0201", 7.0, 0.9, 1.0, z=(1.1, 1.15), tr=CUT),
    S("m_logo", "0039", 3.0, 0.9, 1.0, z=(1.0, 1.05), tr=CUT),
    S("m_seated", "0186", 4.5, 0.9, 1.0, z=(1.05, 1.1), tr=CUT),
    S("m_group", "0201", 15.0, 1.5, 1.0, z=(1.0, 1.06), tr=CUT),
    # --- The call (music stops)
    C("call", 19.0, tr=("fadeblack", 0.5),
      text=[(3.4, 4.2, "Card", "لا تنتظري الأعراض."),
            (8.1, 2.3, "Card", "كوني واعية."),
            (10.6, 2.3, "Card", "كوني مطمئنّة."),
            (13.2, 5.2, "Card2", "واجعلي الفحص خطوة\\Nمن أجل صحتك.")],
      vo=[(0.9, "v10"), (3.3, "v11"), (8.0, "v12")]),
    # --- Ending
    S("final_group", "0201", 12.5, 8.6, 0.6, z=(1.0, 1.1), tr=("fade", 1.4),
      text=[(0.9, 3.2, "Hook", "من أجل كل امرأة…"),
            (4.6, 3.3, "Hook", "من أجل كل أسرة…")]),
    S("final_group2", "0201", 19.0, 7.8, 0.6, z=(1.06, 1.14), tr=("dissolve", 1.1),
      text=[(0.6, 3.1, "Hook", "من أجل مجتمع أكثر وعياً…"),
            (4.1, 3.2, "Hook", "نلتقي على هدف واحد.")], vo=[(0.2, "v13")]),
    C("end", 23.0, tr=("fadeblack", 1.2),
      text=[(0.6, 5.6, "Small", "بمشاركة"),
            (1.1, 5.1, "OrgEnd", "الوكالة الوطنية للجهود التطوعية للشباب\\N{\\fs54}مكتب العجيلات\\N\\N"
                                  "الاتحاد الليبي لمكافحة السرطان\\N\\N"
                                  "مكتب دعم المرأة ببلدية العجيلات"),
            (7.2, 4.7, "Title", "حملة الكشف المجاني\\Nعن سرطان الثدي"),
            (7.9, 4.0, "Year", "العجيلات 2026"),
            (12.5, 3.6, "Card", "وعيكِ… قوّة."),
            (16.5, 4.9, "Card2", "الكشف خطوة…\\Nوالأمل حياة.")],
      vo=[(12.5, "v14"), (16.6, "v15")]),
]
