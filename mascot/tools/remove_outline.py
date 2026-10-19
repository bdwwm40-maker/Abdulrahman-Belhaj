"""Erase a faint rectangular outline the image model left on the fabric.

Inpaints a thin band along the rectangle's four edges, then puts the fabric's
own grain back on the repaired pixels (copied from cloth just beside the band)
so the repair does not read as a smooth smear.

usage:
  python3 remove_outline.py IN.png OUT.png --rect X0 Y0 X1 Y1 [--band 5]
"""
import argparse
import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--rect", type=int, nargs=4, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--band", type=int, default=5, help="half-thickness of the repaired band in px")
    a = ap.parse_args()

    img = cv2.imread(a.src)
    x0, y0, x1, y1 = a.rect
    b = a.band
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.rectangle(mask, (x0, y0), (x1, y1), 255, thickness=2 * b + 1)

    filled = cv2.inpaint(img, mask, 7, cv2.INPAINT_TELEA)

    # restore grain: high-pass of the cloth 3*b px further out, shifted onto the band
    hp = img.astype(np.float32) - cv2.GaussianBlur(img, (0, 0), 2.5).astype(np.float32)
    shift = 3 * b
    grain = np.roll(hp, shift=(shift, shift), axis=(0, 1))
    out = filled.astype(np.float32)
    m = cv2.GaussianBlur(mask, (0, 0), 1.2).astype(np.float32)[..., None] / 255.0
    out = out + grain * m
    out = img.astype(np.float32) * (1 - m) + out * m
    cv2.imwrite(a.out, np.clip(out, 0, 255).astype(np.uint8))
    print("repaired outline", a.rect)


if __name__ == "__main__":
    main()
