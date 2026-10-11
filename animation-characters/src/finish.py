#!/usr/bin/env python3
"""Post-process rendered stills: tight transparent crops, a team picture and a preview sheet."""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHARS = [("ahmed", "أحمد"), ("mariam", "مريم"), ("yousef", "يوسف"), ("sara", "سارة")]
POSES = [("idle", "وقوف"), ("wave", "تلويح"), ("talk", "تحدّث"),
         ("point-right", "إشارة لليمين"), ("point-left", "إشارة لليسار")]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def crop(im, pad=24):
    x0, y0, x1, y1 = im.getchannel("A").getbbox()
    return im.crop((max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, im.width), min(y1 + pad, im.height)))


def main(raw_dir):
    raw = pathlib.Path(raw_dir)
    png_dir = ROOT / "characters" / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    for cid, _ in CHARS:
        for pose, _ in POSES:
            im = Image.open(raw / f"{cid}_{pose}.png").convert("RGBA")
            crop(im).save(png_dir / f"{cid}_{pose}.png", optimize=True)

    # team picture: the four volunteers side by side (transparent background)
    team_poses = {"ahmed": "idle", "mariam": "idle", "yousef": "idle", "sara": "wave"}
    full = [Image.open(raw / f"{cid}_{team_poses[cid]}.png").convert("RGBA") for cid, _ in CHARS]
    # all stills share the same canvas, so crop them with one common box to keep feet aligned
    boxes = [im.getchannel("A").getbbox() for im in full]
    top = min(b[1] for b in boxes) - 30
    bottom = max(b[3] for b in boxes) + 30
    step = 720
    team = Image.new("RGBA", (step * 3 + 1280 + 120, bottom - top), (0, 0, 0, 0))
    for i, im in enumerate(full):
        # each character is centred at x=1080 of its 2160px canvas
        team.alpha_composite(im.crop((440, top, 1720, bottom)), (60 + i * step, 0))
    team = crop(team, 30)
    team.save(ROOT / "characters" / "team.png", optimize=True)

    # preview sheet with Arabic labels
    cw, ch = 300, 400
    font = ImageFont.truetype(FONT, 26, layout_engine=ImageFont.Layout.RAQM)
    small = ImageFont.truetype(FONT, 20, layout_engine=ImageFont.Layout.RAQM)
    head_h, side_w = 60, 130
    sheet = Image.new("RGB", (side_w + cw * len(POSES), head_h + ch * len(CHARS)), (240, 244, 248))
    d = ImageDraw.Draw(sheet)
    for k, (_, label) in enumerate(POSES):
        d.text((side_w + k * cw + cw / 2, head_h / 2), label, font=small, fill=(43, 34, 51),
               anchor="mm", direction="rtl", language="ar")
    for r, (cid, name) in enumerate(CHARS):
        d.text((side_w / 2, head_h + r * ch + ch / 2), name, font=font, fill=(29, 123, 193),
               anchor="mm", direction="rtl", language="ar")
        for k, (pose, _) in enumerate(POSES):
            im = Image.open(raw / f"{cid}_{pose}.png").convert("RGBA").crop((180, 40, 1980, 2700))
            im.thumbnail((cw, ch - 10), Image.LANCZOS)
            sheet.paste(im, (side_w + k * cw + (cw - im.width) // 2, head_h + r * ch + (ch - im.height) // 2), im)
    sheet.save(ROOT / "preview.png", optimize=True)


if __name__ == "__main__":
    main(sys.argv[1])
