# 06 · The voice: text-to-speech

## Goal
Blood's answers are spoken in a natural voice, starting almost instantly, offline.

## Why Piper
Free, offline, fast on a CPU, and available as a Home Assistant add-on. It
**streams** sentence by sentence, so you only wait for the first sentence.
"Medium" voices start talking in **~0.2 s**; "high" voices take ~0.9 s and we
couldn't hear the difference.

## Steps

### 1. Install the add-on
**Settings → Add-ons/Apps** → store → **Piper** → Install →
- **Configuration:** pick any voice for now (you choose properly in step 3).
  Leave `backend` on **piper** (the experimental alternative is slower).
- **Info:** **Start on boot** + **Watchdog** → **Start**.

### 2. Connect it to Home Assistant
**Settings → Devices & services** → *Discovered:* **Wyoming Protocol** (Piper) → **Add**.

### 3. Choose the voice in the assistant
**Settings → Voice assistants → your assistant → Text-to-speech: piper** →
language **English (United States)** → **Voice** → Update. Each voice downloads into
the VM the first time it's used. Our choice: **`en_US-libritts_r-medium`**.

## Choosing a voice: the audition script (optional)
[`tests/tts/tts_audition.py`](../../tests/tts/tts_audition.py) makes several
voices say the same sentences, saves a WAV per voice to listen to, and measures
how fast each one starts.

1. Expose the add-on port: add-on **Configuration → Network → `10200`**, then
   (`$vb` = the path to `VBoxManage.exe`, see chapter 03):
   ```powershell
   & $vb controlvm "Home Assistant" natpf1 "wyoming-tts,tcp,127.0.0.1,10200,,10200"
   ```
2. Run it (Python venv from chapter 05):
   ```powershell
   .venv\Scripts\python.exe tests\tts\tts_audition.py                          # default list
   .venv\Scripts\python.exe tests\tts\tts_audition.py en_US-ryan-medium en_GB-alan-medium
   ```
3. Listen to `tests/tts/voices/*.wav`.

What we measured (first sound / speed vs real time):
| Voice | First sound | Speed |
|---|---|---|
| `en_GB-northern_english_male-medium` | 0.15 s | 12× |
| `en_US-ryan-medium` | 0.16 s | 11× |
| `en_GB-alan-medium` | 0.19 s | 13× |
| `en_US-ryan-high`, `en_US-lessac-high`, `en_GB-cori-high` | 0.8–0.9 s | 2.3–2.4× |

We auditioned 14 voices and finally picked **`en_US-libritts_r-medium`**, a
multi-speaker voice (default speaker) that sounded the most natural and cheerful to us. Taste matters here, so try a few.

## Making it say your name right
Voices read names with English rules, so names from other languages often come
out wrong. Piper accepts **phonemes** (exact sounds) between `[[ ]]`.
[`tests/tts/name_test.py`](../../tests/tts/name_test.py) generates several
spellings and phoneme versions, so you can pick the one that sounds right. Edit
the list to your own name and run:
```powershell
.venv\Scripts\python.exe tests\tts\name_test.py en_US-libritts_r-medium
```
Listen to `tests/tts/names/`. In our case the phoneme version
`[[ tˈuːdoːɾ ]]` came closest. The voice program (chapter 09) will swap the
name for its phonemes just before speaking, while the screen still shows the
normal spelling.

## Check it worked
Assist chat bubble → 🎤 → ask something. You hear the answer. In **Debug**,
*Text-to-speech* shows `tts.piper` with your voice, and near-zero time thanks to streaming.

## The first full round trip
With the ear, brain and voice connected, our first spoken question showed:
speech-to-text **0.73 s**, brain **4.06 s**, voice **~0 s** (streaming). The slow
brain step led to the prompt-cache fix in chapter 04 (clock at the end of the prompt).

## What went wrong for us
| Problem | Cause | Fix |
|---|---|---|
| The first voice in the audition looked slow | it included the download and warm-up | re-run: 0.19 s |
| No voice said our name right | English letter-to-sound rules | phonemes (above) |
| The add-on's documentation page wouldn't load (HTTP 503) | a temporary GitHub hiccup | the add-on changelog lists the options too |
