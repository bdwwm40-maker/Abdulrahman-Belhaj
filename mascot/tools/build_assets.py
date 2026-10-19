"""Build the derived mascot assets from the two master files in ../final:
  mascot-full-body.png  (studio render with the agency logo badge)
  mascot-cutout.png     (same, transparent background — see make_cutout.py)

Outputs (in ../final):
  mascot-emoji.png            1024x1024 transparent head-and-shoulders sticker
  mascot-avatar.png           1080x1080 round profile picture on the agency blue
  mascot-identity-sheet.png   2560x2048 identity sheet (character, logo, values, colours)
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "final"
FONT = Path(__file__).with_name("fonts") / "Cairo.ttf"
LOGO = ROOT / "logo" / "agency-logo-transparent.png"

BLUE, GREEN, ORANGE, DARK = "#006CB4", "#78B424", "#E46C0C", "#181818"

# head-and-shoulders box in the 3072x4096 masters: cap top ~y114, face centre ~x1510,
# chest badge ends ~y1174 — the crop keeps the badge in frame
BUST = (886, 54, 2134, 1302)


def font(size, weight="Bold"):
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_name(weight)
    return f


def emoji(cutout):
    bust = cutout.crop(BUST).resize((1024, 1024), Image.LANCZOS)
    bust.save(FINAL / "mascot-emoji.png", optimize=True)
    return bust


def avatar(bust):
    size = 1080
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.radial_gradient("L").resize((size, size))
    light = Image.new("RGBA", (size, size), (40, 150, 215, 255))
    deep = Image.new("RGBA", (size, size), (0, 84, 150, 255))
    disc = Image.composite(deep, light, grad)
    fig = bust.resize((1000, 1000), Image.LANCZOS)
    disc.alpha_composite(fig, (40, 100))
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(disc, (0, 0), mask)
    out.save(FINAL / "mascot-avatar.png", optimize=True)


def centered(draw, y, text, f, fill, cx):
    draw.text((cx, y), text, font=f, fill=fill, anchor="ma", direction="rtl", language="ar")


def sheet(full):
    W, H = 2560, 2048
    page = Image.new("RGB", (W, H), "white")
    page.paste(full.convert("RGB").resize((1536, 2048), Image.LANCZOS), (0, 0))
    d = ImageDraw.Draw(page)
    cx = 1536 + (W - 1536) // 2

    logo = Image.open(LOGO).convert("RGBA")
    lw = 520
    logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    page.paste(logo, (cx - lw // 2, 110), logo)

    centered(d, 860, "الشخصية الرسمية للوكالة", font(60, "ExtraBold"), DARK, cx)
    centered(d, 975, "الوكالة الوطنية للجهود التطوعية للشباب", font(38, "SemiBold"), "#3C3C3C", cx)
    d.line([(cx - 232, 1100), (cx + 232, 1100)], fill=ORANGE, width=4)
    centered(d, 1140, "الشباب • التطوع • العطاء", font(40, "Bold"), BLUE, cx)
    centered(d, 1205, "الانتماء الوطني • العمل المؤسسي", font(40, "Bold"), BLUE, cx)
    centered(d, 1400, "ألوان الهوية", font(32, "SemiBold"), "#3C3C3C", cx)
    for i, col in enumerate([BLUE, GREEN, ORANGE, DARK]):
        x = cx - 216 + i * 144
        d.ellipse([x - 58, 1502, x + 58, 1618], fill=col)
    centered(d, 1740, "إيثار وعطاء", font(64, "ExtraBold"), GREEN, cx)
    page.save(FINAL / "mascot-identity-sheet.png", optimize=True)


def main():
    full = Image.open(FINAL / "mascot-full-body.png")
    cutout = Image.open(FINAL / "mascot-cutout.png").convert("RGBA")
    avatar(emoji(cutout))
    sheet(full)
    print("built emoji, avatar, identity sheet in", FINAL)


if __name__ == "__main__":
    main()
