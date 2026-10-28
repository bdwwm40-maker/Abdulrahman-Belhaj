"""Face rig for the mascot on top of LivePortrait (KwaiVGI, MIT licence), run on CPU.

LivePortrait re-renders a portrait from implicit 3D keypoints. Offsetting the
keypoint expression deltas gives direct face controls - the same offsets as the
expression editor of ComfyUI-AdvancedLivePortrait: mouth open (aaa), spread (eee),
round (woo), smile, blink, brows, pupils, head rotation - and the lip retargeting
network closes the lips for b / m / f.

A full render costs ~5-10 s per frame on CPU, so instead of rendering every frame
this builds a library once: a mouth grid (open x shape), three lip closures and an
eye grid (blink x brow), all with the same head pose. face_frames.py interpolates
the library per frame.

The LivePortrait code and weights are fetched from the Hugging Face space
"KwaiVGI/LivePortrait" (src/ + pretrained_weights/), see README.

usage: python3 face_rig.py LP_DIR [--image ../mascot/final/mascot-cutout.png] [--out build/face-lib.npz]
       python3 face_rig.py LP_DIR --grid preview.jpg     # sheet of single controls
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OPEN = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
SHAPE = [-1.0, -0.5, 0.0, 0.5, 1.0]          # -1 round (woo 14) ... +1 spread (eee 12)
CLOSE = [0.35, 0.7, 1.0]
BLINK = [0, -5, -10, -15, -20]
BROW = [0, 5, 10]


class Rig:
    def __init__(self, lp, crop256, lip_ratio, threads=4):
        sys.path.insert(0, str(lp))
        from src.modules.appearance_feature_extractor import AppearanceFeatureExtractor
        from src.modules.motion_extractor import MotionExtractor
        from src.modules.warping_network import WarpingNetwork
        from src.modules.spade_generator import SPADEDecoder
        from src.modules.stitching_retargeting_network import StitchingRetargetingNetwork
        from src.utils.camera import headpose_pred_to_degree, get_rotation_matrix
        self.rot = get_rotation_matrix
        torch.set_num_threads(threads)
        cfg = yaml.safe_load(open(f"{lp}/src/config/models.yaml"))["model_params"]
        w = f"{lp}/pretrained_weights/liveportrait"

        def load(cls, key, path):
            m = cls(**cfg[f"{key}_params"])
            m.load_state_dict(torch.load(path, map_location="cpu"))
            return m.eval()

        self.F = load(AppearanceFeatureExtractor, "appearance_feature_extractor", f"{w}/base_models/appearance_feature_extractor.pth")
        self.M = load(MotionExtractor, "motion_extractor", f"{w}/base_models/motion_extractor.pth")
        self.W = load(WarpingNetwork, "warping_module", f"{w}/base_models/warping_module.pth")
        self.G = load(SPADEDecoder, "spade_generator", f"{w}/base_models/spade_generator.pth")
        ck = torch.load(f"{w}/retargeting_models/stitching_retargeting_module.pth", map_location="cpu")
        sr = cfg["stitching_retargeting_module_params"]

        def net(key, part):
            m = StitchingRetargetingNetwork(**sr[key])
            m.load_state_dict({k.replace("module.", ""): v for k, v in ck[part].items()})
            return m.eval()

        self.S, self.L = net("stitching", "retarget_shoulder"), net("lip", "retarget_mouth")
        self.lip_ratio = lip_ratio

        x = torch.from_numpy(crop256.astype(np.float32) / 255).permute(2, 0, 1)[None]
        with torch.no_grad():
            self.fs = self.F(x)
            info = self.M(x)
        for k in ("pitch", "yaw", "roll"):
            info[k] = headpose_pred_to_degree(info[k])[:, None]
        info["kp"] = info["kp"].reshape(1, -1, 3)
        info["exp"] = info["exp"].reshape(1, -1, 3)
        self.info = info
        self.xs = self._kp(0, 0, 0, info["exp"])

    def _kp(self, dp, dy, dr, exp):
        i = self.info
        R = self.rot(i["pitch"] + dp, i["yaw"] + dy, i["roll"] + dr)
        x = i["scale"][..., None] * (i["kp"] @ R + exp)
        x[:, :, 0:2] += i["t"][:, None, 0:2]
        return x

    @staticmethod
    def edit(e, eyes=0., eyebrow=0., wink=0., pupil_x=0., pupil_y=0., aaa=0., eee=0., woo=0., smile=0.,
             pitch=0., yaw=0., roll=0.):
        """Expression offsets on the keypoint deltas; returns the head rotation offsets (degrees).
        The jaw-coupled nod of the original editor is left out so all layers share one head pose."""
        e[0, 20, 1] += smile * -0.01
        e[0, 14, 1] += smile * -0.02
        e[0, 17, 1] += smile * 0.0065
        e[0, 17, 2] += smile * 0.003
        e[0, 13, 1] += smile * -0.00275
        e[0, 16, 1] += smile * -0.00275
        e[0, 3, 1] += smile * -0.0035
        e[0, 7, 1] += smile * -0.0035
        e[0, 19, 1] += aaa * 0.001
        e[0, 19, 2] += aaa * 0.0001
        e[0, 17, 1] += aaa * -0.0001
        e[0, 20, 2] += eee * -0.001
        e[0, 20, 1] += eee * -0.001
        e[0, 14, 1] += eee * -0.001
        e[0, 14, 1] += woo * 0.001
        e[0, 3, 1] += woo * -0.0005
        e[0, 7, 1] += woo * -0.0005
        e[0, 17, 2] += woo * -0.0005
        e[0, 11, 1] += wink * 0.001
        e[0, 13, 1] += wink * -0.0003
        e[0, 17, 0] += wink * 0.0003
        e[0, 17, 1] += wink * 0.0003
        e[0, 3, 1] += wink * -0.0003
        roll -= wink * 0.1
        yaw -= wink * 0.1
        if pupil_x > 0:
            e[0, 11, 0] += pupil_x * 0.0007
            e[0, 15, 0] += pupil_x * 0.001
        else:
            e[0, 11, 0] += pupil_x * 0.001
            e[0, 15, 0] += pupil_x * 0.0007
        e[0, 11, 1] += pupil_y * -0.001
        e[0, 15, 1] += pupil_y * -0.001
        eyes -= pupil_y / 2.
        e[0, 11, 1] += eyes * -0.001
        e[0, 13, 1] += eyes * 0.0003
        e[0, 15, 1] += eyes * -0.001
        e[0, 16, 1] += eyes * 0.0003
        e[0, 1, 1] += eyes * -0.00025
        e[0, 2, 1] += eyes * 0.00025
        if eyebrow > 0:
            e[0, 1, 1] += eyebrow * 0.001
            e[0, 2, 1] += eyebrow * -0.001
        else:
            e[0, 1, 0] += eyebrow * -0.001
            e[0, 2, 0] += eyebrow * 0.001
            e[0, 1, 1] += eyebrow * 0.0003
            e[0, 2, 1] += eyebrow * -0.0003
        return pitch, yaw, roll

    def render(self, lip_close=0.0, **c):
        """512x512 RGB crop for the given controls; lip_close in [0,1] closes the lips."""
        e = self.info["exp"].clone()
        p, y, r = self.edit(e, **c)
        xd = self._kp(p, -y, r, e)
        with torch.no_grad():
            if lip_close > 0:
                ratio = torch.tensor([[self.lip_ratio, self.lip_ratio * (1 - lip_close)]], dtype=torch.float32)
                xd = xd + self.L(torch.cat([self.xs.view(1, -1), ratio], 1)).reshape(1, -1, 3)
            n = xd.shape[1]
            d = self.S(torch.cat([self.xs.view(1, -1), xd.view(1, -1)], 1))
            xd = xd + d[..., :3 * n].reshape(1, n, 3)
            xd[..., :2] += d[..., 3 * n:3 * n + 2].reshape(1, 1, 2)
            img = self.G(feature=self.W(self.fs, kp_source=self.xs, kp_driving=xd)["out"])
        return (img[0].permute(1, 2, 0).clamp(0, 1).numpy() * 255).astype(np.uint8)


def detect(lp, rgba):
    """Face crop (512, LivePortrait framing) of the cutout and its crop->image transform."""
    sys.path.insert(0, str(lp))
    from src.utils.face_analysis_diy import FaceAnalysisDIY
    from src.utils.landmark_runner import LandmarkRunner
    from src.utils.crop import crop_image
    from src.utils.retargeting_utils import calc_lip_close_ratio
    a = rgba[..., 3:].astype(np.float32) / 255
    rgb = (rgba[..., :3] * a + 235 * (1 - a)).astype(np.uint8)        # light grey behind the cutout
    fa = FaceAnalysisDIY(name="buffalo_l", root=f"{lp}/pretrained_weights/insightface", providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(512, 512))
    # look in the head area (top of the figure) so the face is large enough for the 512 detector
    ys, xs = np.nonzero(rgba[..., 3] > 128)
    top, h = ys.min(), ys.max() - ys.min()
    x0, x1 = max(0, xs.min() - h // 10), xs.max() + h // 10
    head = rgb[max(0, top - h // 20):top + int(h * 0.4), x0:x1].copy()
    faces = fa.get(head, flag_do_landmark_2d_106=True, direction="large-small")
    if not faces:
        sys.exit("no face found")
    pts = faces[0].landmark_2d_106 + np.array([x0, max(0, top - h // 20)])
    lr = LandmarkRunner(ckpt_path=f"{lp}/pretrained_weights/liveportrait/landmark.onnx", onnx_provider="cpu", device_id=0)
    lmk = lr.run(rgb, pts)["pts"]
    crop = crop_image(rgb, lmk, dsize=512, scale=2.3, vy_ratio=-0.125)
    return crop["img_crop"], crop["M_c2o"], float(calc_lip_close_ratio(lmk[None])[0, 0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lp", help="LivePortrait folder (src/ + pretrained_weights/)")
    ap.add_argument("--image", default=str(ROOT.parent / "mascot" / "final" / "mascot-cutout.png"))
    ap.add_argument("--out", default=str(ROOT / "build" / "face-lib.npz"))
    ap.add_argument("--grid", help="only write a preview sheet of single controls")
    a = ap.parse_args()

    crop, M, lip = detect(a.lp, np.array(Image.open(a.image).convert("RGBA")))
    rig = Rig(a.lp, np.array(Image.fromarray(crop).resize((256, 256), Image.LANCZOS)), lip)
    t0 = time.time()
    if a.grid:
        ctl = [{}, dict(aaa=60), dict(aaa=100), dict(eee=12), dict(woo=14), dict(lip_close=1.0),
               dict(eyes=-20), dict(eyebrow=10)]
        tiles = [Image.fromarray(rig.render(**c)).crop((96, 100, 416, 450)) for c in ctl]
        sheet = Image.new("RGB", (320 * 4, 350 * 2))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 4) * 320, (i // 4) * 350))
        sheet.save(a.grid, quality=90)
        return

    def mouth_ctrl(o, s):
        return dict(aaa=o, woo=-s * 14 if s < 0 else 0.0, eee=s * 12 if s > 0 else 0.0)

    neutral = rig.render()
    mouth = np.zeros((len(OPEN), len(SHAPE), 512, 512, 3), np.uint8)
    for i, o in enumerate(OPEN):
        for j, s in enumerate(SHAPE):
            mouth[i, j] = neutral if (o == 0 and s == 0) else rig.render(**mouth_ctrl(o, s))
        print(f"mouth open {o}  {time.time() - t0:.0f}s", flush=True)
    close = np.stack([rig.render(lip_close=c) for c in CLOSE])
    eyes = np.zeros((len(BLINK), len(BROW), 512, 512, 3), np.uint8)
    for i, b in enumerate(BLINK):
        for j, w in enumerate(BROW):
            eyes[i, j] = neutral if (b == 0 and w == 0) else rig.render(eyes=b, eyebrow=w)
    print(f"library done {time.time() - t0:.0f}s")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(a.out, neutral=neutral, mouth=mouth, close=close, eyes=eyes, crop=crop, M_c2o=M,
             OPEN=OPEN, SHAPE=SHAPE, CLOSE=CLOSE, BLINK=BLINK, BROW=BROW)


if __name__ == "__main__":
    main()
