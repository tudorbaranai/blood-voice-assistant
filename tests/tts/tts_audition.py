"""Voice audition for Blood.

Asks the Piper text-to-speech server (via the Wyoming protocol) to speak the
same Blood sentences in several voices. For each voice it saves one WAV file
you can listen to, and measures how fast the voice is:

  first sound   time until the first piece of audio comes back
                (what you feel as waiting time, because Piper streams)
  total         time to create the whole answer
  speed         how many seconds of speech it makes per second of work
                (above 1x = faster than real time)

Usage:
    python tts_audition.py                       audition the default voices
    python tts_audition.py en_GB-alan-medium     audition only these voices
"""
import asyncio
import pathlib
import sys
import time
import wave

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.info import Describe, Info
from wyoming.tts import Synthesize, SynthesizeVoice

HOST, PORT = "127.0.0.1", 10200
HERE = pathlib.Path(__file__).parent
OUT = HERE / "voices"

VOICES = [
    "en_GB-alan-medium",                  # British male
    "en_GB-northern_english_male-medium", # British male, northern accent
    "en_US-ryan-high",                    # American male, high quality
    "en_US-lessac-high",                  # American, high quality
    "en_US-joe-medium",                   # American male
    "en_GB-cori-high",                    # British female, high quality
]

SENTENCES = [
    "Yes, Tudor?",
    "The capital of Peru is Lima.",
    "Done, the desk lamp is on.",
    "It's twenty one degrees and fifty percent humidity in the bedroom.",
    "Sorry, I'm offline, so I can't check the weather. Anything else I can help with?",
]


async def synthesize(text, voice):
    """Returns (audio bytes, rate, width, channels, seconds to first sound, total seconds)."""
    async with AsyncTcpClient(HOST, PORT) as client:
        started = time.perf_counter()
        await client.write_event(Synthesize(text=text, voice=SynthesizeVoice(name=voice)).event())
        audio, first, fmt = bytearray(), None, None
        while True:
            event = await client.read_event()
            if event is None:
                raise RuntimeError("The text-to-speech server closed the connection.")
            if AudioStart.is_type(event.type):
                start = AudioStart.from_event(event)
                fmt = (start.rate, start.width, start.channels)
            elif AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                if first is None:
                    first = time.perf_counter() - started
                fmt = fmt or (chunk.rate, chunk.width, chunk.channels)
                audio += chunk.audio
            elif AudioStop.is_type(event.type):
                return bytes(audio), *fmt, first, time.perf_counter() - started


async def audition(voice):
    print(f"\n{voice}")
    print("  preparing (the first time, the voice is downloaded)...")
    await synthesize("Hello.", voice)  # warm-up, not timed

    clips, firsts, totals, spoken = [], [], [], 0.0
    for text in SENTENCES:
        audio, rate, width, channels, first, total = await synthesize(text, voice)
        seconds = len(audio) / (rate * width * channels)
        clips.append(audio)
        firsts.append(first); totals.append(total); spoken += seconds
        print(f"  first sound {first:5.2f}s  total {total:5.2f}s  ({seconds:4.1f}s of speech)  {text}")

    silence = bytes(int(rate * 0.6) * width * channels)
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{voice}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(silence.join(clips))
    avg_first = sum(firsts) / len(firsts)
    speed = spoken / sum(totals)
    print(f"  => first sound avg {avg_first:.2f}s, speed {speed:.1f}x real time, saved {path.name}")
    return voice, avg_first, max(firsts), speed


async def known_voices():
    """Ask the server which voices exist, so a typo isn't silently replaced by the default voice."""
    async with AsyncTcpClient(HOST, PORT) as client:
        await client.write_event(Describe().event())
        while True:
            event = await client.read_event()
            if event is None:
                raise RuntimeError("The text-to-speech server closed the connection.")
            if Info.is_type(event.type):
                return {v.name for tts in Info.from_event(event).tts for v in tts.voices}


async def main():
    voices = sys.argv[1:] or VOICES
    available = await known_voices()
    results = []
    for voice in voices:
        if voice not in available:
            print(f"\n{voice}: not available on this Piper server, skipped")
            continue
        try:
            results.append(await audition(voice))
        except Exception as error:  # one broken voice shouldn't stop the whole audition
            print(f"  failed: {error}")
    print(f"\n{'voice':38} {'first sound avg':>16} {'worst':>6} {'speed':>7}")
    for voice, avg_first, worst, speed in results:
        print(f"{voice:38} {avg_first:>15.2f}s {worst:>5.2f}s {speed:>6.1f}x")
    print(f"\nListen to the files in: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
