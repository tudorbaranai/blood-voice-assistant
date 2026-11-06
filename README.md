# Blood

An offline voice assistant that runs on my old laptop and controls my lights.

Want to build your own? Jump to [Build your own](#build-your-own).

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

Like Alexa or Google Home, but built from free, open-source parts on one Windows
laptop. Speech recognition, the AI model and the voice all run on the laptop, so
it keeps working with the internet unplugged.

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

I say **"Hey Blood"**, it answers **"Yes, Tudor?"**, and I talk. A small
program on the laptop listens all the time, starts by itself at login, and
needs no browser ([chapter 09](docs/tutorial/09-wake-word-and-voice-program.md)).
After an answer it keeps listening for 5 seconds, so I can go on without
saying "Hey Blood" again. A full-screen window, the Eclipse, comes up with it:
my words, its answer, a black sun that moves with both voices, and a hand that
grips the sun when a light goes off ([chapter 10](docs/tutorial/10-screen.md)).
I can also type to it in Home Assistant's Assist. It switches the bulb and the
plug, dims the light, changes its colour, and answers general questions. It
knows the date and the weekday, and it says so when it can't check something
live, like the weather.

Plain commands ("turn off the main light") are handled instantly by Home
Assistant's own matcher. Anything that needs understanding goes to the AI: when
I say *"I can't really read with this light"*, the bulb gets brighter after 4–5
seconds. The bench measures about 2 s of that for the brain deciding and calling
the switch; the rest is speech-to-text, Home Assistant and the voice.

## How well it works

All numbers are measured on the laptop below, with the scripts in [`tests/`](tests/).

**Brain.** [`tests/blood_bench.py`](tests/blood_bench.py) sends 56 commands and
questions to the brain the way Home Assistant 2026.10.1 does, copied as closely
as I could (its hidden instructions and its light-control tools), runs the tool
calls against a pretend house,
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
catches. In November I added 14 harder cases and prompt v13; those runs are in
[the results summary](tests/results/README.md).

**Wake word.** My own "Hey Blood" model, trained on computer voices only (v1),
on recordings of me it never trained on:

| Where I said it | Heard |
|---|---|
| At the desk | 10/12 |
| From the bed | 3/12 |
| Across the room | 3/12 |
| Normal talk (false wake-ups) | 0/12 |

Fine up close, poor at a distance. Retraining with my own recordings went
wrong the first time (v2: worse everywhere) and taught me how the training
cuts clips; the fixed version is ready to run
([chapter 09](docs/tutorial/09-wake-word-and-voice-program.md#part-2--teach-it-your-own-voice-and-test-it-honestly)).

**Whole conversation.** From the end of my sentence to Blood's answer: about
1.5–3 s for most requests, about 1 s when Home Assistant matches the sentence
itself. The first version took 12–18 s; [why](docs/tutorial/09-wake-word-and-voice-program.md#making-it-fast).

**Ear.** On the same 15 recorded sentences (recorded before I tuned the mic),
Parakeet took about 0.7 s each with 9% word errors. Whisper small made fewer mistakes (4%) but took about 4 s, too
slow for a conversation. [Results](tests/stt/results/summary.csv).

**Voice.** I auditioned 14 Piper voices. Some sounded very polished, but speed
came first: if the answer takes too long, I might as well search Google myself.
"Medium" voices start speaking in about 0.2 s, and I picked a cheerful, almost
happy one.

## Known limitations

- **Hints are unreliable.** 1 of 4 on the bench: it sometimes promises "I'll
  turn on the lights" without doing it.
- **The wake word is weak at a distance** (3/12 from the bed). It works best
  said clearly, with a strong "H".
- **Short memory.** The brain holds about 4,000 tokens, instructions
  included, so Blood starts a fresh conversation after 6 questions in a row.
  Past that, it forgot my devices and took ~29 s per answer.
- **Two actions in one sentence can be half done.** "Make it brighter and
  blue" changed only the brightness, but Blood said both were done. One action
  per sentence works.
- **Training the wake word needs Google Colab** (free, but online, a few GPU
  hours a day, and the notebook needed eight fixes in late 2026). The finished
  model runs offline.
- **English only.** The voice can only pronounce English.
- **The router has to stay on.** The internet can be off, but the Wi-Fi bulb
  and plug reach the laptop through the router.
- **Tested on one room with one bulb and one plug.** Every exposed device is
  added to each request, so a bigger home means a longer prompt for a small
  model. I haven't measured how it copes.
- **The GPU is shared.** `blood-brain` takes ~3.4 of the 4 GB, so for games
  Ollama has to be stopped, and Blood can't answer until it's started again.
- **Windows only as written** (VirtualBox, PowerShell). If you pass Bluetooth
  into the VM ([chapter 07](docs/tutorial/07-bluetooth-passthrough.md)),
  Windows loses Bluetooth while the VM runs.

## The system prompt: the part that mattered most

The model is small (4 billion parameters) and its biggest problem is
hallucination: inventing facts, or saying it switched a light it never touched.
The system prompt, the instructions it gets before every question, turned out to
control that more than anything else. I rewrote it thirteen times
([every version](prompts/)). A single rewrite (v5 → v6) took my ten trick
questions from about 4/10 to 7.5/10, same model, same laptop. What I learned:

- **Put the names in.** My name and Blood's name (and how it gets misheard:
  "Blood" or "Blud") are written in the prompt. Home Assistant adds the list of
  devices and rooms by itself, so the names you give them there matter as much.
- **Give devices short, unique names.** Mine are "Main light" and "Bed lights".
  Vague, descriptive names like "big light" confused it; a plain name that
  sounds like nothing else works best.
- **Longer doesn't automatically mean better.** Mine grew from 35 to 67 lines,
  and the longest, v12, scored best, but only because each added line fixed a
  failure the bench had caught. Every line also costs memory and time on a
  4 GB card, so a line that doesn't fix something measurable doesn't go in.
- **It copies the examples.** An early version answered "The ceiling light is
  on." straight from an example, without touching anything. Examples now come
  with "these only show the style, never repeat them word for word".
- **One example beats a paragraph of rules.** A rule didn't stop it guessing
  what weekday Christmas falls on. One example did.
- **Test what you didn't tell it.** The bench asks for a TV, a garage light and a
  front-door lock that don't exist, and for the "famous Romanian scientist Ion
  Blodescu, who invented the toaster". The prompt never mentions any of them;
  Blood has to work out on its own that it can't, or doesn't know.

## How it came together

From the first model test on 5 October to "Hey Blood" in November, with the lessons about
prompt caching, wake-word training, context size and the mic along the way:
[the timeline and what I learned](docs/how-it-came-together.md).

I built this with Claude Code as a pair programmer; the decisions, testing and
hardware are mine.

## Build your own

> **Before you start**
> - **A Windows 10/11 laptop that can stay on**, ideally with an NVIDIA card
>   (4 GB or more). The steps use PowerShell and VirtualBox, so they're
>   Windows-only as written.
> - **About 40 GB of free disk**: ~32 GB for the Home Assistant VM, ~3.3 GB for
>   the AI model.
> - **To download:** this repo (*Code → Download ZIP*, or `git clone`),
>   [Ollama](https://ollama.com/download), [VirtualBox](https://www.virtualbox.org/wiki/Downloads),
>   and [Python 3.9+](https://www.python.org/downloads/) for the benches.
> - **Accounts, only during setup:** the bulb's and plug's phone apps (WiZ,
>   Smart Life) to put them on your Wi-Fi, the same Smart Life login once more
>   so Home Assistant can fetch the plug's local key, and a GitHub login for
>   HACS, the community store Tuya Local comes from. After setup, Blood
>   doesn't use any of them.

The tutorial walks through everything in order. Each chapter follows the same
shape: *Goal → Why → Steps → Check it worked → What went wrong for me.*

0. [Overview and the big decisions](docs/tutorial/00-overview.md)
1. [Prepare the laptop for 24/7](docs/tutorial/01-laptop-24-7.md)
2. [The brain: Ollama](docs/tutorial/02-brain-ollama.md)
3. [Home Assistant in a VirtualBox VM](docs/tutorial/03-home-assistant-vm.md)
4. [Connect the brain and write the prompt](docs/tutorial/04-connect-brain-and-prompt.md)
5. [The ear: speech-to-text](docs/tutorial/05-ear-speech-to-text.md)
6. [The voice: text-to-speech](docs/tutorial/06-voice-text-to-speech.md)
7. [Bluetooth into the VM](docs/tutorial/07-bluetooth-passthrough.md) *(optional)*
8. [Lights and plugs](docs/tutorial/08-lights-and-plugs.md)
9. [Wake word and my own voice program](docs/tutorial/09-wake-word-and-voice-program.md): training on Colab with every fix, your own voice, the program, auto-start
10. [The screen](docs/tutorial/10-screen.md): the Eclipse design, how its God Hand was made in Blender, and the wiring
11. [Maintenance and troubleshooting](docs/tutorial/11-maintenance-and-troubleshooting.md)

To run the brain bench against your own Ollama (Python 3.9+, no extra
packages), from the repo folder:

```powershell
ollama pull qwen3:4b-instruct
ollama create blood-brain -f tools\blood-brain.Modelfile
python tests\blood_bench.py --model blood-brain --prompt prompts\prompt_v13_devices.txt --label my-run
python tests\blood_bench.py --compare
```

The prompts use my name (Tudor). Replace it with yours: Blood addresses you by name.

## What's in this repo

```
docs/tutorial/           the step-by-step guide
blood/                   the voice program
  blood.py               wake word → "Yes, Tudor?" → record → Home Assistant → speak
  ha.py, speak.py        Home Assistant's ear and brain; the voice, with text cleaning
  settings.toml          everything you might tune, in one place
  record_wake.py         record your own wake-word clips, hands-free
  pack_voice.py          split them into training clips and a held-back test set
  wake_test.py           live mic test: the score of every attempt
  wake_eval.py           score a model on your recordings (--holdout: only the held-back ones)
  colab_train_v3.sh      train "Hey Blood" on Colab with your clips (v2: the version that went wrong)
  screen.py              the full-screen window: Edge in kiosk mode, fed live over a websocket
  screen_live.js         plugs a design page into it (screen.html: the plain fallback orb)
  screen_designs.html    five early design candidates
docs/design/manga-v3/    the chosen screen: the Eclipse page, its storyboard, the Blender scripts for the hand
prompts/                 every version of Blood's instructions, v2 → v13
tests/
  blood_bench.py         the brain bench: 70 cases, pretend house, lie detector
  blood_bench_cases.json the test sentences and the pretend devices
  compare-brains.ps1     early side-by-side test of several models on trick questions
  questions-limits.txt   the trick questions
  test-models.ps1        the very first model and temperature test
  stt/                   speech-to-text bench on your own recorded voice
  tts/                   voice audition and name-pronunciation test
  results/               every saved bench run, summarised in its README
tools/
  blood-brain.Modelfile  Ollama settings Home Assistant can't set (GPU layers, answer cap)
  blood-restart.cmd      restart the background voice program after changing its settings
  find_wiz_bulbs.py      find WiZ bulbs on the network
```

## Hardware and cost

ASUS TUF Gaming A15: Ryzen 5 4600H, **8 GB RAM**, GTX 1650 Ti with **4 GB**,
Windows 11. Built-in mic, speakers on the 3.5 mm jack. Any similar laptop with
an NVIDIA card should work; without one, the brain runs on the CPU and is slower.

**Cost: €0.** Everything is free software on hardware I already had. The
accounts it needs are only for setup (see *Before you start*).

"Offline" means no internet. The Wi-Fi bulb and plug still reach the laptop
through the router, so the router has to stay on.
([why](docs/tutorial/00-overview.md#what-fully-offline-means-here-read-this-it-matters))

## What's next

The core works and Blood now listens on its own. Next on the list:

- **wake word v3**, trained with my own clips cut the right way, to hear me from
  the bed and across the room
- **the screen**: more moments, like its own animation for a light turning
  on (now only "off" has the hand)
- **automations**, the thing I wanted in the first place

## License

[MIT](LICENSE). [`tests/blood_bench.py`](tests/blood_bench.py) quotes the
instructions Home Assistant sends to the model, from Home Assistant's source
code (Apache 2.0).
