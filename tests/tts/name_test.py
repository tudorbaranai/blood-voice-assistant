"""Find a spelling that makes the voice pronounce "Tudor" the way Tudor says it.

Text-to-speech voices read names with English rules, so "Tudor" comes out like
the English royal family ("TYOO-der"). The trick is to feed the voice a
different spelling, or even the exact sounds (phonemes, written between
[[ and ]]), that it will read correctly. Only the voice ever sees this
spelling; the screen can still show "Tudor".

Each spelling is saved as its own file, saying it in two sentences.
Listen and pick the number that sounds most like you.

Usage:
    python name_test.py                         uses en_US-ryan-high
    python name_test.py en_US-ryan-medium       try another voice
    python name_test.py en_US-ryan-medium 2     round 2 spellings (numbers 9-16)
"""
import asyncio
import pathlib
import sys
import wave

from tts_audition import synthesize

HERE = pathlib.Path(__file__).parent
OUT = HERE / "names"

SPELLINGS = [
    "Tudor",             # 1  the normal spelling, for comparison
    "Too-dor",           # 2
    "Toodor",            # 3
    "Toodore",           # 4
    "Tooh-door",         # 5
    "Too door",          # 6
    "[[ tˈuːdɔːɹ ]]",    # 7  exact sounds: TOO-dor
    "[[ tˈuːdoːɾ ]]",    # 8  exact sounds: TOO-do, with a tapped r (closer to Romanian)
]

# Round 2, aimed at the Romanian sounds: short u, clear o, rolled/tapped r
ROUND_2 = [
    "[[ tˈudoɾ ]]",      # 9   short u, short o, tapped r
    "[[ tˈudor ]]",      # 10  short u, short o, rolled r
    "[[ tˈuːdɔɾ ]]",     # 11  long u, open o, tapped r
    "[[ tˈʊdoɾ ]]",      # 12  "book" u, tapped r
    "[[ tˈudɔr ]]",      # 13  short u, open o, rolled r
    "[[ tˈuːdoɹ ]]",     # 14  long u, clear o, English r
    "[[ tˈuːdoː ]]",     # 15  no r at all (British style)
    "[[ tˈuːdo ]] r",    # 16  name, then a separate r
]


async def main():
    voice = sys.argv[1] if len(sys.argv) > 1 else "en_US-ryan-high"
    spellings, first = (ROUND_2, 9) if "2" in sys.argv[2:] else (SPELLINGS, 1)
    OUT.mkdir(exist_ok=True)
    await synthesize("Hello.", voice)  # warm-up
    for number, name in enumerate(spellings, first):
        clips = []
        for text in (f"Yes, {name}?", f"Good morning, {name}. The lights are on."):
            audio, rate, width, channels, _, _ = await synthesize(text, voice)
            clips.append(audio)
        silence = bytes(int(rate * 0.6) * width * channels)
        path = OUT / f"{voice}_{number}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(width)
            w.setframerate(rate)
            w.writeframes(silence.join(clips))
        print(f"  {number}: {name:18} -> {path.name}")
    print(f"\nListen to the files in: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
