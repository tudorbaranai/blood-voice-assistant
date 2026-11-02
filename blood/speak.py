"""Blood's mouth: clean the answer text, then have Piper say it on the speakers.

Piper runs inside Home Assistant (port 10200, the Wyoming protocol). It sends
the audio in pieces while it's still working, and we play each piece as soon
as it arrives, so Blood starts talking before the whole answer is made.

Try it:
    .venv\\Scripts\\python.exe blood\\speak.py "Good morning, Tudor. The lights are on."
"""
import asyncio
import re
import sys
import unicodedata

import numpy as np
import sounddevice as sd
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.tts import Synthesize, SynthesizeVoice

HOST, PORT = "127.0.0.1", 10200


def clean(text, your_name="Tudor", name_spoken=None):
    """Make the text safe to read aloud.

    - drops emojis and letters the English voice can't say (Korean, Chinese, ...)
    - drops markdown symbols (* # ` _) that small AI models like to add
    - swaps your name for its sound spelling, so it's pronounced right
    """
    text = re.sub(r"\s*°\s*[CF]?\b", " degrees", text)
    keep = []
    for ch in unicodedata.normalize("NFC", text):
        if ch.isascii():
            keep.append(ch)
        elif unicodedata.category(ch).startswith("L") and "LATIN" in unicodedata.name(ch, ""):
            keep.append(ch)                   # é, ă, ș ... are fine
        elif ch in "’‘“”–—…":
            keep.append({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": ",",
                         "…": "..."}[ch])
    text = "".join(keep)
    text = re.sub(r"[*#`_~>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    if name_spoken:
        text = re.sub(rf"\b{re.escape(your_name)}\b", name_spoken, text)
    return text


async def synthesize(text, voice):
    """Yield (audio bytes, rate) pieces as Piper makes them."""
    async with AsyncTcpClient(HOST, PORT) as client:
        await client.write_event(Synthesize(text=text, voice=SynthesizeVoice(name=voice)).event())
        rate = None
        while True:
            event = await client.read_event()
            if event is None:
                raise RuntimeError("Piper closed the connection.")
            if AudioStart.is_type(event.type):
                rate = AudioStart.from_event(event).rate
            elif AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                yield chunk.audio, rate or chunk.rate
            elif AudioStop.is_type(event.type):
                return


async def render(text, voice):
    """The whole sentence as one int16 array (used for the greeting, made once)."""
    parts, rate = [], 22050
    async for audio, rate in synthesize(text, voice):
        parts.append(np.frombuffer(audio, np.int16))
    return np.concatenate(parts), rate


def play(samples, rate, volume=1.0):
    """Play a ready-made int16 array and wait until it's finished."""
    sd.play((samples * volume).astype(np.int16), rate, blocking=True)


async def say(text, voice, volume=1.0):
    """Stream Piper's audio to the speakers as it arrives."""
    loop = asyncio.get_running_loop()
    stream = None
    try:
        async for audio, rate in synthesize(text, voice):
            if stream is None:
                stream = sd.OutputStream(samplerate=rate, channels=1, dtype="int16")
                stream.start()
            samples = (np.frombuffer(audio, np.int16) * volume).astype(np.int16)
            await loop.run_in_executor(None, stream.write, samples)   # waits while it plays
    finally:
        if stream is not None:
            await loop.run_in_executor(None, stream.stop)               # let the last bit finish
            stream.close()


if __name__ == "__main__":
    line = " ".join(sys.argv[1:]) or "Good morning, Tudor. The lights are on."
    spoken = clean(line, name_spoken="[[ tˈudor ]]")
    print(f"Saying: {spoken}")
    asyncio.run(say(spoken, "en_US-libritts_r-medium"))
