"""Record Tudor reading the test sentences, one WAV file per sentence.

The files are saved as 16 kHz, mono, 16-bit WAV: the same format the
speech-to-text server expects, so every engine hears exactly the same audio.

Usage:
    python record.py                      record every sentence that has no recording yet
    python record.py 7                    (re-)record only sentence number 7
    python record.py --redo               record everything again
    python record.py --dir mic-test-a --only 4,7,13,14,15
                                          record a few sentences into another folder
                                          (used to compare microphone settings)
"""
import argparse
import pathlib
import wave

import numpy as np
import sounddevice as sd

HERE = pathlib.Path(__file__).parent
PHRASES = HERE / "phrases.txt"
RATE = 16000


def load_phrases():
    lines = PHRASES.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def record_one(out, number, total, line):
    far = line.startswith("@far")
    text = line.removeprefix("@far").strip()
    hint = "  (stand ACROSS THE ROOM for this one)" if far else ""

    input(f'\n[{number}/{total}] Press Enter, then say:{hint}\n    "{text}"')
    chunks = []
    with sd.InputStream(samplerate=RATE, channels=1, dtype="int16",
                        callback=lambda data, *_: chunks.append(data.copy())):
        input("    Recording... press Enter when you're done.")
    audio = np.concatenate(chunks)

    path = out / f"{number:02d}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(audio.tobytes())
    print(f"    Saved {path.name} ({len(audio) / RATE:.1f} s)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("number", nargs="?", type=int, help="record only this sentence")
    parser.add_argument("--redo", action="store_true", help="record everything again")
    parser.add_argument("--dir", default="recordings", help="folder to save into")
    parser.add_argument("--only", help="comma-separated sentence numbers, e.g. 4,7,13")
    args = parser.parse_args()

    out = HERE / args.dir
    out.mkdir(exist_ok=True)
    phrases = load_phrases()
    wanted = {args.number} if args.number else (
        {int(n) for n in args.only.split(",")} if args.only else None)

    print(f"Microphone: {sd.query_devices(kind='input')['name']}")
    print(f"Saving into: {out}")
    for number, line in enumerate(phrases, 1):
        if wanted and number not in wanted:
            continue
        if not (wanted or args.redo) and (out / f"{number:02d}.wav").exists():
            continue
        record_one(out, number, len(phrases), line)
    print("\nDone. Recordings are in:", out)


if __name__ == "__main__":
    main()
