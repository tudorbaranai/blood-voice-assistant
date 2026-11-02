"""Blood, the voice program. Runs on the laptop, all the time.

    mic --> "Hey Blood"? --> "Yes, Tudor?" --> record until you stop talking
        --> HA (ear + brain) --> clean the answer --> Piper says it --> back to listening

Start it:
    .venv\\Scripts\\python.exe blood\\blood.py
Stop it with Ctrl+C. Settings are in blood\\settings.toml, the log in logs\\blood.log.
"""
import asyncio
import collections
import logging
import pathlib
import re
import sys
import time
import tomllib

import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from openwakeword.vad import VAD

from ha import Assist
from speak import clean, play, render, say

ROOT = pathlib.Path(__file__).resolve().parent.parent
RATE, CHUNK = 16000, 1280                 # 80 ms pieces, what openWakeWord works in
CHUNK_SECONDS = CHUNK / RATE

# Answers that only promise to act ("I'll check the light") without doing it.
# Small models sometimes stop there; we then tell them "Go ahead." once.
# Only "look something up" verbs, right after the promise, so "Let me know if
# you want me to turn it off" never triggers it.
PROMISE = re.compile(r"\b(I'll|I will|let me|I'm going to|I need to)\s+(now\s+|first\s+)?(check|use|look|get|find|see)\b", re.I)

FILLERS = re.compile(r"\b(uh+|um+|er+|ah+|hmm+|erm)\b[,.]?\s*", re.I)
WAKE_AGAIN = re.compile(r"^\s*(hey|hi|a)\s+(blood|blud|bud)\b[,.!]?\s*", re.I)

log = logging.getLogger("blood")


def tidy_heard(text, fixes):
    """Small fixes to what the ear wrote, so HA's own sentences (and your
    automations) match and the slow brain isn't needed:
    "Uh close the bedlights." -> "close the bed lights"."""
    text = WAKE_AGAIN.sub("", FILLERS.sub("", text))
    for wrong, right in fixes.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,.")
    return text[:1].upper() + text[1:]


def setup_logging():
    (ROOT / "logs").mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S")
    file = logging.FileHandler(ROOT / "logs" / "blood.log", encoding="utf-8")
    screen = logging.StreamHandler(sys.stdout)
    for h in (file, screen):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


class Mic:
    """Collects 80 ms pieces of microphone sound into a queue we can wait on."""

    def __init__(self, device):
        self.queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def callback(indata, frames, when, status):
            loop.call_soon_threadsafe(self.queue.put_nowait, indata[:, 0].copy())

        self.stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=CHUNK,
                                     device=device or None, callback=callback)
        self.stream.start()

    async def read(self):
        return await self.queue.get()

    def flush(self):
        """Throw away what the mic heard meanwhile (e.g. Blood's own voice)."""
        while not self.queue.empty():
            self.queue.get_nowait()


