"""Pack the rendered sweep into what the page needs: small WebP frames + hand-frames.js.

Runs under Blender's Python (numpy and WebP are built in, no extra installs):

    D:\\Blender\\blender.exe -b -P blender/pack_hand.py -- [--quality 82] [--in assets/hand/render] [--out assets/hand/frames]

Layers (all cropped to tight boxes, offsets kept in the meta):
  arm    one image: the pixels that never change across the sweep (forearm, wrist, palm heel)
  back   per level: the moving part of the whole-hand pass (fingers, thumb, knuckles)
  front  per level: the folded fingers nearer than the sun (empty levels are skipped)
A level's full back frame == arm + back[level] exactly, because the arm image has the
moving box cleared to transparent.

Output: <out>/arm.webp, back-NN.webp, front-NN.webp, meta.json, and
docs/design/manga-v3/hand-frames.js (window.BLOOD_HAND = {...} with data URLs).
"""
import argparse
import base64
import json
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_rgba(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    a = buf.reshape(h, w, 4)[::-1]          # Blender stores bottom-up
    return a


def bbox(mask):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def save_webp(rgba, path, quality):
    """rgba: float32 HxWx4, top-down, straight alpha in [0,1] (byte-image convention: sRGB values)."""
    h, w = rgba.shape[:2]
    img = bpy.data.images.new("pack_tmp", w, h, alpha=True, float_buffer=False)
    img.alpha_mode = "STRAIGHT"
    img.colorspace_settings.name = "sRGB"
    img.pixels.foreach_set(np.ascontiguousarray(rgba[::-1]).ravel())
    img.file_format = "WEBP"
    img.save(filepath=path, quality=quality)      # a plain save: no view transform on the way out
    bpy.data.images.remove(img)
    # verify the round trip (alpha and colour) against the source
    back = load_rgba(path)
    err = float(np.abs(back - rgba).mean())
    if err > 0.02:
        raise RuntimeError(f"{path}: WebP round-trip error {err:.3f} (colour/alpha handling is off)")
    return os.path.getsize(path)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=os.path.join(ROOT, "assets", "hand", "render"))
    ap.add_argument("--out", default=os.path.join(ROOT, "assets", "hand", "frames"))
    ap.add_argument("--js", default=os.path.join(ROOT, "hand-frames.js"))
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--alpha-min", type=float, default=0.004)
    ap.add_argument("--split-z", type=float, default=None, help="wrist line in R (default: hand.front_mask_z_r from the config)")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    if a.split_z is None:
        with open(os.path.join(HERE, "hand_config.json"), encoding="utf-8") as fh:
            a.split_z = json.load(fh)["hand"].get("front_mask_z_r", -1.9)
    with open(os.path.join(a.inp, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    N = meta["levels"]
    backs = [load_rgba(os.path.join(a.inp, f["back"])) for f in meta["frames"]]
    fronts = [load_rgba(os.path.join(a.inp, f["front"])) for f in meta["frames"]]
    H, W = backs[0].shape[:2]
    assert (W, H) == (meta["w"], meta["h"]), "render size differs from meta"

    # --- split the back pass at the wrist line: below it nothing moves (one image for all levels)
    split = int(round(meta["sun"]["y"] - a.split_z * meta["px_per_r"]))
    lap = 6                                   # the two parts overlap by a few identical rows: no seam
    pad = 6
    arm = backs[0].copy()
    arm[:max(0, split - lap)] = 0
    ab = bbox(arm[..., 3] > a.alpha_min)
    mb = None
    for b in backs:
        top = b.copy()
        top[split + lap:] = 0
        mb = union(mb, bbox(top[..., 3] > a.alpha_min))
    mb = (max(0, mb[0] - pad), max(0, mb[1] - pad), min(W, mb[2] + pad), min(split + lap, mb[3] + pad))
    out = {"px_per_r": meta["px_per_r"], "w": W, "h": H, "sun": meta["sun"], "levels": N, "curl": meta["curl"],
           "model": meta.get("model"), "quality": a.quality, "split_y": split, "arm": None, "back": [], "front": [],
           "front_box": None}
    total = 0
    if ab:
        p = os.path.join(a.out, "arm.webp")
        total += save_webp(arm[ab[1]:ab[3], ab[0]:ab[2]], p, a.quality)
        out["arm"] = {"file": "arm.webp", "x": ab[0], "y": ab[1], "w": ab[2] - ab[0], "h": ab[3] - ab[1]}
    for i, b in enumerate(backs):
        p = os.path.join(a.out, f"back-{i:02d}.webp")
        total += save_webp(b[mb[1]:mb[3], mb[0]:mb[2]], p, a.quality)
        out["back"].append({"file": f"back-{i:02d}.webp", "x": mb[0], "y": mb[1], "w": mb[2] - mb[0], "h": mb[3] - mb[1]})
    # --- the front pass: one shared box over every non-empty level
    def solid(f):
        return (f[..., 3] > 0.05).sum() >= 40           # a few stray pixels are not a frame
    fb = None
    for f in fronts:
        if solid(f):
            fb = union(fb, bbox(f[..., 3] > a.alpha_min))
    if fb:
        fb = (max(0, fb[0] - pad), max(0, fb[1] - pad), min(W, fb[2] + pad), min(H, fb[3] + pad))
        out["front_box"] = {"x": fb[0], "y": fb[1], "w": fb[2] - fb[0], "h": fb[3] - fb[1]}
    for i, f in enumerate(fronts):
        if fb is None or not solid(f):
            out["front"].append(None)
            continue
        p = os.path.join(a.out, f"front-{i:02d}.webp")
        total += save_webp(f[fb[1]:fb[3], fb[0]:fb[2]], p, a.quality)
        out["front"].append({"file": f"front-{i:02d}.webp", "x": fb[0], "y": fb[1], "w": fb[2] - fb[0], "h": fb[3] - fb[1]})
    with open(os.path.join(a.out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    # --- one script the page can embed: the frames as data URLs
    def durl(name):
        with open(os.path.join(a.out, name), "rb") as fh:
            return "data:image/webp;base64," + base64.b64encode(fh.read()).decode("ascii")
    js = dict(out)
    js["arm"] = dict(out["arm"], src=durl(out["arm"]["file"])) if out["arm"] else None
    js["back"] = [dict(e, src=durl(e["file"])) for e in out["back"]]
    js["front"] = [dict(e, src=durl(e["file"])) if e else None for e in out["front"]]
    with open(a.js, "w", encoding="utf-8") as fh:
        fh.write("/* Blood - the God Hand, pre-rendered in Blender (see blender/hand_scene.py). Generated by pack_hand.py. */\n")
        fh.write("window.BLOOD_HAND = " + json.dumps(js, separators=(",", ":")) + ";\n")
    print(f"packed {N} levels: webp total {total / 1024:.0f} KB, js {os.path.getsize(a.js) / 1024:.0f} KB, "
          f"split row {split}, hand box {mb}, front box {fb}, arm box {ab}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(argv)
