#!/usr/bin/env python3
"""Generate the volunteer cartoon characters as SVG (+ HTML stages for rendering).

Every character wears clothing that carries the agency logo
(logo/logo-original.png).  The SVGs are built from named groups so that
src/anim.js can pose them (arms, head, eyes, mouth) frame by frame.
"""
import base64
import io
import pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOGO_SRC = ROOT / "logo" / "logo-original.png"
LOGO_OUT = ROOT / "logo" / "logo-transparent.png"
SVG_DIR = ROOT / "characters" / "svg"
STAGE_DIR = ROOT / "build" / "stage"

OUT = "#2b2233"  # outline colour
SW = 5  # outline width

# Arm geometry (local coordinates, shoulder at 0,0, arm hangs along +y)
UPPER = 112  # shoulder -> elbow
FORE = 92  # elbow -> wrist
HAND = 110  # elbow -> hand centre
SHOULDER = {"L": (220, 442), "R": (380, 442)}


# --------------------------------------------------------------------------
# Logo
# --------------------------------------------------------------------------
def make_logo():
    """Crop the logo and turn its white background transparent."""
    im = Image.open(LOGO_SRC).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    mn = a.min(axis=2)
    ys, xs = np.where(mn < 235)
    pad = 12
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, a.shape[1])
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, a.shape[0])
    a = a[y0:y1, x0:x1]
    mn = a.min(axis=2)
    # colour-to-alpha against white, solid colours stay fully opaque
    alpha = np.clip((250.0 - mn) / 45.0, 0.0, 1.0)
    safe = np.maximum(alpha, 1e-3)[..., None]
    rgb = np.clip(255.0 - (255.0 - a) / safe, 0, 255)
    out = np.dstack([rgb, alpha * 255.0]).astype(np.uint8)
    logo = Image.fromarray(out, "RGBA")
    logo.save(LOGO_OUT, optimize=True)
    small = logo.resize((360, round(360 * logo.height / logo.width)), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, "PNG", optimize=True)
    return logo.width / logo.height, "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


LOGO_RATIO, LOGO_URI = make_logo()


def logo_img(cx, cy, h):
    w = h * LOGO_RATIO
    return (f'<image href="{LOGO_URI}" x="{cx - w / 2:.1f}" y="{cy - h / 2:.1f}" '
            f'width="{w:.1f}" height="{h:.1f}" preserveAspectRatio="xMidYMid meet"/>')


def logo_patch(cx, cy, r, ring):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" stroke="{OUT}" stroke-width="4"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r - 7}" fill="none" stroke="{ring}" stroke-width="2.5" '
            f'stroke-dasharray="6 5" opacity="0.8"/>'
            + logo_img(cx, cy, (r - 12) * 1.6))


# --------------------------------------------------------------------------
# Body parts
# --------------------------------------------------------------------------
def legs(c):
    s = []
    if c["bottom"] == "skirt":
        s.append(f'<path d="M 214,690 L 386,690 L 414,934 C 380,944 220,944 186,934 Z" '
                 f'fill="{c["pants"]}" stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>')
        s.append(f'<path d="M 252,760 L 240,930 M 348,760 L 360,930" stroke="{c["pants_shade"]}" '
                 f'stroke-width="4" stroke-linecap="round" fill="none"/>')
    else:
        s.append(f'<path d="M 212,630 L 388,630 L 384,928 L 306,928 L 300,716 L 294,928 L 216,928 Z" '
                 f'fill="{c["pants"]}" stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>')
        s.append(f'<path d="M 255,700 L 255,925 M 345,700 L 345,925" stroke="{c["pants_shade"]}" '
                 f'stroke-width="3" fill="none" opacity="0.6"/>')
    # shoes
    for d, sole in (
        ("M 218,918 L 294,918 L 296,950 Q 296,967 279,967 L 205,967 Q 189,967 191,952 Q 195,929 218,918 Z",
         "M 191,952 L 296,952 L 296,950 Q 296,967 279,967 L 205,967 Q 189,967 191,952 Z"),
        ("M 382,918 L 306,918 L 304,950 Q 304,967 321,967 L 395,967 Q 411,967 409,952 Q 405,929 382,918 Z",
         "M 409,952 L 304,952 L 304,950 Q 304,967 321,967 L 395,967 Q 411,967 409,952 Z"),
    ):
        s.append(f'<path d="{d}" fill="{c["shoe"]}" stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>')
        s.append(f'<path d="{sole}" fill="{c["sole"]}" stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>')
    return "\n".join(s)