class Blood:
    def __init__(self, cfg):
        self.cfg = cfg
        self.wake = Model(wakeword_models=[str(ROOT / cfg["wake"]["model"])], inference_framework="onnx")
        self.wake_name = list(self.wake.models)[0]
        self.vad = VAD()
        self.assist = Assist()
        self.voice = cfg["voice"]
        self.last_request = 0.0

    def spoken(self, text):
        return clean(text, self.voice["your_name"], self.voice["name_spoken"])

    async def start(self):
        self.mic = Mic(self.cfg["mic"]["device"])
        self.greeting = await render(self.spoken(self.voice["greeting"]), self.voice["name"])
        log.info(f"Ready. Listening for '{self.wake_name}' (threshold {self.cfg['wake']['threshold']}). Ctrl+C to stop.")
        while True:
            await self.wait_for_wake_word()
            await self.handle_request()
            self.mic.flush()
            self.wake.reset()

    async def wait_for_wake_word(self):
        threshold = self.cfg["wake"]["threshold"]
        while True:
            score = self.wake.predict(await self.mic.read())[self.wake_name]
            if score >= threshold:
                log.info(f"Wake word (score {score:.2f})")
                return

    async def handle_request(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, play, *self.greeting, self.voice["volume"])
        await asyncio.sleep(0.25)                          # the room's echo of "Yes, Tudor?" dies down
        self.mic.flush()                                   # don't send Blood's own voice

        first = await self.wait_for_speech()
        if first is None:
            log.info("No speech after the greeting, back to sleep")
            return
        t0 = time.perf_counter()
        self.recorded = (0.0, 0.0)
        # A long silence = a new topic: start a fresh, short conversation. A long
        # one makes the brain re-read all of it, which is what made it slow.
        if time.monotonic() - self.last_request > self.cfg["listen"]["forget_after"]:
            self.assist.conversation_id = None
        heard = said = answer = None
        try:
            heard = await self.assist.transcribe(self.rest_of_speech(first))
            ear = time.perf_counter() - t0
            said = tidy_heard(heard or "", self.cfg.get("heard_fixes", {}))
            if said:
                answer = await self.assist.ask_text(said)
                if answer and PROMISE.search(answer) and len(answer) < 160:
                    log.info(f"Only a promise ({answer!r}), telling it to go ahead")
                    answer = await self.assist.ask_text("Go ahead.")
        except Exception as error:                        # HA down, nothing understood, ...
            log.info(f"Problem: {error}")
        self.last_request = time.monotonic()
        if heard is None or not said:
            answer = "Sorry, I didn't catch that."
        log.info(f"Recorded {self.recorded[0]:.1f}s ({self.recorded[1]:.1f}s of it speech)")
        log.info(f"Heard: {heard!r} -> sent {said!r}  ->  Blood: {answer!r}  "
                 f"(ear {ear if heard else 0:.1f}s, total {time.perf_counter() - t0:.1f}s)")
        if answer:
            await say(self.spoken(answer), self.voice["name"], self.voice["volume"])

    async def wait_for_speech(self):
        """Wait until you start talking. Returns the last ~0.5 s of sound (so the
        start of the first word isn't lost), or None if you said nothing."""
        cfg = self.cfg["listen"]
        before = collections.deque(maxlen=8)
        self.vad.reset_states()
        in_a_row = 0
        for _ in range(int(cfg["wait_for_speech"] / CHUNK_SECONDS)):
            chunk = await self.mic.read()
            before.append(chunk)
            talking = self.vad.predict(chunk, frame_size=640) >= cfg["speech_threshold"]
            in_a_row = in_a_row + 1 if talking else 0
            if in_a_row >= 2:                  # 160 ms of real speech, not a click or an echo
                return list(before)
        return None

    async def rest_of_speech(self, first):
        """Send the sound to HA while you talk. Stop once you've said something
        AND then stayed quiet for a moment (a pause before you start doesn't count)."""
        cfg = self.cfg["listen"]
        for chunk in first:
            yield chunk.tobytes()
        quiet, total, speech = 0.0, len(first) * CHUNK_SECONDS, 2 * CHUNK_SECONDS
        while total < cfg["max_seconds"]:
            # Said enough: a short pause ends it. Only a word or an echo so far: wait
            # longer, you may not have started yet.
            if quiet >= (cfg["silence_to_stop"] if speech >= cfg["min_speech"] else cfg["silence_if_short"]):
                break
            chunk = await self.mic.read()
            yield chunk.tobytes()
            total += CHUNK_SECONDS
            if self.vad.predict(chunk, frame_size=640) >= cfg["speech_threshold"]:
                quiet, speech = 0.0, speech + CHUNK_SECONDS
            else:
                quiet += CHUNK_SECONDS
            self.recorded = (total, speech)


async def main():
    setup_logging()
    cfg = tomllib.loads((ROOT / "blood" / "settings.toml").read_text(encoding="utf-8"))
    await Blood(cfg).start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
