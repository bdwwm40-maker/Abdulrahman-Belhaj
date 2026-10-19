"""Build the derived mascot assets from the two master files in ../final:
  mascot-full-body.png  (studio render with the agency logo badge)
  mascot-cutout.png     (same, transparent background — see make_cutout.py)

Outputs (in ../final):
  mascot-emoji.png            1024x1024 transparent head-and-shoulders sticker
  mascot-avatar.png           1080x1080 round profile picture on the agency blue
  mascot-identity-sheet.png   2560x2048 identity sheet (character, logo, values, colours)
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "final"
FONT = Path(__file__).with_name("fonts") / "Cairo.ttf"
LOGO = ROOT / "logo" / "agency-logo-transparent.png"

# median colours sampled from the official logo
BLUE, GREEN, ORANGE, DARK = "#0375BA", "#80BB2E", "#E47617", "#1F1B1A"

# head-and-shoulders box in the 3072x4096 masters: cap top ~y114, face centre ~x1510,
# chest badge spans ~y910-1180 — the crop keeps the whole badge in frame
BUST = (940, 54, 2080, 1194)


def font(size, weight="Bold"):
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_name(weight)
    return f


def sticker(bust, size=1024, border=16):
    """Die-cut sticker: white outline around the silhouette and a soft drop shadow."""
    inner = size - 2 * (border + 14)
    fig = bust.resize((inner, inner), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    a = Image.new("L", (size, size), 0)
    a.paste(fig.getchannel("A"), (border + 14, border + 14))
    outline = a.filter(ImageFilter.MaxFilter(2 * border + 1)).filter(ImageFilter.GaussianBlur(1.2))
    shadow = Image.new("RGBA", (size, size), (10, 30, 50, 0))
    shadow.putalpha(outline.point(lambda v: int(v * 0.35)).filter(ImageFilter.GaussianBlur(10)))
    canvas.alpha_composite(shadow, (0, 8))
    white = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    white.putalpha(outline)
    canvas.alpha_composite(white)
    canvas.alpha_composite(fig, (border + 14, border + 14))
    return canvas


def emoji(cutout):
    bust = cutout.crop(BUST)
    sticker(bust).save(FINAL / "mascot-emoji.png", optimize=True)
    return bust.resize((1024, 1024), Image.LANCZOS)


def avatar(bust):
    size = 1080
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.radial_gradient("L").resize((size, size))
    light = Image.new("RGBA", (size, size), (52, 152, 214, 255))
    deep = Image.new("RGBA", (size, size), (3, 117, 186, 255))  # logo blue #0375BA
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
    centered(d, 1140, "الشباب، التطوع، العطاء", font(40, "Bold"), BLUE, cx)
    centered(d, 1205, "الانتماء الوطني، العمل المؤسسي", font(40, "Bold"), BLUE, cx)
    centered(d, 1440, "ألوان الهوية", font(32, "SemiBold"), "#3C3C3C", cx)
    for i, col in enumerate([BLUE, GREEN, ORANGE, DARK]):
        x = cx - 216 + i * 144
        d.ellipse([x - 58, 1540, x + 58, 1656], fill=col)
        d.text((x, 1672), col, font=font(22, "SemiBold"), fill="#5A5F66", anchor="ma", direction="ltr")
    page.save(FINAL / "mascot-identity-sheet.png", optimize=True)


def main():
    full = Image.open(FINAL / "mascot-full-body.png")
    cutout = Image.open(FINAL / "mascot-cutout.png").convert("RGBA")
    avatar(emoji(cutout))
    sheet(full)
    print("built emoji, avatar, identity sheet in", FINAL)


if __name__ == "__main__":
    main()