def torso(c):
    s = []
    if not c.get("hijab"):
        s.append(f'<path d="M 274,340 L 326,340 L 328,432 L 272,432 Z" fill="{c["skin"]}" '
                 f'stroke="{OUT}" stroke-width="{SW}"/>')
        s.append(f'<path d="M 275,352 Q 300,378 325,352 L 325,372 Q 300,392 275,372 Z" '
                 f'fill="{c["skin_shade"]}" opacity="0.55"/>')
    if c["shirt_len"] == "tunic":
        body = ("M 214,436 C 214,420 226,412 244,410 L 356,410 C 374,412 386,420 386,436 "
                "L 404,752 C 405,764 398,772 386,772 L 214,772 C 202,772 195,764 196,752 Z")
    else:
        body = ("M 214,436 C 214,420 226,412 244,410 L 356,410 C 374,412 386,420 386,436 "
                "L 392,644 C 392,656 385,662 373,662 L 227,662 C 215,662 208,656 208,644 Z")
    s.append(f'<path d="{body}" fill="{c["shirt"]}" stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>')
    if c["shirt_len"] == "tunic":
        s.append(f'<path d="M 214,700 L 220,770 M 386,700 L 380,770" stroke="{c["shirt_shade"]}" '
                 f'stroke-width="4" stroke-linecap="round" fill="none"/>')
    else:
        s.append(f'<path d="M 212,640 L 388,640" stroke="{c["shirt_shade"]}" stroke-width="4" fill="none"/>')
    if not c.get("hijab"):
        # round collar
        s.append(f'<path d="M 264,410 Q 300,458 336,410" fill="none" stroke="{c["shirt_shade"]}" '
                 f'stroke-width="12" stroke-linecap="round"/>')
        s.append(f'<path d="M 270,410 Q 300,448 330,410 Z" fill="{c["skin"]}" stroke="{OUT}" '
                 f'stroke-width="{SW}" stroke-linejoin="round"/>')
    # logo on the chest
    cy = 556 if c["shirt_len"] == "tunic" else 528
    if c["logo"] == "direct":
        s.append(logo_img(300, cy, 150))
    else:
        s.append(logo_patch(300, cy, 66, c["shirt_shade"]))
    return "\n".join(s)


def arm(side, c):
    """Arm drawn in three passes (outline / fill / details) that share transforms."""
    sx, sy = SHOULDER[side]
    long_sleeve = c["sleeves"] == "long"
    w = 50 if long_sleeve else 46
    upper_col = c["shirt"] if long_sleeve else c["skin"]
    fore_col = c["shirt"] if long_sleeve else c["skin"]
    rest_u, rest_f = (12, -6) if side == "L" else (-12, 6)
    thumb = 1 if side == "L" else -1

    def nest(upper, fore, hand, thumb_s, finger, open_lines=""):
        return (f'<g class="u{side}" transform="rotate({rest_u})">{upper}'
                f'<g class="f{side}" transform="translate(0,{UPPER}) rotate({rest_f})">{fore}'
                f'<g class="h{side}" transform="translate(0,{HAND})">{hand}'
                f'<g class="th{side}" transform="scale({thumb},1)">{thumb_s}</g>'
                f'<g class="fi{side}" style="display:none">{finger}</g>'
                f'<g class="ol{side}">{open_lines}</g>'
                f'</g></g></g>')

    def line(length, col, width):
        return (f'<line x1="0" y1="0" x2="0" y2="{length}" stroke="{col}" stroke-width="{width}" '
                f'stroke-linecap="round"/>')

    o = SW * 2
    outline = nest(
        line(UPPER, OUT, w + o),
        line(FORE, OUT, w + o),
        f'<ellipse cx="0" cy="0" rx="{26 + SW}" ry="{28 + SW}" fill="{OUT}"/>',
        f'<ellipse cx="23" cy="-4" rx="{9 + SW}" ry="{15 + SW}" transform="rotate(-28 23 -4)" fill="{OUT}"/>',
        f'<rect x="{-7 - SW}" y="{6 - SW}" width="{14 + o}" height="{46 + o}" rx="{7 + SW}" fill="{OUT}"/>',
    )
    fill = nest(
        line(UPPER, upper_col, w),
        line(FORE, fore_col, w),
        f'<ellipse cx="0" cy="0" rx="26" ry="28" fill="{c["skin"]}"/>',
        f'<ellipse cx="23" cy="-4" rx="9" ry="15" transform="rotate(-28 23 -4)" fill="{c["skin"]}"/>',
        f'<rect x="-7" y="6" width="14" height="46" rx="7" fill="{c["skin"]}"/>'
        f'<path d="M -6,18 L 6,18" stroke="{c["skin_shade"]}" stroke-width="3" stroke-linecap="round"/>',
    )
    if long_sleeve:
        upper_d = ""
        fore_d = (f'<rect x="{-w / 2 - 3}" y="{FORE - 20}" width="{w + 6}" height="18" rx="7" '
                  f'fill="{c["shirt_shade"]}" stroke="{OUT}" stroke-width="4"/>')
    else:
        upper_d = (f'<path d="M -30,-14 Q 0,-26 30,-14 L 33,58 Q 0,66 -33,58 Z" fill="{c["shirt"]}" '
                   f'stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>'
                   f'<path d="M -31,46 Q 0,54 31,46" stroke="{c["shirt_shade"]}" stroke-width="4" fill="none"/>')
        fore_d = ""
    fingers = (f'<path d="M -11,11 L -11,24 M 0,14 L 0,27 M 11,11 L 11,24" stroke="{c["skin_shade"]}" '
               f'stroke-width="3.5" stroke-linecap="round" fill="none"/>')
    details = nest(upper_d, fore_d, "", "", "", fingers)
    return (f'<g id="arm{side}" class="arm" transform="translate({sx},{sy})" '
            f'data-upper="{UPPER}" data-hand="{HAND}">'
            f'{outline}{fill}{details}</g>')


