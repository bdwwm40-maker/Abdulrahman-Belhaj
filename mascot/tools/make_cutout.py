"""Cut the mascot out of its studio background (transparent PNG for stickers).

1. rembg (isnet-general-use) predicts the matte at 1536 px wide.
2. A small morphological close fills pin-holes and hairline gaps the model
   leaves where the white shirt meets the light-grey backdrop.
3. The matte is upsampled to the full image size.
4. Edge colours are de-contaminated against a reconstructed background plate,
   so no light-grey fringe shows when the sticker sits on a dark colour.

usage:
  python3 make_cutout.py IN.png OUT.png [--close 21]
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
    ap.add_argument("--close", type=int, default=21, help="closing kernel (px at working size)")
    a = ap.parse_args()

    full = Image.open(a.src).convert("RGB")
    W, H = full.size
    work = full.resize((WORK_W, round(H * WORK_W / W)), Image.LANCZOS)
    matte = np.asarray(remove(work, session=new_session("isnet-general-use"),
                              only_mask=True, post_process_mask=True))

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (a.close, a.close))
    solid = (matte > 127).astype(np.uint8) * 255
    closed = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, k)
    added = (closed > 0) & (solid == 0)
    matte = np.where(added, 255, matte).astype(np.uint8)
    print("closing filled", int(added.sum()), "px at working size")

    alpha = cv2.resize(matte, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
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
