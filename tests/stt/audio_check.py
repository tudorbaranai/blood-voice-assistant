"""Check how loud and how clean each recording is.

For every WAV file it prints:
  voice level   how loud your voice is (dBFS: 0 = maximum, -20 = good, -40 = very quiet)
  noise level   how loud the background is when you're not speaking (fan, room)
  clarity       voice minus noise, in dB (higher = cleaner; 20+ good, 10-20 okay, under 10 hard)

Usage:
    python audio_check.py               check the main recordings
    python audio_check.py mic-test-a    check another folder
"""
import pathlib
import sys
import wave

import numpy as np

HERE = pathlib.Path(__file__).parent
FRAME = 400  # 25 ms at 16 kHz


def db(x):
    return 20 * np.log10(max(x, 1e-9))


def analyse(path):
    with wave.open(str(path), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    frames = audio[: len(audio) // FRAME * FRAME].reshape(-1, FRAME)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    noise = np.percentile(rms, 10)   # quietest moments = background
    voice = np.percentile(rms, 95)   # loudest moments = your voice
    peak = np.abs(audio).max()
    return db(voice), db(noise), db(voice) - db(noise), db(peak)


def main():
    folder = HERE / (sys.argv[1] if len(sys.argv) > 1 else "recordings")
    print(f"Folder: {folder.name}")
    print(f"{'file':8} {'voice level':>12} {'noise level':>12} {'clarity':>9} {'peak':>7}")
    for path in sorted(folder.glob("*.wav")):
        voice, noise, clarity, peak = analyse(path)
        verdict = "good" if clarity >= 20 else "okay" if clarity >= 10 else "HARD"
        clip = "  CLIPPED" if peak > -0.5 else ""
        print(f"{path.name:8} {voice:9.1f} dB {noise:9.1f} dB {clarity:6.1f} dB {peak:6.1f}  {verdict}{clip}")


if __name__ == "__main__":
    main()