def ears(c):
    if c.get("hijab"):
        return ""
    s = []
    for cx, d in ((190, "M 196,262 Q 182,272 194,288"), (410, "M 404,262 Q 418,272 406,288")):
        s.append(f'<ellipse cx="{cx}" cy="275" rx="20" ry="27" fill="{c["skin"]}" stroke="{OUT}" stroke-width="{SW}"/>')
        s.append(f'<path d="{d}" stroke="{c["skin_shade"]}" stroke-width="5" fill="none" stroke-linecap="round"/>')
    return "".join(s)


FACE = {"normal": (300, 262, 112, 122), "hijab": (300, 266, 104, 116)}


def face(c):
    cx, cy, rx, ry = FACE["hijab" if c.get("hijab") else "normal"]
    s = [f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{c["skin"]}" stroke="{OUT}" stroke-width="{SW}"/>']
    if c.get("stubble"):
        s.append(f'<clipPath id="{c["id"]}-faceclip"><ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/></clipPath>')
        s.append(f'<path clip-path="url(#{c["id"]}-faceclip)" d="M 180,276 C 186,352 236,394 300,396 '
                 f'C 364,394 414,352 420,276 C 404,326 372,350 300,352 C 228,350 196,326 180,276 Z" '
                 f'fill="{c["hair"]}" opacity="0.22"/>')
        s.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" stroke="{OUT}" stroke-width="{SW}"/>')
    return "".join(s)


def hair_front(c):
    style = c["hair_style"]
    if style == "short":
        return (f'<path d="M 186,262 C 172,190 204,124 268,110 C 312,100 362,108 392,134 '
                f'C 422,162 428,214 414,262 C 408,232 398,214 386,204 C 362,214 330,206 316,186 '
                f'C 294,206 250,214 222,200 C 206,214 194,236 186,262 Z" fill="{c["hair"]}" '
                f'stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>'
                f'<path d="M 316,186 C 326,168 340,156 360,150 M 270,124 C 300,118 330,122 352,134" '
                f'stroke="{c["hair_hi"]}" stroke-width="5" fill="none" stroke-linecap="round"/>')
    if style == "cap":
        return (
            # side burns under the cap
            f'<path d="M 188,200 L 212,200 L 208,288 C 198,276 190,248 188,200 Z" fill="{c["hair"]}" '
            f'stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>'
            f'<path d="M 412,200 L 388,200 L 392,288 C 402,276 410,248 412,200 Z" fill="{c["hair"]}" '
            f'stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>'
            # crown
            f'<path d="M 188,208 C 186,132 238,92 300,92 C 362,92 414,132 412,208 Q 300,190 188,208 Z" '
            f'fill="{c["cap"]}" stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>'
            f'<path d="M 300,94 L 300,112 M 240,108 C 224,132 216,164 216,200 M 360,108 C 376,132 384,164 384,200" '
            f'stroke="{c["cap_shade"]}" stroke-width="4" fill="none" stroke-linecap="round"/>'
            f'<circle cx="300" cy="93" r="8" fill="{c["cap_shade"]}" stroke="{OUT}" stroke-width="4"/>'
            + logo_patch(300, 148, 40, c["cap_shade"]) +
            # bill, seen from the front: a lens that curves down toward the viewer
            f'<path d="M 194,204 Q 300,186 406,204 Q 404,234 300,238 Q 196,234 194,204 Z" fill="{c["cap_shade"]}" '
            f'stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>'
            f'<path d="M 214,222 Q 300,236 386,222" stroke="{c["cap"]}" stroke-width="4" fill="none" '
            f'stroke-linecap="round" opacity="0.7"/>'
        )
    return ""


def hijab_back(c):
    if not c.get("hijab"):
        return ""
    return (f'<path d="M 300,106 C 400,106 448,178 442,284 C 438,346 428,386 448,420 '
            f'C 464,450 438,478 300,480 C 162,478 136,450 152,420 C 172,386 162,346 158,284 '
            f'C 152,178 200,106 300,106 Z" fill="{c["hijab"]}" stroke="{OUT}" stroke-width="{SW}" '
            f'stroke-linejoin="round"/>'
            f'<path d="M 214,376 Q 300,446 386,376 M 172,428 Q 214,452 262,458 M 428,428 Q 386,452 338,458" '
            f'stroke="{c["hijab_shade"]}" stroke-width="5" fill="none" stroke-linecap="round"/>')


def hijab_front(c):
    if not c.get("hijab"):
        return ""
    return (f'<path d="M 194,276 C 186,182 236,138 300,138 C 364,138 414,182 406,276 '
            f'C 398,216 360,180 300,180 C 240,180 202,216 194,276 Z" fill="{c["hijab"]}" '
            f'stroke="{OUT}" stroke-width="{SW}" stroke-linejoin="round"/>'
            f'<path d="M 232,160 C 256,150 280,146 300,146" stroke="{c["hijab_hi"]}" stroke-width="5" '
            f'fill="none" stroke-linecap="round"/>')


def eyes(c):
    s = ['<g id="eyes">']
    for cx in (258, 342):
        s.append(f'<g class="eye" data-cx="{cx}" data-cy="274">'
                 f'<ellipse cx="{cx}" cy="274" rx="12.5" ry="17" fill="{OUT}"/>'
                 f'<circle cx="{cx + 4}" cy="266" r="4.8" fill="#ffffff"/>'
                 f'<circle cx="{cx - 4}" cy="282" r="2.2" fill="#ffffff" opacity="0.8"/></g>')
    s.append("</g>")
    if c["gender"] == "f":
        s.append(f'<path d="M 245,264 L 236,257 M 355,264 L 364,257" stroke="{OUT}" stroke-width="4" '
                 f'stroke-linecap="round"/>')
    if c.get("glasses"):
        s.append(f'<g fill="#ffffff" fill-opacity="0.18" stroke="{OUT}" stroke-width="5">'
                 f'<rect x="224" y="246" width="68" height="56" rx="20"/>'
                 f'<rect x="308" y="246" width="68" height="56" rx="20"/></g>'
                 f'<path d="M 292,268 Q 300,262 308,268" stroke="{OUT}" stroke-width="5" fill="none"/>')
    bw = 8 if c["gender"] == "m" else 6
    col = c.get("hair", OUT)
    s.append(f'<g id="brows" stroke="{col}" stroke-width="{bw}" fill="none" stroke-linecap="round">'
             f'<path d="M 238,236 Q 258,224 280,232"/><path d="M 320,232 Q 342,224 362,236"/></g>')
    return "".join(s)


MOUTH_DARK = "#6d1f2c"
TONGUE = "#ef7d86"


def mouths():
    m = {
        "smile": f'<path d="M 274,326 Q 300,352 326,326" stroke="{OUT}" stroke-width="6" fill="none" stroke-linecap="round"/>',
        "mid": (f'<path d="M 280,324 Q 300,354 320,324 Q 300,330 280,324 Z" fill="{MOUTH_DARK}" '
                f'stroke="{OUT}" stroke-width="4" stroke-linejoin="round"/>'),
        "big": (f'<path d="M 272,320 Q 300,372 328,320 Q 300,330 272,320 Z" fill="{MOUTH_DARK}" '
                f'stroke="{OUT}" stroke-width="4" stroke-linejoin="round"/>'
                f'<path d="M 287,352 Q 300,342 313,352 Q 300,360 287,352 Z" fill="{TONGUE}"/>'),
        "o": (f'<ellipse cx="300" cy="334" rx="10" ry="13" fill="{MOUTH_DARK}" stroke="{OUT}" stroke-width="4"/>'),
        "grin": (f'<path d="M 266,318 Q 300,378 334,318 Q 300,328 266,318 Z" fill="{MOUTH_DARK}" '
                 f'stroke="{OUT}" stroke-width="4" stroke-linejoin="round"/>'
                 f'<path d="M 272,322 Q 300,330 328,322 L 325,333 Q 300,340 275,333 Z" fill="#ffffff"/>'
                 f'<path d="M 286,356 Q 300,346 314,356 Q 300,364 286,356 Z" fill="{TONGUE}"/>'),
    }
    return "".join(f'<g class="mouth" data-shape="{k}" style="display:{"inline" if k == "smile" else "none"}">{v}</g>'
                   for k, v in m.items())


def head(c):
    return (
        f'<g id="head" transform="rotate(0 300 400)">'
        + hijab_back(c) + ears(c) + face(c) + hijab_front(c) + hair_front(c)
        + eyes(c)
        + f'<path d="M 293,306 Q 300,313 307,306" stroke="{c["skin_shade"]}" stroke-width="5" fill="none" stroke-linecap="round"/>'
        + '<g fill="#ff6f73" opacity="0.28"><ellipse cx="232" cy="314" rx="17" ry="10"/>'
          '<ellipse cx="368" cy="314" rx="17" ry="10"/></g>'
        + f'<g id="mouth">{mouths()}</g>'
        + "</g>"
    )


def character_svg(c):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-100 0 800 1000" width="800" height="1000" id="{c['id']}">
<title>{c['name_ar']} - {c['name_en']}</title>
<ellipse id="shadow" cx="300" cy="966" rx="150" ry="16" fill="#000000" opacity="0.16"/>
<g id="legs">{legs(c)}</g>
<g id="upper">
<g id="slotBack">{arm('L', c)}{arm('R', c)}</g>
<g id="torso">{torso(c)}</g>
{head(c)}
<g id="slotFront"></g>
</g>
</svg>
"""


# --------------------------------------------------------------------------
# Characters
# --------------------------------------------------------------------------
CHARACTERS = [
    dict(id="ahmed", name_ar="أحمد", name_en="Ahmed", gender="m",
         skin="#efc29a", skin_shade="#d39a6e", hair="#2a1b17", hair_hi="#5a4036", hair_style="short",
         shirt="#ffffff", shirt_shade="#cfdbe6", shirt_len="normal", sleeves="short", logo="direct",
         bottom="pants", pants="#2f5f9e", pants_shade="#244a7c", shoe="#ffffff", sole="#1d7bc1"),
    dict(id="mariam", name_ar="مريم", name_en="Mariam", gender="f",
         skin="#f6d4b4", skin_shade="#dfa985", hijab="#3f98d6", hijab_shade="#2a77b0", hijab_hi="#7cbbe6",
         hair_style="none",
         shirt="#ffffff", shirt_shade="#cfdbe6", shirt_len="tunic", sleeves="long", logo="direct",
         bottom="skirt", pants="#283a5e", pants_shade="#1d2b47", shoe="#3b2c2a", sole="#1f1716"),
    dict(id="yousef", name_ar="يوسف", name_en="Yousef", gender="m",
         skin="#cf9468", skin_shade="#a8704a", hair="#1d1411", hair_hi="#3e2c25", hair_style="cap",
         cap="#1d7bc1", cap_shade="#145d94", stubble=True, glasses=True,
         shirt="#78b843", shirt_shade="#5c9430", shirt_len="normal", sleeves="short", logo="patch",
         bottom="pants", pants="#5b5f66", pants_shade="#45484e", shoe="#2f3238", sole="#e9e9e9"),
    dict(id="sara", name_ar="سارة", name_en="Sara", gender="f",
         skin="#ebb894", skin_shade="#cc8e66", hijab="#ec8a2f", hijab_shade="#c96b17", hijab_hi="#f6b071",
         hair_style="none",
         shirt="#1d7bc1", shirt_shade="#145d94", shirt_len="tunic", sleeves="long", logo="patch",
         bottom="pants", pants="#3a3d45", pants_shade="#2a2c32", shoe="#ffffff", sole="#ec8a2f"),
]

STAGE_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:transparent;overflow:hidden}}
svg{{width:100vw;height:100vh;display:block}}
</style></head><body>
{svg}
<script src="../../src/anim.js"></script>
</body></html>
"""


def main():
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    for c in CHARACTERS:
        svg = character_svg(c)
        (SVG_DIR / f"{c['id']}.svg").write_text(svg, encoding="utf-8")
        (STAGE_DIR / f"{c['id']}.html").write_text(STAGE_HTML.format(svg=svg), encoding="utf-8")
        print("wrote", c["id"])


if __name__ == "__main__":
    main()
