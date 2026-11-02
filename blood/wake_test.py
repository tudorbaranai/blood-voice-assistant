"""Wake-word test: does the mic hear the wake word, and how sure is it?

Say the wake word a few times: at the desk, from the bed, from across the room,
with music or a video playing. For EVERY attempt it prints the peak score
(0 = no, 1 = certain), so you can see near-misses too, not only the hits.
Also watch for detections when you DIDN'T say it.

Usage:
    .venv\\Scripts\\python.exe blood\\wake_test.py --model models\\hey_blood.onnx
    ... --threshold 0.3                   accept weaker matches
    ... --gain 4                          boost the mic volume 4x in software
    ... --auto-gain                       boost quiet (far-away) speech automatically
    ... --list                            show microphones
    ... --mic 3                           use microphone number 3
Stop with Ctrl+C.
"""
import argparse
import time

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

RATE = 16000          # openWakeWord expects 16 kHz mono audio
CHUNK = 1280          # 80 ms per piece, the size openWakeWord works in


class AutoGain:
    """Raise quiet sound towards a target level, smoothly, never clipping.

    Far-away speech reaches the laptop mic very quietly. This brings it up to a
    normal level before the wake-word model listens, like turning up the volume
    only when someone is far away.
    """

    def __init__(self, target_rms=3000, max_gain=8.0):
        self.target, self.max_gain, self.gain = target_rms, max_gain, 1.0

    def __call__(self, audio):
        rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) + 1e-6
        wanted = min(self.max_gain, max(1.0, self.target / rms)) if rms > 150 else self.gain
        self.gain = 0.9 * self.gain + 0.1 * wanted          # change smoothly
        return np.clip(audio * self.gain, -32768, 32767).astype(np.int16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="hey_jarvis", help="wake-word model name or path to a .onnx file")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--gain", type=float, default=1.0, help="fixed software volume boost")
    ap.add_argument("--auto-gain", action="store_true", help="boost quiet speech automatically")
    ap.add_argument("--mic", type=int, default=None)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                print(f"{i:3}  {d['name']}  ({d['hostapi']})")
        return

    model = Model(wakeword_models=[a.model], inference_framework="onnx")
    name = list(model.models.keys())[0]
    mic = sd.query_devices(a.mic, "input")["name"]
    agc = AutoGain() if a.auto_gain else None
    print(f"Listening for '{name}' on: {mic}")
    print(f"Threshold {a.threshold}, gain {'auto' if agc else a.gain}. Say the wake word. Ctrl+C to stop.\n")

    attempt, peak, hits, attempts = False, 0.0, 0, 0
    last_hit = 0.0
    with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=CHUNK, device=a.mic) as stream:
        while True:
            audio, _ = stream.read(CHUNK)
            audio = audio[:, 0]
            if agc:
                audio = agc(audio)
            elif a.gain != 1.0:
                audio = np.clip(audio.astype(np.float64) * a.gain, -32768, 32767).astype(np.int16)
            score = model.predict(audio)[name]
            level = int(np.abs(audio).mean() / 300)
            print(f"\r  mic {'#' * min(level, 30):30}  score {score:4.2f}  ", end="", flush=True)

            now = time.time()
            if score >= a.threshold and now - last_hit > 1.0:
                hits += 1
                last_hit = now
                print(f"\n>>> HEARD IT ({hits})  score {score:.2f}  at {time.strftime('%H:%M:%S')}")
            # Track every attempt (any bump above 0.05) and report its peak when it ends
            if score > 0.05:
                attempt, peak = True, max(peak, score)
            elif attempt:
                attempts += 1
                verdict = "HIT " if peak >= a.threshold else "miss"
                print(f"\n    attempt {attempts}: peak {peak:.2f}  ({verdict} at threshold {a.threshold})")
                attempt, peak = False, 0.0


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
