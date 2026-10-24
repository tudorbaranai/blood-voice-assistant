# 00 · Overview: what we're building and why it's built this way

**Blood** is a home voice assistant, like Google Home or Alexa, except that:

- it costs **€0** (only hardware you already own),
- it runs **fully offline**: your voice, the "brain" and the answers never leave your home,
- every piece is open source and replaceable.

You say *"Hey Blood"*, it answers *"Yes?"*, you ask a question or give a command
("turn off the bedroom light"), and it answers through your speakers.

> The project started under the name "Jarvis", which is why the folder and some
> files still use that name.

---

## The pipeline: what happens when you speak

```
 🎤 mic ─▶ [1 wake word] ─▶ [2 ear: speech → text] ─▶ [3 brain: think] ─▶ [4 voice: text → speech] ─▶ 🔊 speakers
                                                          │
                                                          ▼
                                                [5 home: lights, plugs]
```

| # | Job | What we use | Where it runs |
|---|---|---|---|
| 1 | Hear "Hey Blood" | openWakeWord, custom model *(planned, chapter 09)* | Windows, our own small program |
| 2 | **Ear**: speech → text | **Parakeet** (via Home Assistant's Whisper add-on) | Home Assistant VM |
| 3 | **Brain**: understand and answer | **Ollama** + `qwen3:4b-instruct`, with our own instructions ("prompt") | Windows, on the graphics card |
| 4 | **Voice**: text → speech | **Piper**, voice `en_US-libritts_r-medium` | Home Assistant VM |
| 5 | Control devices | **Home Assistant** integrations (WiZ, Tuya, …) | Home Assistant VM |
| – | Glue that connects 2–5 | Home Assistant **Assist** voice pipeline | Home Assistant VM |

Home Assistant is the conductor. It already knows how to talk to thousands of
devices and has a ready-made voice pipeline, so we only build the parts it
doesn't have: the wake word on Windows, the personality, and later the screen.

An interactive picture of the whole flow: open [`docs/how-blood-works.html`](../how-blood-works.html) in a browser.

---

## The hardware

Everything runs on **one Windows laptop** that stays on 24/7:

| Part | Ours | Minimum that should work |
|---|---|---|
| CPU | AMD Ryzen 5 4600H (6 cores) | any 4+ core x86-64 from the last ~6 years |
| RAM | 8 GB | 8 GB (tight; 16 GB is comfortable) |
| Graphics card | NVIDIA GTX 1650 Ti, 4 GB | NVIDIA with 4+ GB (without one, the brain runs on the CPU and is slower) |
| OS | Windows 11 Pro | Windows 10/11 (Home works too) |
| Mic | the laptop's built-in mic | built-in is fine for a small room |
| Speakers | any speakers on the 3.5 mm jack | any |
| Devices | one WiZ Wi-Fi bulb, one LSC (Tuya) Wi-Fi plug | anything Home Assistant supports |

The laptop is still usable for normal things while Blood runs.

---

## What "fully offline" means here (read this, it matters)

**Offline = no internet needed.** It does **not** mean "no network at all".

```
 ┌──────────────── YOUR HOME (all local) ─────────────────┐
 │                                                        │
 │   Laptop (Blood)  ◀── Wi-Fi ──▶  YOUR ROUTER           │
 │                                  (must be ON)  ──✂──── 🌍 internet
 │                                   ▲       ▲            │   (can be OFF)
 │                           Wi-Fi ──┘       └── Wi-Fi    │
 │                             │                 │        │
 │                        Wi-Fi bulb        Wi-Fi plug    │
 └────────────────────────────────────────────────────────┘
```

- The wake word, ear, brain and voice all run on the laptop. ✅ No internet.
- **Wi-Fi** bulbs and plugs talk to the laptop **through your router**, like
  letters through a post office. The router must be powered on. The internet
  connection can be unplugged and everything keeps working.
- **Bluetooth** or **Zigbee** devices talk to the laptop directly by radio, with
  no router at all. That's the option if you want to be independent even of
  the router.
- Phone apps (WiZ app, Google Home, …) use the cloud, so *they* stop working
  without internet. Blood doesn't.

---

## Why it's built this way (the big decisions)

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Overall approach | Home Assistant + small custom programs | **Everything custom in Python**: would mean re-writing device control for every brand. **A DIY ESP32 speaker**: costs money for parts. |
| Brain | **Ollama**, local model | **Cloud AI** (ChatGPT, Claude, Gemini): not offline, may cost money. |
| Where Home Assistant runs | **A virtual machine (VM) on the same laptop** | **A separate mini-PC or Raspberry Pi**: costs money (fine later, it can be moved with a backup). |
| VM vs. Docker | **VM with Home Assistant OS** | **Docker on Windows**: no add-on store, Bluetooth and network discovery don't reach the container. |
| Which VM software | **VirtualBox** | **Hyper-V**: built into Windows, but [Home Assistant says it has no USB support](https://www.home-assistant.io/installation/windows/), so the laptop's Bluetooth couldn't be passed in. |
| VM network | **NAT + port forwarding** | **Bridged over Wi-Fi**: the default in Home Assistant's guide, but it was unreliable on our Realtek Wi-Fi (setup got stuck). |
| Model | **`qwen3:4b-instruct`** | **`qwen3:1.7b`**: fastest but made up facts. **`qwen3:4b` / `-thinking`**: smartest, but 10–200 s per answer, far too slow for voice. |
| Ear | **Parakeet** | **Whisper small**: slightly more accurate but ~4 s per sentence vs. ~0.7 s. |
| Voice | **Piper** `en_US-libritts_r-medium` | 14 voices auditioned; this one sounded most natural to us. |

Each chapter explains its own decision in more detail.

---

## The chapters

| # | Chapter | Status |
|---|---|---|
| 00 | Overview (this page) | ✅ |
| 01 | [Prepare the laptop for 24/7](01-laptop-24-7.md) | ✅ |
| 02 | [The brain: Ollama](02-brain-ollama.md) | ✅ |
| 03 | [Home Assistant in a VirtualBox VM](03-home-assistant-vm.md) | ✅ |
| 04 | [Connect the brain and write the prompt](04-connect-brain-and-prompt.md) | ✅ |
| 05 | [The ear: speech-to-text](05-ear-speech-to-text.md) | ✅ |
| 06 | [The voice: text-to-speech](06-voice-text-to-speech.md) | ✅ |
| 07 | [Bluetooth into the VM](07-bluetooth-passthrough.md) | ✅ (optional) |
| 08 | [Lights and plugs](08-lights-and-plugs.md) | 🟡 bulb + plug done, voice control next |
| 09 | [Wake word and our own voice program](09-wake-word-and-voice-program.md) | ⬜ planned |
| 10 | [The screen](10-screen.md) | ⬜ planned |
| 11 | [Maintenance and troubleshooting](11-maintenance-and-troubleshooting.md) | ✅ (grows over time) |

Every chapter follows the same shape: **Goal → Why → Steps → Check it worked →
What went wrong for us.** The last part is often the most useful one.
