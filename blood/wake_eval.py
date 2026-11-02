"""Score your recorded clips with a wake-word model: hits per spot, false alarms.

Uses the clips from record_wake.py (models\\my_voice\\<spot>\\). Tries several
settings at once (threshold, software gain) so we can pick the best by numbers.

Usage:
    .venv\\Scripts\\python.exe blood\\wake_eval.py
    .venv\\Scripts\\python.exe blood\\wake_eval.py --model models\\hey_blood.onnx --verifier models\\hey_blood_verifier.pkl
    .venv\\Scripts\\python.exe blood\\wake_eval.py --model models\\hey_blood_v2.onnx --holdout
"""
import argparse
import json
import pathlib
import wave

import numpy as np
from openwakeword.model import Model

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOICE = ROOT / "models" / "my_voice"
CHUNK = 1280


def load(path):
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def peak_score(model, name, audio, gain):
    model.reset()
    audio = np.clip(audio.astype(np.float64) * gain, -32768, 32767).astype(np.int16)
    # half a second of silence first, so the model "settles" like in live listening
    audio = np.concatenate([np.zeros(8000, dtype=np.int16), audio, np.zeros(8000, dtype=np.int16)])
    best = 0.0
    for i in range(0, len(audio) - CHUNK + 1, CHUNK):
        best = max(best, model.predict(audio[i:i + CHUNK])[name])
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "models" / "hey_blood.onnx"))
    ap.add_argument("--verifier", default=None, help="custom verifier .pkl (optional)")
    ap.add_argument("--verifier-threshold", type=float, default=0.3)
    ap.add_argument("--holdout", action="store_true",
                    help="score only the clips in my_voice\\holdout.json (never used for training)")
    a = ap.parse_args()
    keep = None
    if a.holdout:
        keep = set(json.loads((VOICE / "holdout.json").read_text()))

    kw = {"wakeword_models": [a.model], "inference_framework": "onnx"}
    if a.verifier:
        kw["custom_verifier_models"] = {pathlib.Path(a.model).stem: a.verifier}
        kw["custom_verifier_threshold"] = a.verifier_threshold
    model = Model(**kw)
    name = list(model.models)[0]

    spots = [s for s in ["desk", "bed", "far", "talk"] if (VOICE / s).exists()]
    if not spots:
        raise SystemExit("No recordings yet. Run blood\\record_wake.py first.")
    print(f"Model: {name}" + (f"  + verifier {pathlib.Path(a.verifier).name}" if a.verifier else ""))

    clips = {s: [f for f in sorted((VOICE / s).glob("*.wav")) if keep is None or f"{s}/{f.name}" in keep]
             for s in spots}
    if keep is not None:
        print("Holdout clips only (the model never heard these).")
    for gain in (1, 3, 6):
        scores = {s: [peak_score(model, name, load(f), gain) for f in fs] for s, fs in clips.items()}
        print(f"\n== software gain x{gain} ==")
        print("  peaks per spot: " + "  ".join(f"{s}: median {np.median(v):.2f}" for s, v in scores.items()))
        for th in (0.1, 0.2, 0.3, 0.5):
            cells = []
            for s, v in scores.items():
                hit = sum(x >= th for x in v)
                cells.append(f"{s} {'false' if s == 'talk' else 'hits'} {hit}/{len(v)}")
            print(f"  threshold {th:.1f}:  " + "   ".join(cells))


if __name__ == "__main__":
    main()
