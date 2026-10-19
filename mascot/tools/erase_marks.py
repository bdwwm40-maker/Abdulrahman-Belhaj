"""Erase small letter-like marks the image model drew inside embroidery scrolls.

Each mark is given by hand as an ellipse (the plain cloth at the centre of a
scroll curl, where the stray glyphs sit). The ellipse is inpainted from the
surrounding cloth and the fabric grain is put back, as in remove_outline.py,
so the curl reads as clean embroidery with a plain centre.

usage:
  python3 erase_marks.py IN.png OUT.png --ellipse CX CY RX RY [--ellipse ...] [--debug DEBUG.png]
"""
import argparse
import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--ellipse", type=int, nargs=4, action="append", required=True,
                    metavar=("CX", "CY", "RX", "RY"))
    ap.add_argument("--debug")
    a = ap.parse_args()

    img = cv2.imread(a.src)
    mask = np.zeros(img.shape[:2], np.uint8)
    for cx, cy, rx, ry in a.ellipse:
        cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)

    filled = cv2.inpaint(img, mask, 6, cv2.INPAINT_TELEA).astype(np.float32)
    hp = img.astype(np.float32) - cv2.GaussianBlur(img, (0, 0), 2.5).astype(np.float32)
    grain = np.roll(hp, shift=(0, 40), axis=(0, 1))  # cloth grain from just beside the mark
    m = cv2.GaussianBlur(mask, (0, 0), 2.0).astype(np.float32)[..., None] / 255.0
    out = img.astype(np.float32) * (1 - m) + (filled + grain * 0.7) * m
    cv2.imwrite(a.out, np.clip(out, 0, 255).astype(np.uint8))

    if a.debug:
        dbg = img.copy()
        cnt, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(dbg, cnt, -1, (0, 0, 255), 1)
        cv2.imwrite(a.debug, dbg)
    print("erased", len(a.ellipse), "marks")


if __name__ == "__main__":
    main()
