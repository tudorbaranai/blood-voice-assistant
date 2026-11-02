#!/bin/bash
# Retrain "hey blood" again, this time with the real voice clips CUT so the
# phrase ends right at the end of each clip (openWakeWord assumes that: it
# labels the END of a clip as "the wake word"). v2 skipped this and learned the
# silence after the phrase instead.
# Run in the same Colab runtime after colab_train_v2.sh (reuses its synthetic
# clips, config and the uploaded my_voice_train.zip):
#   nohup bash colab_train_v3.sh > v3.log 2>&1 &
set -e
cd /content
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
D=my_custom_model/hey_blood_v2

echo "== [1/4] remove the badly cut real clips from v2"
rm -f $D/positive_train/real_* $D/negative_train/real_*
rm -rf my_voice && unzip -o -q my_voice_train.zip -d my_voice

echo "== [2/4] cut each real clip so it ends 0.15 s after the phrase, copy 15x"
python - <<'PY'
import pathlib, shutil, wave
import numpy as np

SR, FRAME = 16000, 320          # 20 ms energy frames

def phrase_end(a):
    """End of the loud part around the loudest moment (quiet for 100 ms after).
    Checked on the laptop: v1 fires 0.26 s (+-0.06) after this point."""
    f = a.astype(float)
    e = np.array([np.sqrt(np.mean(f[i:i + FRAME] ** 2)) for i in range(0, len(f) - FRAME, FRAME)])
    j = pk = int(np.argmax(e))
    while j < len(e) - 5 and not all(e[j:j + 5] < e[pk] * 0.10):
        j += 1
    return (j + 1) * FRAME

D = pathlib.Path("my_custom_model/hey_blood_v2")
for spot in ["desk", "bed", "far"]:
    for f in sorted(pathlib.Path("my_voice", spot).glob("*.wav")):
        with wave.open(str(f)) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        end = phrase_end(a)
        cut = a[max(0, end - int(1.3 * SR)):min(len(a), end + int(0.15 * SR))]
        for r in range(1, 16):
            with wave.open(str(D / "positive_train" / f"real_{spot}_{r}_{f.name}"), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(cut.tobytes())
for f in sorted(pathlib.Path("my_voice", "talk").glob("*.wav")):
    for r in range(1, 16):
        shutil.copy(f, D / "negative_train" / f"real_talk_{r}_{f.name}")
PY
echo "positive_train: $(ls $D/positive_train | wc -l)  negative_train: $(ls $D/negative_train | wc -l)"

echo "== [3/4] augment (noise + echo) and compute features"
rm -f $D/*_features_*.npy
python openwakeword/openwakeword/train.py --training_config v2.yaml --augment_clips 2>&1 | grep -v -E "DEBUG|Warning|warn" | tail -8

echo "== [4/4] train"
python openwakeword/openwakeword/train.py --training_config v2.yaml --train_model 2>&1 | grep -v -E "DEBUG|Warning|warn|onnx_ir|onnxscript" | tail -12 || true
python -c "import onnx; m=onnx.load('my_custom_model/hey_blood_v2.onnx'); onnx.save(m,'hey_blood_v3.onnx'); print('MERGED')"
ls -la hey_blood_v3.onnx
echo "ALL DONE"
