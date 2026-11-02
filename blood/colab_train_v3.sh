#!/bin/bash
# Train "hey blood" on Google Colab: computer voices + your own recordings.
# Each of your clips is CUT so it ends 0.15 s after the phrase: openWakeWord
# labels the END of a clip as "the wake word". v2 skipped the cut and learned
# the silence after the phrase instead (worse than v1, see docs/tutorial/09).
#
# Before: run the notebook's step 1 and step 2 with the fixes from
# docs/tutorial/09 (Part 1), and upload two files to /content (the folder
# panel on the left): this script and my_voice_train.zip (from blood/pack_voice.py).
# Then run it in the background and look at the log now and then:
#   !nohup bash colab_train_v3.sh > v3.log 2>&1 &
#   !tail -5 v3.log
# About 2 hours on a T4. Result: /content/hey_blood_v3.onnx (one file, ready to download).
set -e
cd /content
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
NAME=hey_blood_v3
D=my_custom_model/$NAME

echo "== [1/6] patch torch_audiomentations for new torchaudio"
python - <<'PY'
import os, importlib.util
# find the file WITHOUT importing the library (importing it is what crashes)
p = os.path.join(importlib.util.find_spec("torch_audiomentations").submodule_search_locations[0], "utils", "io.py")
s = open(p).read()
s = s.replace('torchaudio.set_audio_backend("soundfile")', "pass")
s = s.replace("torchaudio.info(file_path)",
              "__import__('types').SimpleNamespace(num_frames=__import__('soundfile').info(str(file_path)).frames,"
              " sample_rate=__import__('soundfile').info(str(file_path)).samplerate)")
open(p, "w").write(s)
print("patched", p)
PY

echo "== [2/6] write training config"
python - <<'PY'
import yaml
c = yaml.safe_load(open("openwakeword/examples/custom_model.yml"))
c.update({
    "target_phrase": ["hey blood"], "model_name": "hey_blood_v3",
    "n_samples": 30000, "n_samples_val": 3000, "steps": 30000,
    "target_accuracy": 0.5, "target_recall": 0.25,
    "output_dir": "./my_custom_model", "max_negative_weight": 1000,
    "background_paths": ["./audioset_16k", "./fma"],
    "false_positive_validation_data_path": "validation_set_features.npy",
    "feature_data_files": {"ACAV100M_sample": "openwakeword_features_ACAV100M_2000_hrs_16bit.npy"},
})
yaml.dump(c, open("v3.yaml", "w"))
print(c)
PY

echo "== [3/6] computer voices (skipped if they already exist)"
python openwakeword/openwakeword/train.py --training_config v3.yaml --generate_clips 2>&1 | grep -v DEBUG | tail -5

echo "== [4/6] cut each of your clips so it ends 0.15 s after the phrase, copy 15x"
rm -f $D/positive_train/real_* $D/negative_train/real_*
rm -rf my_voice && unzip -o -q my_voice_train.zip -d my_voice
D=$D python - <<'PY'
import os, pathlib, shutil, wave
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

D = pathlib.Path(os.environ["D"])
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

echo "== [5/6] augment (noise + echo) and compute features"
rm -f $D/*_features_*.npy
python openwakeword/openwakeword/train.py --training_config v3.yaml --augment_clips 2>&1 | grep -v -E "DEBUG|Warning|warn" | tail -8

echo "== [6/6] train, then merge the model into one file"
python openwakeword/openwakeword/train.py --training_config v3.yaml --train_model 2>&1 | grep -v -E "DEBUG|Warning|warn|onnx_ir|onnxscript" | tail -12 || true
python -c "import onnx; m=onnx.load('my_custom_model/hey_blood_v3.onnx'); onnx.save(m,'hey_blood_v3.onnx'); print('MERGED')"
ls -la hey_blood_v3.onnx
echo "ALL DONE"
