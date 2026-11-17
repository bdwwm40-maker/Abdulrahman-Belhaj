import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
im = np.asarray(Image.open("assets/character.png").convert("RGB")).astype(float)
dist = np.sqrt(((255 - im) ** 2).sum(-1))           # distance from pure white
near = ndimage.binary_opening(dist < 12, iterations=3)
lab, _ = ndimage.label(near)
border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
bg = np.isin(lab, list(border))
alpha = (~bg).astype(np.uint8) * 255
a = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
out = Image.open("assets/character.png").convert("RGBA"); out.putalpha(a)
out = out.crop(out.getbbox()); out.save("assets/character_cut.png")
prev = Image.new("RGBA", out.size, (40, 10, 70, 255)); prev.alpha_composite(out)
prev.convert("RGB").resize((out.width // 3, out.height // 3)).save("/tmp/claude-0/-home-user-Abdulrahman-Belhaj/aaef3668-8ecd-57ee-b80d-6dfcd1fb9e3a/scratchpad/cut_preview.png")
print(out.size)
