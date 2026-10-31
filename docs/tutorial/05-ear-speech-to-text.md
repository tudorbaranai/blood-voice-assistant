# 05 · The ear: speech-to-text

## Goal
Home Assistant turns your spoken sentence into text, accurately and in under a second, offline.

## Why Parakeet (through the "Whisper" add-on)
Home Assistant's **Whisper** add-on now contains several engines. For English,
`model: auto` uses **NVIDIA Parakeet**, which in my tests was **6× faster** than
Whisper "small", with about twice the word errors (still few). I measured it myself:

| Engine (add-on settings) | Word errors | Perfect sentences | Avg. wait |
|---|---|---|---|
| **Parakeet** (`model auto`, `stt_library auto`) ✅ | 8.9% | 10/15 | **0.66 s** |
| Whisper small-int8 + glossary prompt | 4.0% | 12/15 | 4.16 s |
| Whisper small-int8, beam 1 | 4.0% | 12/15 | 3.74 s |
| Whisper base-int8 + glossary prompt | 8.9% | 9/15 | 1.47 s |

*(15 recorded sentences, VM with 4 CPU cores. Whisper always processes a fixed
30-second window, so even short commands cost ~4 s on a CPU. Parakeet only
processes the actual audio.)*

Then **tuning the microphone** cut the errors far more than switching engines did (step 5).

## Steps

### 1. Install the add-on
**Settings → Add-ons** (called **Apps** in newer versions) → store → **Whisper** → Install →
- **Configuration:** Language **`en`** (`auto` detection is much slower), model `auto`, stt_library `auto`, beam_size `0`.
- **Info:** turn on **Start on boot** and **Watchdog** → **Start**.

The first start downloads the model (~1 GB of RAM in use afterwards, so give the
VM 2.5 GB, chapter 03).

### 2. Connect it to Home Assistant
**Settings → Devices & services** → a **Wyoming Protocol** card appears under
*Discovered* → **Add**. (No card? **+ Add Integration → Wyoming Protocol** →
Host `core-whisper`, Port `10300`.)

### 3. Put it in the voice assistant
**Settings → Voice assistants → your assistant → Speech-to-text:** `faster-whisper`
(that's the add-on's name, even when it runs Parakeet) → language English → Update.

### 4. Make it truly offline
After the model has downloaded once: add-on **Configuration → `local_files_only`: on**
→ Save. The add-on then never checks online for models again.

### 5. Tune the microphone (the biggest improvement)
Laptop mics often come with "effects" (noise suppression, beam-forming) that
damage speech for recognition. What worked for me (Realtek audio):
1. Windows: Settings → System → Sound → **Input** → your mic → **Volume 100**.
2. **Realtek Audio Console** → Recording Devices → Microphone Array →
   **Microphone Effects: All Off** (Acoustic Echo Cancellation off).
3. **Microphone Boost: 0 dB**. With +10 dB, my voice **clipped** (distorted) when close.

| Mic settings | Word errors (5 sentences) |
|---|---|
| volume 60, effects on (Windows default) | 14.3% |
| volume 100, effects on | 5.7% |
| volume 100, **effects off**, boost +10 dB | 2.9%, but near speech clipped |
| **volume 100, effects off, boost 0 dB** ✅ | 0% on a 2-sentence re-test; near voice ≈ −22 dB, far ≈ −31 dB |

## Check it worked
- Assist chat bubble → 🎤 → speak (the browser allows the mic on `127.0.0.1`).
- **Settings → Voice assistants → ⋮ → Debug:** *Speech-to-text* should take
  ~0.7 s, and its text should match what you said.

## Test it yourself: the speech-to-text bench (optional)
[`tests/stt/`](../../tests/stt/) measures any engine or mic setting on **your own voice**:
1. Expose the add-on port to Windows: add-on **Configuration → Network → `10300`**, then
   (`$vb` = the path to `VBoxManage.exe`, see chapter 03):
   ```powershell
   & $vb controlvm "Home Assistant" natpf1 "wyoming-stt,tcp,127.0.0.1,10300,,10300"
   ```
2. Python 3 + a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r tests\stt\requirements.txt
   ```
3. Record yourself reading [`phrases.txt`](../../tests/stt/phrases.txt) (edit it to your own commands and name):
   `.venv\Scripts\python.exe tests\stt\record.py`
4. Score the current engine: `... bench_stt.py --label parakeet`. Change the add-on settings,
   run again with another label, and compare: `... bench_stt.py --compare`.
5. Check loudness and clipping: `... audio_check.py`.

Recordings are 16 kHz mono WAV, the format the engine expects. Results go to
`tests/stt/results/`. Keep your recordings private: they're your voice.

## What went wrong for me
| Problem | Cause | Fix |
|---|---|---|
| Assistant showed Speech-to-text **"None"** | the add-on was installed, but the **Wyoming** integration wasn't added in Home Assistant | add Wyoming Protocol (step 2) |
| Bench couldn't reach the add-on | the add-on port isn't exposed by default | add-on Network `10300` + the NAT rule |
| First scores looked worse than they were | "kilometres" vs "kilometers" and "uh" counted as errors | the scoring now ignores spelling variants and fillers |
| Parakeet heard my name wrong | uncommon names are hard for any engine | the prompt doesn't need the name heard right, and the planned wake word (chapter 09) will listen for "Hey Blood" on its own |
| `python` not found right after installing it | the PowerShell window was opened before the install | open a new window |
