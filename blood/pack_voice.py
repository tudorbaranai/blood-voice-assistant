"""Split your recorded wake-word clips into a training part and a held-back test part.

Every 4th clip of each spot is held back (listed in models\\my_voice\\holdout.json)
and never used for training: it's the honest exam for the finished model,
because a model can memorise clips it trained on. The rest goes into
models\\my_voice_train.zip, which you upload to Colab for colab_train_v3.sh.

Usage (after record_wake.py):
    .venv\\Scripts\\python.exe blood\\pack_voice.py
Then test any model on the held-back clips:
    .venv\\Scripts\\python.exe blood\\wake_eval.py --model models\\hey_blood_v3.onnx --holdout
"""
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOICE = ROOT / "models" / "my_voice"
SPOTS = ["desk", "bed", "far", "talk"]


def main():
    holdout, train = [], []
    for spot in SPOTS:
        clips = sorted((VOICE / spot).glob("*.wav"))
        for i, f in enumerate(clips):
            (holdout if i % 4 == 3 else train).append(f"{spot}/{f.name}")
    if not train:
        raise SystemExit("No recordings found. Run blood\\record_wake.py first.")

    (VOICE / "holdout.json").write_text(json.dumps(holdout, indent=1))
    with zipfile.ZipFile(ROOT / "models" / "my_voice_train.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name in train:
            z.write(VOICE / name, name)
    for spot in SPOTS:
        n_train = sum(n.startswith(spot + "/") for n in train)
        n_test = sum(n.startswith(spot + "/") for n in holdout)
        print(f"{spot:5}  training {n_train:3}   held back {n_test:3}")
    print(f"\nUpload to Colab: {ROOT / 'models' / 'my_voice_train.zip'}")


if __name__ == "__main__":
    main()
