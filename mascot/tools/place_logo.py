"""Composite the official agency logo onto the mascot's left chest.

The logo pixels are never redrawn or re-lit: the original PNG is only scaled
(aspect ratio locked) and optionally rotated a few degrees to follow the jacket
panel. Only the badge backing and its stitching take the render's lighting and
the cloth weave, so the logo's colours stay exactly as supplied. Two looks:
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


def stitch_ring(size, inset, width, dash):
    """Dashed stitch line along an inset ellipse, dashes spaced by arc length."""
    pw, ph = size
    rx, ry = pw / 2 - inset, ph / 2 - inset
    t = np.linspace(0, 2 * np.pi, 4000)
    pts = np.stack([pw / 2 + rx * np.cos(t), ph / 2 + ry * np.sin(t)], axis=1)
    arc = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    ring = Image.new("L", size, 0)
    d = ImageDraw.Draw(ring)
    on = (arc // dash) % 2 == 0
    for i in range(len(pts) - 1):
        if on[i]:
            d.line([tuple(pts[i]), tuple(pts[i + 1])], fill=255, width=width)
    return ring


def build_patch(logo, mode):
    """Return (backing, logo offset): the badge backing without the logo, and where the logo goes."""
    lw, lh = logo.size
    if mode == "print":
        return Image.new("RGBA", logo.size, (0, 0, 0, 0)), (0, 0)
    # oval badge: the logo's bounding box inscribed in an ellipse with a little air
    pad_x, pad_y = int(lw * 0.16), int(lh * 0.11)
    pw, ph = lw + 2 * pad_x, lh + 2 * pad_y
    patch = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(patch)
    d.ellipse([0, 0, pw - 1, ph - 1], fill=PATCH_COLOR + (255,))
    # merrowed edge: darker rim + dashed stitch line just inside it
    rim = max(2, int(pw * 0.03))
    d.ellipse([0, 0, pw - 1, ph - 1], outline=(196, 168, 128, 255), width=rim)
    ring = stitch_ring((pw, ph), inset=pw * 0.05, width=max(2, int(pw * 0.01)), dash=max(4, pw * 0.03))
    stitch_layer = Image.new("RGBA", (pw, ph), STITCH_COLOR + (0,))
    stitch_layer.putalpha(ring.filter(ImageFilter.GaussianBlur(0.6)))
    return Image.alpha_composite(patch, stitch_layer), (pad_x, pad_y)


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

    backing, (lx, ly) = build_patch(logo, a.mode)
    logo_layer = Image.new("RGBA", backing.size, (0, 0, 0, 0))
    logo_layer.alpha_composite(logo, (lx, ly))
    if a.rotate:
        backing = backing.rotate(a.rotate, resample=Image.BICUBIC, expand=True)
        logo_layer = logo_layer.rotate(a.rotate, resample=Image.BICUBIC, expand=True)
    pw, ph = backing.size
    x0, y0 = round(a.cx - pw / 2), round(a.cy - ph / 2)
    box = (x0, y0, x0 + pw, y0 + ph)

    # backing only: the render's own lighting + fine thread grain + a hint of the cloth weave
    rgb = np.asarray(backing.convert("RGB"), dtype=np.float32)
    shade = lighting_map(base, box, a.light) * thread_texture((pw, ph))
    rgb = rgb * shade[..., None]
    under = base.crop(box).convert("L")
    weave = (np.asarray(under, dtype=np.float32)
             - np.asarray(under.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32))
    rgb = (rgb + weave[..., None] * a.weave).clip(0, 255).astype(np.uint8)
    lit = Image.fromarray(rgb)
    lit.putalpha(backing.getchannel("A"))

    out = base.convert("RGBA")
    # soft contact shadow, drawn on a padded canvas so the blur is never clipped
    silhouette = backing.getchannel("A") if a.mode == "patch" else logo_layer.getchannel("A")
    pad = round(max(pw, ph) * 0.15)
    shadow = Image.new("RGBA", (pw + 2 * pad, ph + 2 * pad), (40, 22, 10, 0))
    sa = Image.new("L", shadow.size, 0)
    sa.paste(silhouette.point(lambda v: int(v * (0.38 if a.mode == "patch" else 0.12))), (pad, pad))
    shadow.putalpha(sa)
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(2, pw * 0.02)))
    off = max(1, round(pw * 0.012))
    out.alpha_composite(shadow, (x0 - pad + off, y0 - pad + off * 2))
    out.alpha_composite(lit, (x0, y0))
    out.alpha_composite(logo_layer, (x0, y0))
    out.convert("RGB").save(a.out)
    print("placed", a.mode, "box", box)


if __name__ == "__main__":
    main()
