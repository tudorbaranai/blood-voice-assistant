"""Speech-to-text test bench.

Sends every recording to the speech-to-text server (the Whisper add-on, via
the Wyoming protocol) and scores what it heard against what you really said.

Usage (run once per engine setting you want to compare):
    python bench_stt.py --label parakeet
    python bench_stt.py --label whisper-small-prompt
    python bench_stt.py --compare          show all runs side by side
    python bench_stt.py --label mic-a --dir mic-test-a   test another recordings folder

Score: "word errors" = words wrong, missing or extra, as a percentage of all
words (lower is better). "Seconds" = time from the end of the audio until the
text comes back, which is what you feel as waiting time.
"""
import argparse
import asyncio
import csv
import datetime
import pathlib
import re
import time
import wave

import jiwer
from num2words import num2words
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient

HERE = pathlib.Path(__file__).parent
RESULTS = HERE / "results"
SUMMARY = RESULTS / "summary.csv"
NAMES = ["jarvis", "tudor"]  # words we especially care about

CONTRACTIONS = {"what's": "what is", "it's": "it is", "i'm": "i am", "don't": "do not",
                "can't": "cannot", "that's": "that is", "there's": "there is"}
# American and British spellings of the same word count as the same word.
SPELLINGS = {"kilometers": "kilometres", "kilometer": "kilometre", "meters": "metres",
             "meter": "metre", "color": "colour", "favorite": "favourite"}
# Hesitation sounds: if you really said "uh", writing it down is not a mistake.
FILLERS = {"uh", "um", "er", "erm", "ah", "hmm", "mm"}


def normalize(text):
    """Make texts comparable: lowercase, numbers as words, no punctuation."""
    text = text.lower().replace("%", " percent")
    text = re.sub(r"(\d+)(st|nd|rd|th)\b", lambda m: num2words(int(m.group(1)), to="ordinal"), text)
    text = re.sub(r"\d+", lambda m: num2words(int(m.group())), text)
    text = re.sub(r"[^a-z' ]", " ", text.replace("-", " "))
    words = []
    for word in text.split():
        if word in FILLERS:
            continue
        words.extend(CONTRACTIONS.get(word, SPELLINGS.get(word, word)).split())
    return " ".join(words)


def load_phrases():
    lines = (HERE / "phrases.txt").read_text(encoding="utf-8").splitlines()
    phrases = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    return [p.removeprefix("@far").strip() for p in phrases]


async def transcribe(host, port, wav_path):
    with wave.open(str(wav_path), "rb") as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        audio = w.readframes(w.getnframes())

    async with AsyncTcpClient(host, port) as client:
        await client.write_event(Transcribe(language="en").event())
        await client.write_event(AudioStart(rate=rate, width=width, channels=channels).event())
        step = 1024 * width * channels
        for i in range(0, len(audio), step):
            await client.write_event(
                AudioChunk(rate=rate, width=width, channels=channels, audio=audio[i:i + step]).event())
        await client.write_event(AudioStop().event())
        started = time.perf_counter()
        while True:
            event = await client.read_event()
            if event is None:
                raise RuntimeError("The speech-to-text server closed the connection.")
            if Transcript.is_type(event.type):
                return Transcript.from_event(event).text, time.perf_counter() - started


async def run(label, host, port, recordings):
    phrases = load_phrases()
    rows, refs, hyps, seconds = [], [], [], []
    print(f"Testing '{label}' on {host}:{port}\n")
    for number, expected in enumerate(phrases, 1):
        wav = recordings / f"{number:02d}.wav"
        if not wav.exists():
            print(f"  {number:02d}  (no recording, skipped)")
            continue
        heard, secs = await transcribe(host, port, wav)
        ref, hyp = normalize(expected), normalize(heard)
        wer = jiwer.wer(ref, hyp) if hyp else 1.0
        refs.append(ref); hyps.append(hyp); seconds.append(secs)
        mark = "OK " if wer == 0 else "ERR"
        print(f"  {number:02d} {mark} {secs:5.2f}s  heard: {heard}")
        rows.append((number, expected, heard, wer, secs))

    if not rows:
        print("No recordings found. Run record.py first.")
        return

    total_wer = jiwer.wer(refs, hyps)
    names_total = sum(r.split().count(n) for r in refs for n in NAMES)
    names_heard = sum(min(r.split().count(n), h.split().count(n)) for r, h in zip(refs, hyps) for n in NAMES)
    avg, worst = sum(seconds) / len(seconds), max(seconds)
    perfect = sum(1 for r in rows if r[3] == 0)

    print(f"\n  Word errors: {total_wer:.1%}   Perfect sentences: {perfect}/{len(rows)}   "
          f"Names (Jarvis/Tudor) heard: {names_heard}/{names_total}   "
          f"Seconds: avg {avg:.2f}, worst {worst:.2f}")

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    report = RESULTS / f"stt-{label}-{stamp}.md"
    lines = [f"# Speech-to-text test: {label} ({stamp})", "",
             f"Word errors **{total_wer:.1%}**, perfect {perfect}/{len(rows)}, "
             f"names {names_heard}/{names_total}, seconds avg {avg:.2f} / worst {worst:.2f}", "",
             "| # | You said | It heard | Errors | Seconds |", "|---|---|---|---|---|"]
    lines += [f"| {n} | {e} | {h} | {w:.0%} | {s:.2f} |" for n, e, h, w, s in rows]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    new_file = not SUMMARY.exists()
    with SUMMARY.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["when", "label", "word_errors", "perfect", "sentences", "names_heard",
                             "names_total", "avg_seconds", "worst_seconds"])
        writer.writerow([stamp, label, f"{total_wer:.4f}", perfect, len(rows), names_heard,
                         names_total, f"{avg:.2f}", f"{worst:.2f}"])
    print(f"  Report saved: {report}")


def compare():
    if not SUMMARY.exists():
        print("No runs yet.")
        return
    with SUMMARY.open(encoding="utf-8") as f:
        runs = list(csv.DictReader(f))
    print(f"{'label':28} {'word errors':>11} {'perfect':>8} {'names':>6} {'avg s':>6} {'worst s':>8}")
    for r in sorted(runs, key=lambda r: float(r["word_errors"])):
        print(f"{r['label']:28} {float(r['word_errors']):>11.1%} {r['perfect'] + '/' + r['sentences']:>8} "
              f"{r['names_heard'] + '/' + r['names_total']:>6} {r['avg_seconds']:>6} {r['worst_seconds']:>8}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", help="name for this run, e.g. the engine setting being tested")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--dir", default="recordings", help="folder with the recordings to test")
    parser.add_argument("--compare", action="store_true", help="show all previous runs side by side")
    args = parser.parse_args()
    if args.compare:
        compare()
    elif args.label:
        asyncio.run(run(args.label, args.host, args.port, HERE / args.dir))
    else:
        parser.error("give --label NAME (or --compare)")


if __name__ == "__main__":
    main()
