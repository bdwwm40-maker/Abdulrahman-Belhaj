"""Cut the mascot out of its studio background (transparent PNG for stickers).

1. rembg (BiRefNet by default) predicts the matte at 1536 px wide.
2. Only fully enclosed pin-holes are filled; gaps that connect to the outer
   background (e.g. between the arms and the body) stay transparent.
3. Optional --open-box regions get a morphological opening, which removes thin
   stray strips the image model drew outside the silhouette (shoulder "fins").
4. The matte is upsampled to the full image size and choked by about 1 px.
5. Edge colours are de-contaminated against a reconstructed background plate,
   so no light-grey fringe shows when the sticker sits on a dark colour.

usage:
  python3 make_cutout.py IN.png OUT.png [--model birefnet-general] [--open-box X0 Y0 X1 Y1 ...]
"""
import argparse
import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

WORK_W = 1536


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--model", default="birefnet-general")
    ap.add_argument("--max-hole", type=int, default=400, help="largest enclosed hole to fill (px at working size)")
    ap.add_argument("--open-box", type=int, nargs=4, action="append", default=[],
                    help="full-size box where thin strips outside the body are removed")
    ap.add_argument("--open", type=int, default=11, help="opening kernel (px at working size)")
    a = ap.parse_args()

    full = Image.open(a.src).convert("RGB")
    W, H = full.size
    s = WORK_W / W
    work = full.resize((WORK_W, round(H * s)), Image.LANCZOS)
    matte = np.asarray(remove(work, session=new_session(a.model), only_mask=True)).copy()

    # fill only small holes fully enclosed by the figure
    bg = (matte < 128).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bg, connectivity=4)
    h, w = bg.shape
    filled = 0
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if x > 0 and y > 0 and x + bw < w and y + bh < h and area <= a.max_hole:
            matte[lab == i] = 255
            filled += area
    print("filled", filled, "px of enclosed holes")

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (a.open, a.open))
    for x0, y0, x1, y1 in a.open_box:
        x0, y0, x1, y1 = (round(v * s) for v in (x0, y0, x1, y1))
        reg = matte[y0:y1, x0:x1]
        matte[y0:y1, x0:x1] = np.minimum(reg, cv2.morphologyEx(reg, cv2.MORPH_OPEN, k))

    alpha = cv2.resize(matte, (W, H), interpolation=cv2.INTER_CUBIC)
    alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8)).astype(np.float32) / 255.0  # ~1 px choke
    alpha = np.clip((alpha - 0.02) / 0.96, 0, 1)

    img = np.asarray(full).astype(np.float32)
    fg_mask = cv2.dilate((alpha > 0.01).astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
    small = cv2.resize(img.astype(np.uint8), (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    small_mask = cv2.resize(fg_mask, (W // 4, H // 4), interpolation=cv2.INTER_NEAREST)
    plate = cv2.inpaint(small, small_mask, 9, cv2.INPAINT_TELEA)
    plate = cv2.resize(plate, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)

    a3 = alpha[..., None]
    edge = (a3 > 0.02) & (a3 < 0.98)
    fg = np.where(edge, (img - (1 - a3) * plate) / np.maximum(a3, 0.02), img)
    rgba = np.dstack([np.clip(fg, 0, 255), alpha * 255]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(a.out, optimize=True)
    print("saved", a.out, (W, H))


if __name__ == "__main__":
    main()
