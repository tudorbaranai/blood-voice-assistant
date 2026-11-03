"""Background entry point: render the God Hand without touching the live Blender.

    D:\\Blender\\blender.exe -b assets/hand/hand.blend -P blender/render_hand.py -- --pose-tests
    D:\\Blender\\blender.exe -b assets/hand/hand.blend -P blender/render_hand.py -- --sweep [--levels 24]

Without a saved .blend (fresh): add --build to rebuild the scene from hand_config.json first.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hand_scene as hs  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="rebuild the scene from the config before rendering")
    ap.add_argument("--pose-tests", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--levels", type=int, default=None)
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--save", action="store_true", help="save the .blend after building")
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.build or hs.scene() is None:
        hs.build()
        hs.load_hand()
        hs.pose(0.0)
        if a.save:
            print("saved", hs.save_blend())
    sc = hs.scene()
    sc.cycles.device = "GPU" if hs._gpu() else "CPU"
    print("render device:", sc.cycles.device)
    if a.samples:
        sc.cycles.samples = a.samples
    if a.pose_tests:
        for p in hs.render_pose_tests():
            print("still", p)
    if a.sweep:
        meta = hs.render_sweep(levels=a.levels)
        print("sweep done:", meta["levels"], "levels, sun", meta["sun"])
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(argv)
