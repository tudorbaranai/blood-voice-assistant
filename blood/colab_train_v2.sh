#!/bin/bash
# !! Superseded by colab_train_v3.sh. Kept as a record: this version mixes the
# !! recordings in UNCUT, which made the model worse than v1 (docs/tutorial/09).
# Retrain "hey blood" on Google Colab with the owner's real voice mixed in.
# Run AFTER the notebook's step 1 + step 2 (and their fixes) have finished,
# and after my_voice_train.zip was uploaded to /content.
#   nohup bash colab_train_v2.sh > v2.log 2>&1 &
set -e
cd /content
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
echo "== [1/7] patch torch_audiomentations for new torchaudio"
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

echo "== [2/7] write training config"
python - <<'PY'
import yaml
c = yaml.safe_load(open("openwakeword/examples/custom_model.yml"))
c.update({
    "target_phrase": ["hey blood"], "model_name": "hey_blood_v2",
    "n_samples": 30000, "n_samples_val": 3000, "steps": 30000,
    "target_accuracy": 0.5, "target_recall": 0.25,
    "output_dir": "./my_custom_model", "max_negative_weight": 1000,
    "background_paths": ["./audioset_16k", "./fma"],
    "false_positive_validation_data_path": "validation_set_features.npy",
    "feature_data_files": {"ACAV100M_sample": "openwakeword_features_ACAV100M_2000_hrs_16bit.npy"},
})
yaml.dump(c, open("v2.yaml", "w"))
print(c)
PY

echo "== [3/7] generate synthetic clips"
python openwakeword/openwakeword/train.py --training_config v2.yaml --generate_clips 2>&1 | grep -v DEBUG | tail -5

echo "== [4/7] mix in the real voice clips (each copied 15x; every copy gets different noise/echo)"
rm -rf my_voice && unzip -o -q my_voice_train.zip -d my_voice
D=my_custom_model/hey_blood_v2
for r in $(seq 1 15); do
  for s in desk bed far; do
    for f in my_voice/$s/*.wav; do cp "$f" "$D/positive_train/real_${s}_${r}_$(basename "$f")"; done
  done
  for f in my_voice/talk/*.wav; do cp "$f" "$D/negative_train/real_talk_${r}_$(basename "$f")"; done
done
echo "positive_train: $(ls $D/positive_train | wc -l)  negative_train: $(ls $D/negative_train | wc -l)"

echo "== [5/7] augment (noise + echo) and compute features"
rm -f $D/*_features_*.npy
python openwakeword/openwakeword/train.py --training_config v2.yaml --augment_clips 2>&1 | grep -v -E "DEBUG|Warning|warn" | tail -8

echo "== [6/7] train"
python openwakeword/openwakeword/train.py --training_config v2.yaml --train_model 2>&1 | grep -v -E "DEBUG|Warning|warn|onnx_ir|onnxscript" | tail -12 || true

echo "== [7/7] merge model into one file and pack"
python -c "import onnx; m=onnx.load('my_custom_model/hey_blood_v2.onnx'); onnx.save(m,'hey_blood_v2.onnx'); print('MERGED')"
ls -la hey_blood_v2.onnx
echo "ALL DONE"
