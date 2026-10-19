"""Composite the official agency logo onto the mascot's left chest.

The logo pixels are never redrawn: the original PNG is only scaled (aspect ratio
locked), optionally rotated a few degrees to follow the jacket panel, and lit to
match the render. Two looks:
  patch  - the logo sits on an off-white embroidered badge with a stitched edge
           (keeps the logo's own white background, best legibility on brown cloth)
  print  - the logo is printed directly on the fabric (transparent background)

usage:
  python3 place_logo.py BASE.png OUT.png --cx X --cy Y --width W [--rotate DEG] [--mode patch|print]
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops

LOGO = __file__.rsplit("/", 2)[0] + "/logo/agency-logo-transparent.png"
PATCH_COLOR = (247, 243, 234)
STITCH_COLOR = (74, 42, 20)


def lighting_map(base, box, strength):
    """Low-frequency luminance of the fabric under `box`, normalised around 1.0."""
    region = base.crop(box).convert("L")
    blur = region.filter(ImageFilter.GaussianBlur(max(region.size) / 6))
    arr = np.asarray(blur, dtype=np.float32)
    arr = arr / max(arr.mean(), 1.0)
    return 1.0 + (arr - 1.0) * strength


def thread_texture(size, seed=7):
    """Very fine diagonal thread grain, centred on 1.0 (±2.5%)."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    period = max(w, h) / 160.0
    grain = np.sin((xx + yy) * (2 * np.pi / period)) * 0.012
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 0.008, (h, w)).astype(np.float32)
    noise = np.asarray(Image.fromarray(((noise + 0.05) * 2000).clip(0, 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(0.7)), dtype=np.float32) / 2000 - 0.05
    return 1.0 + grain + noise


def build_patch(logo, mode):
    lw, lh = logo.size
    if mode == "print":
        return logo
    # oval badge: the logo's bounding box inscribed in an ellipse with a little air
    pad_x, pad_y = int(lw * 0.24), int(lh * 0.17)
    pw, ph = lw + 2 * pad_x, lh + 2 * pad_y
    patch = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(patch)
    d.ellipse([0, 0, pw - 1, ph - 1], fill=PATCH_COLOR + (255,))
    # merrowed edge: darker rim + dashed stitch line just inside it
    rim = max(2, int(pw * 0.03))
    d.ellipse([0, 0, pw - 1, ph - 1], outline=(196, 168, 128, 255), width=rim)
    inset = int(pw * 0.055)
    stitch = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(stitch).ellipse(
        [inset, inset, pw - 1 - inset, ph - 1 - inset],
        outline=255, width=max(2, int(pw * 0.01)))
    sarr = np.asarray(stitch).copy()
    yy, xx = np.nonzero(sarr)
    dash = max(4, int(pw * 0.03))
    gaps = ((xx + yy) // dash) % 2 == 1  # break the line into stitches
    sarr[yy[gaps], xx[gaps]] = 0
    stitch_layer = Image.new("RGBA", (pw, ph), STITCH_COLOR + (0,))
    stitch_layer.putalpha(Image.fromarray(sarr).filter(ImageFilter.GaussianBlur(0.6)))
    patch = Image.alpha_composite(patch, stitch_layer)
    patch.alpha_composite(logo, (pad_x, pad_y))
    return patch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("out")
    ap.add_argument("--cx", type=float, required=True)
    ap.add_argument("--cy", type=float, required=True)
    ap.add_argument("--width", type=float, required=True, help="logo width in px (badge adds a margin)")
    ap.add_argument("--rotate", type=float, default=0.0, help="degrees, positive = counter-clockwise")
    ap.add_argument("--mode", choices=["patch", "print"], default="patch")
    ap.add_argument("--light", type=float, default=0.5, help="how strongly render lighting shades the logo")
    ap.add_argument("--weave", type=float, default=0.35, help="how much fabric texture shows through")
    a = ap.parse_args()

    base = Image.open(a.base).convert("RGB")
    logo = Image.open(LOGO).convert("RGBA")
    scale = a.width / logo.width
    logo = logo.resize((round(logo.width * scale), round(logo.height * scale)), Image.LANCZOS)

    patch = build_patch(logo, a.mode)
    if a.rotate:
        patch = patch.rotate(a.rotate, resample=Image.BICUBIC, expand=True)
    pw, ph = patch.size
    x0, y0 = round(a.cx - pw / 2), round(a.cy - ph / 2)
    box = (x0, y0, x0 + pw, y0 + ph)

    # shade with the render's own lighting + fine thread grain (keeps hue, nudges value only)
    rgb = np.asarray(patch.convert("RGB"), dtype=np.float32)
    shade = lighting_map(base, box, a.light) * thread_texture((pw, ph))
    rgb = rgb * shade[..., None]
    # let the cloth's own weave show through faintly (high-pass of the fabric under the badge)
    under = np.asarray(base.crop(box).convert("L"), dtype=np.float32)
    weave = under - np.asarray(base.crop(box).convert("L").filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)
    rgb = (rgb + weave[..., None] * a.weave).clip(0, 255).astype(np.uint8)
    lit = Image.fromarray(rgb)
    lit.putalpha(patch.getchannel("A"))

    out = base.convert("RGBA")
    # soft contact shadow so the badge sits on the cloth instead of floating
    alpha = patch.getchannel("A")
    shadow = Image.new("RGBA", (pw, ph), (40, 22, 10, 0))
    shadow.putalpha(alpha.point(lambda v: int(v * (0.38 if a.mode == "patch" else 0.12))))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(2, pw * 0.02)))
    off = max(1, round(pw * 0.012))
    out.alpha_composite(shadow, (x0 + off, y0 + off * 2))
    out.alpha_composite(lit, (x0, y0))
    out.convert("RGB").save(a.out)
    print("placed", a.mode, "box", box)


if __name__ == "__main__":
    main()
