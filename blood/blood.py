"""Blood, the voice program. Runs on the laptop, all the time.

    mic --> "Hey Blood"? --> "Yes, Tudor?" --> record until you stop talking
        --> HA (ear + brain) --> clean the answer --> Piper says it --> back to listening

Start it:
    .venv\\Scripts\\python.exe blood\\blood.py
Stop it with Ctrl+C. Settings are in blood\\settings.toml, the log in logs\\blood.log.
At login it starts by itself, hidden (Task Scheduler: "Blood - voice program").
"""
import asyncio
import collections
import logging
import logging.handlers
import pathlib
import re
import socket
import sys
import time
import tomllib
import winsound

import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from openwakeword.vad import VAD

from ha import Assist
from screen import NoScreen, Screen
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


def mic_level(chunk):
    """How loud you are, 0..1, for the screen's orb (normal speech is about 0.3-0.8)."""
    return min(1.0, float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2))) / 2500)


def setup_logging():
    (ROOT / "logs").mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S")
    # 1 MB per file, the last 3 kept: it runs for months, the log must not grow forever
    handlers = [logging.handlers.RotatingFileHandler(ROOT / "logs" / "blood.log", maxBytes=1_000_000,
                                                     backupCount=3, encoding="utf-8")]
    if sys.stdout:                     # started hidden (pythonw) = no screen to print to
        handlers.append(logging.StreamHandler(sys.stdout))
    for h in handlers:
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def only_one_blood():
    """Two Bloods would both answer. The first one holds this local port; a
    second one sees it's taken and quits."""
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 47201))
    except OSError:
        log.info("Blood is already running, this copy quits.")
        sys.exit(0)
    return lock


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
        screen = cfg.get("screen", {})
        self.screen = Screen(screen.get("hide_after", 10)) if screen.get("enabled", True) else NoScreen()

    def spoken(self, text):
        return clean(text, self.voice["your_name"], self.voice["name_spoken"])

    def level(self, value):
        self.screen.send(level=round(value, 3))

    async def start(self):
        await self.screen.start()
        await self.wait_for_home_assistant()
        self.mic = Mic(self.cfg["mic"]["device"])
        log.info(f"Ready. Listening for '{self.wake_name}' (threshold {self.cfg['wake']['threshold']}). Ctrl+C to stop.")
        while True:
            await self.wait_for_wake_word()
            try:
                await self.handle_request()
            except Exception:                  # never let one bad request stop Blood
                log.exception("Something went wrong with this request")
                winsound.Beep(300, 400)        # low beep = "that didn't work"
            self.screen.done()
            self.mic.flush()
            self.wake.reset()

    async def wait_for_home_assistant(self):
        """After a restart the VM needs 1-2 minutes. The voice lives in HA too, so
        making the greeting is a good "is it up?" test: retry until it works."""
        waiting = False
        while True:
            try:
                self.greeting = await render(self.spoken(self.voice["greeting"]), self.voice["name"])
                return
            except OSError:
                if not waiting:
                    log.info("Waiting for Home Assistant (the voice isn't reachable yet)...")
                    waiting = True
                await asyncio.sleep(10)

    async def wait_for_wake_word(self):
        threshold = self.cfg["wake"]["threshold"]
        while True:
            score = self.wake.predict(await self.mic.read())[self.wake_name]
            if score >= threshold:
                log.info(f"Wake word (score {score:.2f})")
                return

    async def handle_request(self):
        asyncio.create_task(self.screen.show())             # screen on, window to the front
        self.screen.send(state="speaking")
        await play(*self.greeting, self.voice["volume"], on_level=self.level)
        self.screen.send(state="listening")
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
                self.screen.send(state="thinking", heard=said)
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
            self.screen.send(state="speaking", answer=clean(answer))      # the screen shows "Tudor"
            await say(self.spoken(answer), self.voice["name"], self.voice["volume"], on_level=self.level)

    async def wait_for_speech(self):
        """Wait until you start talking. Returns the last ~0.5 s of sound (so the
        start of the first word isn't lost), or None if you said nothing."""
        cfg = self.cfg["listen"]
        before = collections.deque(maxlen=8)
        self.vad.reset_states()
        in_a_row = 0
        for _ in range(int(cfg["wait_for_speech"] / CHUNK_SECONDS)):
            chunk = await self.mic.read()
            self.level(mic_level(chunk))
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
            self.level(mic_level(chunk))
            yield chunk.tobytes()
            total += CHUNK_SECONDS
            if self.vad.predict(chunk, frame_size=640) >= cfg["speech_threshold"]:
                quiet, speech = 0.0, speech + CHUNK_SECONDS
            else:
                quiet += CHUNK_SECONDS
            self.recorded = (total, speech)


async def main():
    cfg = tomllib.loads((ROOT / "blood" / "settings.toml").read_text(encoding="utf-8"))
    await Blood(cfg).start()


if __name__ == "__main__":
    setup_logging()
    lock = only_one_blood()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
    except Exception:
        log.exception("Blood crashed (Task Scheduler restarts it in a minute)")
        raise
