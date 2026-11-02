"""Talk to Home Assistant's Assist (Blood's ear and brain) over the websocket API.

HA already has everything set up: Parakeet turns speech into text, the
blood-brain model answers and switches devices. This file only carries things
back and forth:

    our audio (or typed text) --> HA --> what it heard + Blood's answer (text)

We stop HA before its own speaking step, because we speak the answer ourselves
(so we can clean the text and say "Tudor" right).

Test it by typing, without the mic:
    .venv\\Scripts\\python.exe blood\\ha.py "what time is it?"
"""
import asyncio
import json
import pathlib
import sys
import time

import websockets

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = "ws://127.0.0.1:8123/api/websocket"


def load_token():
    """Read HA_TOKEN from jarvis\\.env (never printed, never committed)."""
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "HA_TOKEN":
            return value.strip().strip('"')
    raise SystemExit("HA_TOKEN not found in jarvis\\.env")


class Assist:
    """One run of HA's Assist pipeline. Keeps the conversation id, so follow-ups
    ("and the other one?") are understood, like in the HA chat window."""

    def __init__(self, token=None):
        self.token = token or load_token()
        self.conversation_id = None
        self.timings = {}       # pipeline step -> seconds since the start (for the log)

    async def _connect(self):
        ws = await websockets.connect(URL, max_size=None)
        await ws.recv()                                              # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": self.token}))
        reply = json.loads(await ws.recv())
        if reply.get("type") != "auth_ok":
            await ws.close()
            raise RuntimeError("Home Assistant refused the token (check HA_TOKEN in .env)")
        return ws

    async def _run(self, start_stage, run_input, audio_chunks=None, end_stage="intent"):
        """Start the pipeline, feed audio if any, collect what HA heard and answered."""
        ws = await self._connect()
        try:
            msg = {"id": 1, "type": "assist_pipeline/run", "start_stage": start_stage,
                   "end_stage": end_stage, "input": run_input}
            if self.conversation_id:
                msg["conversation_id"] = self.conversation_id
            await ws.send(json.dumps(msg))

            heard, answer, sender = None, None, None
            started, self.timings = time.perf_counter(), {}
            async for raw in ws:
                m = json.loads(raw)
                if m.get("type") == "result" and not m.get("success"):
                    raise RuntimeError(f"HA: {m.get('error', {}).get('message')}")
                if m.get("type") != "event":
                    continue
                kind, data = m["event"]["type"], m["event"].get("data") or {}
                self.timings[kind] = round(time.perf_counter() - started, 2)
                if kind == "run-start" and audio_chunks is not None:
                    handler = data["runner_data"]["stt_binary_handler_id"]
                    sender = asyncio.create_task(self._send_audio(ws, handler, audio_chunks))
                elif kind == "stt-end":
                    heard = data["stt_output"]["text"]
                    if end_stage == "stt":
                        break
                elif kind == "intent-end":
                    out = data["intent_output"]
                    self.conversation_id = out.get("conversation_id") or self.conversation_id
                    answer = out["response"]["speech"]["plain"]["speech"]
                elif kind == "error":
                    raise RuntimeError(f"HA {data.get('code')}: {data.get('message')}")
                elif kind == "run-end":
                    break
            return heard, answer
        finally:
            if sender:
                sender.cancel()
            await ws.close()

    @staticmethod
    async def _send_audio(ws, handler, audio_chunks):
        """Audio goes as binary messages: 1 byte "which stream" + raw 16 kHz 16-bit mono.
        An empty message (just the byte) means "I'm done talking"."""
        prefix = bytes([handler])
        async for chunk in audio_chunks:
            await ws.send(prefix + chunk)
        await ws.send(prefix)

    async def ask_text(self, text):
        """Skip the ear: send typed text straight to the brain. Returns the answer."""
        _, answer = await self._run("intent", {"text": text})
        return answer

    async def ask_audio(self, audio_chunks):
        """Send speech (an async iterator of 16 kHz int16 mono bytes).
        Returns (what HA heard, Blood's answer)."""
        return await self._run("stt", {"sample_rate": 16000}, audio_chunks)

    async def transcribe(self, audio_chunks):
        """Only the ear: speech in, text out (so we can tidy the text before the brain sees it)."""
        heard, _ = await self._run("stt", {"sample_rate": 16000}, audio_chunks, end_stage="stt")
        return heard


async def _demo(text):
    assist = Assist()
    print(f"You:   {text}")
    print(f"Blood: {await assist.ask_text(text)}")


if __name__ == "__main__":
    asyncio.run(_demo(" ".join(sys.argv[1:]) or "What time is it?"))
