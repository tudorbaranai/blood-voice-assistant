"""Record your own wake-word clips, hands-free.

Stand (or lie) at a spot, start the script, and after every BEEP say the wake
word once, the way you normally would. It records a short window after each
beep and saves it as a 16 kHz mono WAV (the format openWakeWord uses).

Spots:
    desk   next to the laptop
    bed    from the bed
    far    across the room
    talk   NOT the wake word: just talk normally (or say look-alike phrases such
           as "hey bud", "hey love", "a blood", "hey Johnny"), one phrase per beep

Usage:
    .venv\\Scripts\\python.exe blood\\record_wake.py desk
    .venv\\Scripts\\python.exe blood\\record_wake.py bed --count 10
    .venv\\Scripts\\python.exe blood\\record_wake.py talk --count 15
The clips go to models\\my_voice\\<spot>\\ (private, never committed).
Re-running a spot adds more clips; it never overwrites.
"""
import argparse
import pathlib
import time
import wave

import numpy as np
import sounddevice as sd

RATE = 16000
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "models" / "my_voice"


def beep(freq=880, secs=0.25):
    """Windows' built-in beep (reliable); falls back to a sounddevice tone elsewhere."""
    try:
        import winsound
        winsound.Beep(int(freq), int(secs * 1000))
    except (ImportError, RuntimeError):
        t = np.arange(int(RATE * (secs + 0.3))) / RATE
        tone = (np.sin(2 * np.pi * freq * t) * 0.5 * 32767).astype(np.int16)
        sd.play(tone, RATE, blocking=True)


def save(path, audio):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(audio.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spot", choices=["desk", "bed", "far", "talk"])
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--seconds", type=float, default=2.5, help="recording window after each beep")
    ap.add_argument("--pause", type=float, default=1.5, help="rest between clips")
    ap.add_argument("--start-delay", type=float, default=8, help="time to walk to the spot")
    ap.add_argument("--mic", type=int, default=None)
    a = ap.parse_args()

    folder = OUT / a.spot
    folder.mkdir(parents=True, exist_ok=True)
    n = len(list(folder.glob("*.wav")))
    say = "the wake word" if a.spot != "talk" else "a normal phrase (NOT the wake word)"
    print(f"Recording {a.count} clips at '{a.spot}'. After each BEEP, say {say} once.")
    print(f"Starting in {a.start_delay:.0f} s, go to your spot...")
    time.sleep(a.start_delay)

    for i in range(a.count):
        beep()
        print(f"  >>> SAY IT NOW ({i + 1}/{a.count}) <<<", flush=True)
        audio = sd.rec(int(a.seconds * RATE), samplerate=RATE, channels=1, dtype="int16", device=a.mic)
        sd.wait()
        audio = audio[:, 0]
        n += 1
        path = folder / f"{a.spot}_{n:03d}.wav"
        save(path, audio)
        level = 20 * np.log10(max(np.abs(audio).max(), 1) / 32768)
        print(f"  {i + 1}/{a.count}  saved {path.name}  (loudest {level:.0f} dB)")
        time.sleep(a.pause)
    beep(freq=440, secs=0.4)
    print(f"Done. {n} clips in {folder}")


if __name__ == "__main__":
    main()
