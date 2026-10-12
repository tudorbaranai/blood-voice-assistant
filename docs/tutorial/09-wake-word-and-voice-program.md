# 09 · Wake word and our own voice program ⬜ planned

> This chapter is a plan. It will be rewritten with the real steps once it's built.

## Goal
Say **"Hey Blood"** → hear **"Yes?"** → speak → hear the answer on the speakers.
No browser, no clicking.

```
mic → [wake word "Hey Blood"] → play "Yes?" → record until you stop talking
    → send to Home Assistant (ear + brain) → get the answer as text
    → clean the text → Piper speaks it → speakers
```

## Why our own program, instead of letting Home Assistant do everything
Home Assistant runs inside the VM and can't use the Windows mic and speakers.
So a small Python program on Windows does the "mouth and ears" part, and also
gives us control at code level:
- **Guaranteed clean speech:** strip characters the voice can't read (the model
  sometimes adds Korean letters or emojis, see chapter 04).
- **Names pronounced right:** voices read names with English rules. We swap the
  name for a phonetic spelling just before speaking (found with
  [`tests/tts/name_test.py`](../../tests/tts/name_test.py)), while the screen
  still shows the normal spelling.

## Planned pieces
| Piece | How |
|---|---|
| Wake word | [openWakeWord](https://github.com/dscripka/openWakeWord), always listening, ~1–3% CPU. There's no ready-made "Hey Blood", so we train one with openWakeWord's free training notebook (Google Colab, about 1 hour). Only the *training* is online; the model then runs offline. Until then: the built-in `hey_jarvis` model as a stand-in. |
| Greeting | a pre-made "Yes, <name>?" audio file in the same Piper voice |
| End of speech | voice activity detection (stop recording when you stop talking) |
| Home Assistant connection | the websocket API with a **long-lived access token** (Profile → Security → Long-lived access tokens), stored in a `.env` file that is **never committed** |
| Speaking | Piper over the Wyoming protocol (port 10200, see chapter 06) |
| Auto-start | Task Scheduler at login, `pythonw.exe` (no window) |
| Settings | one config file: mic, volume, wake-word sensitivity |
| Logs | a log file, to diagnose problems |

## How we'll test it
- **Distance:** "Hey Blood" from the desk, the bed and across the room, 10 tries each.
- **False triggers:** an hour of YouTube/TV with it running. Aim for 0–1 per hour.
- **Speed:** from the end of your sentence to the first word of the answer. Target ~2–3 s.
- **Name:** does "Yes, <name>?" sound right?
