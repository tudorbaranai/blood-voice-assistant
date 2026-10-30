# Blood: an offline voice assistant on an old gaming laptop

Blood is a home voice assistant like Alexa or Google Home, built from free,
open-source parts on one Windows laptop. It answers questions and controls my
bedroom lights, and it keeps working with the internet unplugged: speech
recognition, the AI model and the voice all run on the laptop.

<!-- DEMO: a 20–30 s clip goes here (ask a question, then "I can't really read
     with this light" and the bulb gets brighter). Upload it by dragging the .mp4
     into README.md in GitHub's web editor. -->

## Why I built this

My lights and plugs were already set up in Google Home, and I wanted to write my
own automations for them. Google Home wouldn't let me: there's no local way for
your own code to control devices through it. Looking for alternatives, I found
[Home Assistant](https://www.home-assistant.io/) and the people using it to run
their homes themselves. Once the lights were in Home Assistant, adding a voice
and a local AI on top was the obvious next step.

## How it works

```
mic ─▶ speech → text ─▶ local AI ─▶ text → speech ─▶ speakers
                           │
                           ▼
                  Wi-Fi bulb · Wi-Fi plug
```

| Piece | Built with |
|---|---|
| Glue + device control | [Home Assistant OS](https://www.home-assistant.io/) in a VirtualBox VM |
| Brain | [Ollama](https://ollama.com/) running `qwen3:4b-instruct` on the GPU, tuned as [`blood-brain`](tools/blood-brain.Modelfile) |
| Speech → text | Parakeet, through Home Assistant's Whisper add-on |
| Text → speech | [Piper](https://github.com/rhasspy/piper), voice `en_US-libritts_r-medium` (default speaker) |
| Devices | a WiZ Wi-Fi bulb and an LSC (Tuya) Wi-Fi plug, both controlled locally |

## What it can do

I talk to Blood through Home Assistant's Assist, by voice from the browser or by
typing. It switches the bulb and the plug, dims the light, changes its colour,
and answers general questions. It knows the date and the weekday, and it says so
when it can't check something live, like the weather.

Plain commands ("turn off the main light") are handled instantly by Home
Assistant's own matcher. Anything that needs understanding goes to the AI: when
I say *"I can't really read with this light"*, it thinks for 4–5 seconds and
turns the bulb up.

## How well it works

All numbers are measured on the laptop below, with the scripts in [`tests/`](tests/).

**Brain.** [`tests/blood_bench.py`](tests/blood_bench.py) sends 56 commands and
questions to the brain exactly the way Home Assistant 2026.10.1 does (same
hidden instructions, same tools), runs the tool calls against a pretend house,
and grades the answers. Its most important check is a lie detector: if Blood
says "the light is on" but no switch was actually called, the test fails.

Latest run ([full results](tests/results/bench-v12-blood-brain-2026-10-24_22-47.md)):
**52 of 56 passed, 1.4 s average answer, 3.2 s worst.**

| Category | Passed |
|---|---|
| Switching devices on/off | 11/11 |
| Other names for a device ("the ceiling light") | 2/2 |
| Unclear target ("turn on the light") | 1/1 |
| Brightness and colour | 4/4 |
| "Is the light on?" | 6/6 |
| Devices that don't exist ("turn on the TV") | 5/5 |
| Several devices at once | 3/3 |
| General knowledge | 19/20 |
| Hints instead of commands ("it's too dark in here") | 1/4 |

Hints are the weak spot. The one I use works at home, but on other phrasings,
like "I can't see anything, it's so dark", it replies "I'll turn on the lights
for you" without calling the switch. Those three answers are the lies the bench
catches.

**Ear.** On the same 15 recorded sentences, Parakeet took about 0.7 s each with
9% word errors. Whisper small made fewer mistakes (4%) but took about 4 s, too
slow for a conversation. [Results](tests/stt/results/summary.csv).

**Voice.** I auditioned 14 Piper voices. Some sounded very polished, but speed
came first: if the answer takes too long, I might as well search Google myself.
"Medium" voices start speaking in about 0.2 s, and I picked a cheerful, almost
happy one.

## The system prompt: the part that mattered most

The model is small (4 billion parameters) and its biggest problem is
hallucination: inventing facts, or saying it switched a light it never touched.
The system prompt, the instructions it gets before every question, turned out to
control that more than anything else. I rewrote it twelve times
([every version](prompts/)). A single rewrite (v5 → v6) took my ten trick
questions from about 4/10 to 7.5/10, same model, same laptop. What I learned:

- **Put the names in.** My name, Blood's name (and how it gets misheard:
  "Blood" or "Blud"), and the exact name of every device and room.
- **Give devices short, unique names.** Mine are "Main light" and "Bed lights".
  Vague, descriptive names like "big light" confused it; a plain name that
  sounds like nothing else works best.
- **Keep it medium-length.** Mine stayed between 35 and 67 lines. Every line
  takes memory on a 4 GB card, and a longer prompt made it hallucinate more,
  not less.
- **It copies the examples.** An early version answered "The ceiling light is
  on." straight from an example, without touching anything. Examples now come
  with "these only show the style, never repeat them word for word".
- **One example beats a paragraph of rules.** A rule didn't stop it guessing
  what weekday Christmas falls on. One example did.
- **Test what you didn't tell it.** The bench asks for a TV, a garage light and a
  front-door lock that don't exist, and for the "famous Romanian scientist Ion
  Blodescu, who invented the toaster". The prompt never mentions any of them;
  Blood has to work out on its own that it can't, or doesn't know.

## Other things I learned

- **Anything that changes goes at the end of the prompt.** Ollama reuses the
  start of a prompt between questions, up to the first character that differs.
  With the clock (to the minute) at the top, the whole prompt was re-read on
  every question: 4–7 s per answer. Moving it to the bottom fixed it.
  ([chapter 04](docs/tutorial/04-connect-brain-and-prompt.md))
- **Home Assistant quietly overrides the context size.** It asks Ollama for
  8192 tokens, which pushed 36% of the model onto the slow CPU. Setting 4096
  brought that to 27%, and forcing every layer onto the 4 GB GPU took the
  average answer from 3.4 s to 1.4 s with the same prompt.
- **Small and fast isn't enough.** `qwen3:1.7b` answered in under a second but
  happily described the made-up toaster scientist. The "thinking" models were
  smarter but took 11–235 s. `llama3.2:3b` just wasn't my style.
  `qwen3:4b-instruct` was the middle: not brilliant, honest, under 2 s.
  ([chapter 02](docs/tutorial/02-brain-ollama.md))
- **Tuning the mic beat switching engines.** Mic volume to 100, Realtek
  "effects" off and boost at 0 dB took word errors on my test sentences from 14%
  to near zero, a bigger gain than any model change.
  ([chapter 05](docs/tutorial/05-ear-speech-to-text.md))

## How it came together

| When (2026) | What happened |
|---|---|
| 5 Oct | Tried local models on my everyday laptop. Qwen felt better than Llama. |
| 6–8 Oct | Set up the Asus to run 24/7 and installed Home Assistant OS in a VM on it. The first install hung at 5% for half an hour; switching the VM's network from bridged to NAT fixed it. |
| 9–12 Oct | Benchmarked models and moved from `qwen3:1.7b` to `qwen3:4b-instruct`. Chose the ear and the voice, tuned the mic. |
| 13 Oct | First light switched by Home Assistant. Surprise: the bulb I thought was a Philips Hue was a WiZ, so the Bluetooth setup I'd just done wasn't needed. |
| 24 Oct | Smart plug working locally (installed by hand, because the community store's GitHub login was broken). Built the bench with the lie detector, prompts v8 → v12, all layers on the GPU. |

I built this with Claude Code as a pair programmer; the decisions, testing and
hardware are mine.

## Build your own

The tutorial walks through everything in order. Each chapter follows the same
shape: *Goal → Why → Steps → Check it worked → What went wrong for us.*

0. [Overview and the big decisions](docs/tutorial/00-overview.md)
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

To run the brain bench against your own Ollama (Python 3, no extra packages):

```powershell
python tests/blood_bench.py --model blood-brain --prompt prompts/prompt_v12_devices.txt --label my-run
python tests/blood_bench.py --compare
```

The prompts use my name (Tudor). Replace it with yours: Blood addresses you by name.

## What's in this repo

```
docs/
  tutorial/              the step-by-step guide
  how-blood-works.html   interactive diagram of the pipeline (download and open)
prompts/                 every version of Blood's instructions, v2 → v12
tests/
  blood_bench.py         the brain bench: 56 cases, pretend house, lie detector
  blood_bench_cases.json the test sentences and the pretend devices
  compare-brains.ps1     early side-by-side test of several models
  stt/                   speech-to-text bench on your own recorded voice
  tts/                   voice audition and name-pronunciation test
  results/               every saved bench run
tools/
  blood-brain.Modelfile  Ollama settings Home Assistant can't set (GPU layers, answer cap)
  gaming-mode.cmd        stop Blood to free the GPU and RAM for games
  blood-mode.cmd         start it again and preload the brain
  find_wiz_bulbs.py      find WiZ bulbs on the network
ROADMAP.md               the working plan
```

## Hardware and cost

ASUS TUF Gaming A15: Ryzen 5 4600H, **8 GB RAM**, GTX 1650 Ti with **4 GB**,
Windows 11. Built-in mic, speakers on the 3.5 mm jack. Any similar laptop with
an NVIDIA card should work; without one, the brain runs on the CPU and is slower.

**Cost: €0.** Everything is free software on hardware I already had. The only
accounts needed are the bulb and plug apps, once, for their first Wi-Fi setup.

"Offline" means no internet. The Wi-Fi bulb and plug still reach the laptop
through the router, so the router has to stay on.
([why](docs/tutorial/00-overview.md#what-fully-offline-means-here-read-this-it-matters))

## What's next

The project is paused for now, with the core working. Next on the list:

- a **"Hey Blood" wake word** and a small Windows program that listens and speaks
  on its own, so no browser is needed ([plan](docs/tutorial/09-wake-word-and-voice-program.md))
- **my own interface**, designed for my home instead of Home Assistant's default
  dashboard
- **automations**, the thing I wanted in the first place
