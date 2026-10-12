# 🩸 Blood: a €0, fully offline home voice assistant

Say **"Hey Blood"**, ask a question or give a command, and hear the answer from
your speakers, like Google Home or Alexa. The difference: **it runs entirely
on one old Windows laptop, costs nothing, and your voice never leaves your home.**

```
 🎤 ─▶ wake word ─▶ ear (speech→text) ─▶ brain (local AI) ─▶ voice (text→speech) ─▶ 🔊
                                              │
                                              ▼
                                     💡 lights · 🔌 plugs
```

| Piece | Built with |
|---|---|
| Conductor + device control | [Home Assistant OS](https://www.home-assistant.io/) in a VirtualBox VM |
| Brain | [Ollama](https://ollama.com/) running `qwen3:4b-instruct` on the laptop's GPU |
| Ear (speech → text) | Parakeet, via Home Assistant's Whisper add-on |
| Voice (text → speech) | [Piper](https://github.com/rhasspy/piper), voice `en_US-libritts_r-medium` |
| Wake word *(in progress)* | [openWakeWord](https://github.com/dscripka/openWakeWord) with a custom "Hey Blood" model |
| Devices | WiZ Wi-Fi bulb, Tuya-based Wi-Fi plug |

> **Fully offline** means **no internet needed**: unplug it and Blood keeps
> working. Wi-Fi bulbs and plugs still need your **router** switched on, because
> that's how they reach the laptop. [Details](docs/tutorial/00-overview.md#what-fully-offline-means-here-read-this-it-matters).

---

## Status (V1)

| Stage | |
|---|---|
| Laptop ready for 24/7 | ✅ |
| Home Assistant OS in VirtualBox, auto-starts | ✅ |
| Brain: Ollama + prompt v6 | ✅ |
| Ear: Parakeet, mic tuned | ✅ |
| Voice: Piper | ✅ |
| Bluetooth into the VM | ✅ (optional, unused for now) |
| WiZ bulb in Home Assistant | ✅ |
| Smart plug, local (Tuya Local) | 🟡 next |
| Device names + device-aware prompt v7 | ⬜ |
| "Hey Blood" wake word + own voice program | ⬜ |
| Screen window | ⬜ |

## The tutorial

Start at **[docs/tutorial/00-overview.md](docs/tutorial/00-overview.md)** and
follow the chapters in order. Each one has the same shape:
**Goal → Why → Steps → Check it worked → What went wrong for us.**

1. [Prepare the laptop for 24/7](docs/tutorial/01-laptop-24-7.md)
2. [The brain: Ollama](docs/tutorial/02-brain-ollama.md)
3. [Home Assistant in a VirtualBox VM](docs/tutorial/03-home-assistant-vm.md)
4. [Connect the brain and write the prompt](docs/tutorial/04-connect-brain-and-prompt.md)
5. [The ear: speech-to-text](docs/tutorial/05-ear-speech-to-text.md)
6. [The voice: text-to-speech](docs/tutorial/06-voice-text-to-speech.md)
7. [Bluetooth into the VM](docs/tutorial/07-bluetooth-passthrough.md) *(optional)*
8. [Lights and plugs](docs/tutorial/08-lights-and-plugs.md)
9. [Wake word and our own voice program](docs/tutorial/09-wake-word-and-voice-program.md) *(planned)*
10. [The screen](docs/tutorial/10-screen.md) *(planned)*
11. [Maintenance and troubleshooting](docs/tutorial/11-maintenance-and-troubleshooting.md)

There's also an interactive picture of the pipeline: download
[`docs/how-blood-works.html`](docs/how-blood-works.html) and open it in a browser.

## What's in this repo

```
docs/
  tutorial/            the step-by-step guide (start here)
  how-blood-works.html interactive explainer of the pipeline
prompts/               the brain's instructions, v2 → v7 (each version fixes something, see chapter 04)
tests/
  compare-brains.ps1   ask several models the same tricky questions, side by side
  questions-limits.txt the tricky questions
  test-models.ps1      the first model/temperature bench
  stt/                 speech-to-text bench: record your voice, score each engine
  tts/                 voice audition + name pronunciation test
  results/             saved bench results
tools/
  find_wiz_bulbs.py    find WiZ bulbs on your network and check they're reachable
ROADMAP.md             the working plan from here to the finish
```

The examples and prompts use the author's name (Tudor). Replace it with your
own: the assistant addresses you by name.

## Hardware it was built on
ASUS TUF Gaming A15 (Ryzen 5 4600H, **8 GB RAM**, GTX 1650 Ti **4 GB**), Windows 11,
built-in mic, speakers on the 3.5 mm jack. Any similar laptop with an NVIDIA
card should work; without one, the brain runs on the CPU and is slower.

## Budget
**€0.** Everything is free and open source, running on hardware we already owned.
Nothing needs an account or a subscription, except the phone apps your bulbs
and plugs come with, for their first setup.
