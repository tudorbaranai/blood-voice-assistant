# 09 · Wake word and my own voice program

## Goal
Say **"Hey Blood"** → hear **"Yes, Tudor?"** → speak → hear the answer on the
speakers. No browser, no clicking. It starts by itself when the laptop starts.

```
mic → [wake word "Hey Blood"] → "Yes, Tudor?" → record until you stop talking
    → Home Assistant's ear (speech → text) → tidy the text → Blood's brain
    → clean the answer → Piper speaks it → speakers
```

This chapter has four parts:
1. [Train the wake word](#part-1--train-the-wake-word-google-colab) (Google Colab, free, ~2 h)
2. [Teach it your own voice](#part-2--teach-it-your-own-voice-and-test-it-honestly) (and test it honestly)
3. [The voice program](#part-3--the-voice-program-blood) (`blood/`)
4. [Start it by itself at login](#part-4--start-it-by-itself-at-login)

## Why my own program, instead of letting Home Assistant do everything
Home Assistant runs inside the VM and can't use the Windows mic and speakers.
So a small Python program on Windows does the "mouth and ears" part, and also
gives me control at code level:
- **Guaranteed clean speech:** strip characters the voice can't read (the model
  sometimes adds Korean letters or emojis, see chapter 04).
- **Names pronounced right:** the voice reads names with English rules, so the
  program swaps my name for a sound spelling just before speaking. The screen
  still shows the normal spelling.
- **Speed tricks** Home Assistant can't do on its own (Part 3).

---

## Part 1 · Train the wake word (Google Colab)

### What a wake word model is
A tiny neural network (~200 KB, about 50,000 numbers) that listens to the last
1.3 seconds of sound, every 80 ms, and answers one question: *"was that 'Hey
Blood'?"* as a score from 0 to 1. It doesn't understand words; it's a pattern
detector. It runs on the CPU at 1–3%.

There's no ready-made "Hey Blood", so I trained one with
[openWakeWord](https://github.com/dscripka/openWakeWord). Its training notebook
does everything:

| Step | What happens |
|---|---|
| Fake voices | Piper says "hey blood" **thousands of times** in hundreds of voices, speeds and tones. It also makes look-alike phrases ("hey bud", "hey love") labelled **NO**. |
| Noise + echo | each clip is mixed with random background sound (music, street, TV) and the echo of a random room, so it learns the phrase in messy real life |
| Fingerprints | Google's ready-made speech model turns every clip into numbers; the small model only learns from those |
| Training | the small model sees the YES and NO fingerprints thousands of times, plus 2,000 hours of random audio as NO (that's what stops it waking up on TV) |

Only the **training** uses Google's computers. The finished `.onnx` file runs
offline on the laptop forever.

### Steps
1. Open the **simple training notebook** from the openWakeWord README
   (*"Training New Models"* → the Colab link). Sign in with a Google account.
   **Don't** grant it Google Drive access; it isn't needed.
2. **Runtime → Change runtime type → T4 GPU.** Without a graphics card the
   training takes many hours.
3. **Before running anything, add a new code cell at the top** with these
   fixes and run it (why each one: see the table below):
   ```
   !pip install -q piper-phonemize-fix pyarrow==20.0.0 && apt-get -qq install -y git-lfs > /dev/null && git lfs install && echo SETUP-OK
   %env TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
   ```
4. Run the notebook's **step 1** (installs) → then **Runtime → Restart session**.
   Run the `%env` line again after every restart.
5. Run **step 2** (downloads the noise, music and room-echo data). Then fix the
   room-echo files, which arrive as empty placeholders:
   ```
   !cd MIT_environmental_impulse_responses && git lfs pull && cd .. && rm -rf mit_rirs
   ```
   and run step 2 again so it rebuilds `mit_rirs` from the real files.
6. Fix the audio library the notebook uses (it calls functions newer
   `torchaudio` removed). Run this in a new cell; it edits the file without
   importing it, because importing it is what crashes:
   ```python
   import os, importlib.util
   p = os.path.join(importlib.util.find_spec("torch_audiomentations").submodule_search_locations[0], "utils", "io.py")
   s = open(p).read()
   s = s.replace('torchaudio.set_audio_backend("soundfile")', "pass")
   s = s.replace("torchaudio.info(file_path)",
                 "__import__('types').SimpleNamespace(num_frames=__import__('soundfile').info(str(file_path)).frames,"
                 " sample_rate=__import__('soundfile').info(str(file_path)).samplerate)")
   open(p, "w").write(s)
   print("patched", p)
   ```
7. In **step 3**, set the target word and the size, then run it:

   | Setting | Notebook example | What I used | Why |
   |---|---|---|---|
   | `target_word` | — | `hey blood` | lower case, no punctuation; it also catches "hey blud" |
   | `number_of_examples` | 1,000 | **10,000** | the notebook's own note says at least 20,000 for a good model; 1,000 is a quick test |
   | `number_of_training_steps` | 10,000 | **20,000** | |
   | `false_activation_penalty` | 1,500 | 1,500 | higher = fewer false wake-ups, more misses |

8. When it finishes, the model may be split into **two files**, `hey_blood.onnx`
   plus `hey_blood.onnx.data`. Merge them into one before downloading,
   otherwise the `.onnx` alone won't load:
   ```
   !python -c "import onnx; m=onnx.load('my_custom_model/hey_blood.onnx'); onnx.save(m,'hey_blood.onnx'); print('MERGED')"
   ```
   Then download it (`from google.colab import files; files.download('hey_blood.onnx')`)
   and put it in `models\` in this repo's folder (git-ignored).
9. **Runtime → Disconnect and delete runtime** when you're done.

The whole run took me about 2–2.5 hours: ~20 min setup and downloads, the
fake voices, ~50 min of noise and echo, ~20 min of training.

### Check it worked
On the laptop (Python venv from chapter 05):
```powershell
.venv\Scripts\python.exe -m pip install -r blood\requirements.txt
.venv\Scripts\python.exe blood\wake_test.py --model models\hey_blood.onnx --threshold 0.2
```
Say "Hey Blood" a few times. Every attempt prints its peak score and
`HIT`/`miss`, so you see near-misses too. Also watch for hits when you
*didn't* say it.

### What went wrong for me (Colab, October–November 2026)
Colab moved to Python 3.13 and PyTorch 2.11, and the notebook hadn't caught up.
Every row cost me at least one restart:

| Problem | Cause | Fix |
|---|---|---|
| `piper-phonemize` won't install | no version for Python 3.13 | `pip install piper-phonemize-fix` (same thing, built for 3.13; I checked PyPI: `piper-phonemize-cross` doesn't exist) |
| Generating the fake voices fails while loading the voice model (`weights_only`) | PyTorch 2.6+ refuses to load older model files by default | `%env TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` (run it again after every restart) |
| Errors from `datasets`/`pyarrow` in step 2 | the notebook installs `datasets 2.14.6`, which doesn't work with the newest `pyarrow` | `pip install pyarrow==20.0.0`, then restart |
| `numpy` error about `ufunc` / `__module__` | step 1 replaced libraries that were already loaded | **Runtime → Restart session** after the installs; delete half-downloaded folders (`mit_rirs`, `audioset_16k`, `fma`) and run step 2 again |
| Room-echo files are tiny and won't open | the MIT dataset stores them with Git LFS; without it you only get placeholders | `apt-get install git-lfs`, `git lfs pull` in that folder (step 5) |
| `module 'torchaudio' has no attribute 'set_audio_backend'` (then `info`) | `torch_audiomentations` uses functions newer `torchaudio` removed | patch the file (step 6) |
| A rerun says features already exist and skips the noise step | a crashed run left a half-written `positive_features_train.npy` | delete `my_custom_model/<name>/*_features_*.npy` and run again |
| `No module named 'onnx_tf'` at the very end | the optional phone format (`.tflite`) needs an extra library | ignore it; the `.onnx` file is what we use |
| The downloaded `.onnx` won't load on the laptop | newer PyTorch saves the weights in a separate `.onnx.data` file | merge them (step 8) |
| The notebook's own test cell crashes (`get_pretrained_model_paths`) | the notebook's development version of openWakeWord | test on the laptop instead (`wake_test.py`) |
| "Runtime disconnected", and reconnecting gave a computer **without** a graphics card | idle timeout | **Change runtime type → T4 GPU** again. Long jobs: start them in the background (`nohup … &`) and check the log |
| **"Cannot connect to GPU backend: usage limits"**, and everything on the runtime was gone | the free tier allows only a few GPU hours a day; I'd used ~2h40m | wait about a day. Keep every file you uploaded on your own laptop, because the runtime is wiped |

---

## Part 2 · Teach it your own voice (and test it honestly)

### Why
The first model (v1) was trained on fake voices only. On **its own kind** of
clips it was nearly perfect: 49/50 heard, 0/50 look-alikes. On **my** voice:

| Held-back clips (never used for training), threshold 0.2 | Desk | Bed | Across the room | Normal talk (false alarms) |
|---|---|---|---|---|
| v1 | 10/12 | 3/12 | 3/12 | 0/12 |

So it works up close, but badly from the bed or across the room. Turning up
the mic volume in software (`--gain`, `--auto-gain`) **didn't help at all**.
At a distance the problem is the room's echo and my real voice, not loudness.
The fix is to train with real recordings of me.

### Steps
1. **Record yourself**, hands-free: walk to the spot, and after every beep say
   the wake word once, the way you normally would.
   ```powershell
   .venv\Scripts\python.exe blood\record_wake.py desk --count 50
   .venv\Scripts\python.exe blood\record_wake.py bed --count 50
   .venv\Scripts\python.exe blood\record_wake.py far --count 50
   .venv\Scripts\python.exe blood\record_wake.py talk --count 50     # NOT the wake word: normal phrases, look-alikes
   ```
   They go to `models\my_voice\<spot>\` (git-ignored: it's your voice).
2. **Keep a quarter aside** as a held-back test set. Never train on them.
   They're the honest exam: a model can memorise clips it trained on.
   ```powershell
   .venv\Scripts\python.exe blood\pack_voice.py
   ```
   It holds back every 4th clip (listed in `models\my_voice\holdout.json`) and
   zips the rest into `models\my_voice_train.zip` for Colab.
3. **Cut every clip so it ENDS right after the phrase.** This is the one that
   cost me a whole training run, see below. [`blood/colab_train_v3.sh`](../../blood/colab_train_v3.sh)
   does it: it finds the end of the loud part around the loudest moment and
   keeps 1.3 s before it and 0.15 s after.
4. In Colab, do Part 1's steps 1–6 (setup, fixes, step 1 and step 2 of the
   notebook, but **not** its step 3). Then upload `my_voice_train.zip` and
   [`blood/colab_train_v3.sh`](../../blood/colab_train_v3.sh) with the 📁
   panel on the left, and start it in the background:
   ```
   !nohup bash colab_train_v3.sh > v3.log 2>&1 &
   ```
   Check on it now and then with `!tail -5 v3.log`. It makes the fake voices,
   cuts your clips, copies each one 15 times (every copy gets different noise
   and echo, so they act like new recordings), trains, and ends with
   `ALL DONE` and a single `hey_blood_v3.onnx` to download. About 2 hours.
   *(Settings: 30,000 fake examples, 30,000 steps, false-alarm weight 1,000.)*
5. Score the new model on the held-back clips and compare with the old one:
   ```powershell
   .venv\Scripts\python.exe blood\wake_eval.py --model models\hey_blood.onnx --holdout
   .venv\Scripts\python.exe blood\wake_eval.py --model models\hey_blood_v3.onnx --holdout
   ```

### The mistake that made v2 worse than v1
openWakeWord assumes **the phrase ends at the end of each clip**, the way the
fake-voice clips are cut. It labels the *last* ~1.3 seconds as "the wake word".
My recordings were 2.5 s long with the phrase in the middle:

```
my clip (2.5 s):  [beep..][ hey blood ][.......silence 1.4 s.......]
labelled YES:                              [ last ~1.3 s ]
```

So v2 learned "the quiet after Tudor speaks = YES", and with my normal talk
labelled NO, effectively "Tudor's voice = probably NO". It got worse
everywhere, even on the clips it trained on:

| Held-back clips, threshold 0.2 | Desk | Bed | Far | False alarms |
|---|---|---|---|---|
| v1 (fake voices only) | 10/12 | 3/12 | 3/12 | 0/12 |
| v2 (my clips, uncut) | 4/12 | 0/12 | 1/12 | 0/12 |

**How I made sure the cut is right:** my first try (find where speech starts
*and* ends) chopped off the soft "h" and lowered v1's hits from 14 to 3 on the
bed clips. The version in the script only finds the **end**. I checked it
against v1 itself: on the 53 clips v1 hears, v1 fires **0.26 s (± 0.06) after**
the detected end, every time. A consistent gap means the end is found
consistently. Then I listened to a few cut clips.

> ⬜ **v3 (with the cut clips) hasn't finished a run yet:** Colab's free GPU
> limit ran out halfway through, the same day as v2. The script is checked
> (I ran its cutting step on my clips on the laptop). The numbers go here once
> it has run. Until then, Blood uses v1.

### What went wrong for me
| Problem | Cause | Fix |
|---|---|---|
| v1 misses from the bed and across the room | trained on fake voices only | record your own clips (step 1) |
| More software volume didn't help at a distance | the problem is echo and voice, not loudness | real recordings, or a better/closer mic |
| v2 worse than v1 | clips not cut to end at the phrase | cut them (step 3) |
| The recording beep was silent | a very short tone played through `sounddevice` got swallowed | `winsound.Beep` (Windows' own beep) |

---

## Part 3 · The voice program (`blood/`)

### The pieces
| File | What it does |
|---|---|
| [`blood/blood.py`](../../blood/blood.py) | the main loop: wake word → greeting → record → ear → brain → speak |
| [`blood/ha.py`](../../blood/ha.py) | talks to Home Assistant's Assist over the websocket API: audio in → text, text in → answer |
| [`blood/speak.py`](../../blood/speak.py) | cleans the answer (emojis, non-Latin letters, markdown, `°C`) and has Piper say it on port 10200, playing while it's still being made |
| [`blood/screen.py`](../../blood/screen.py), [`screen_live.js`](../../blood/screen_live.js) | the full-screen window that follows the conversation ([chapter 10](10-screen.md)) |
| [`blood/settings.toml`](../../blood/settings.toml) | everything you might tune: wake model and threshold, mic, recording and follow-up timings, the screen, voice, name spelling, word fixes |
| `logs\blood.log` | every request: what it heard, what it sent, the answer, the timings (git-ignored: it's what you say) |

### Steps
1. **A Home Assistant token**, so the program can log in like an app: Home
   Assistant → your profile (bottom left) → **Security** →
   **Long-lived access tokens → Create token**. Copy it once and put it in a
   file `.env` in the repo folder:
   ```
   HA_TOKEN=paste-it-here
   ```
   `.env` is git-ignored. Treat it like a password.
2. Install the packages into the venv (if you didn't in Part 1):
   ```powershell
   .venv\Scripts\python.exe -m pip install -r blood\requirements.txt
   ```
3. **Your name's sound spelling.** Run the name test with your voice, listen,
   and put the best one in `settings.toml` (`name_spoken`):
   ```powershell
   .venv\Scripts\python.exe tests\tts\name_test.py en_US-libritts_r-medium      # spellings 1-8
   .venv\Scripts\python.exe tests\tts\name_test.py en_US-libritts_r-medium 2    # 9-16, aimed at Romanian sounds
   ```
   For "Tudor" the winner was `[[ tˈudor ]]` (#10): Piper's phoneme syntax for
   short u, short o and a rolled r. If none sounds right, use a title
   ("Yes, sir?") in `greeting` instead.
4. Start it and talk:
   ```powershell
   .venv\Scripts\python.exe blood\blood.py
   ```
5. Test the pieces separately when something's off:
   ```powershell
   .venv\Scripts\python.exe blood\ha.py "what time is it?"     # brain only, typed
   .venv\Scripts\python.exe blood\speak.py "Good morning, Tudor."  # voice only
   ```

### How it decides you've finished talking
A speech detector (Silero VAD, included in openWakeWord) scores every 80 ms.
- After "Yes, Tudor?" it waits 0.25 s for the room's echo to die, then for
  **0.16 s of real speech** before recording, so a click or an echo isn't you.
- It stops once you've said **at least 0.4 s** of speech **and** then been quiet
  for **1 s**. Before that (one word, or just an echo) it waits up to 2 s, so a
  normal pause before you start doesn't end the recording.

### Talking on without "Hey Blood"
After each answer Blood listens **5 more seconds** (`follow_up` in
`settings.toml`, `0` switches it off). If I start talking in that time, it's
the same conversation: "Turn on the main light" → *"The main light is on."* →
"make it 100%". The 5 seconds only count until I *start* talking; 2–3 s was too
short, because the clock starts the moment Blood stops and I need a moment to
react.
- **"That's all"**, "stop", "never mind", "no thanks", "thank you, Blood" end
  the conversation quietly, without asking the brain. "Stop the music" is still
  a normal request: only the whole sentence counts.
- If a follow-up hears only noise (often Blood's own echo), it ends quietly.
  Answering "Sorry, I didn't catch that" there could start Blood answering
  itself.
- **A fresh conversation after 6 of my questions** (`fresh_after`). The brain's
  memory is 4,096 tokens, and it holds the instructions (with the list of my
  devices) *and* the conversation. In a long chat it filled up around my 17th
  question: Ollama's log showed `4089 of 4096 … truncated`, every answer took
  ~29 s instead of 1–2 s, and since the cut starts at the beginning, Blood
  forgot the bed lights existed ("I don't have any lights in an area called
  bed"). 6 keeps well clear of that; the price is that it forgets what came
  before.

### Making it fast
The first live test was slow: **12–18 s** from the end of my sentence to the
answer. Typing the same thing in Home Assistant's chat took 1–2 s. Three causes:

| Cause | What I saw | Fix |
|---|---|---|
| Home Assistant's agent was set to the plain `qwen3:4b-instruct` | `ollama ps` showed 28% of the model on the CPU | pick `blood-brain` again in the Ollama agent's settings (chapter 04): 100% GPU |
| **One endless conversation** | the conversation grew to 3,800 of 4,096 tokens | the program starts a **fresh conversation after 2 minutes of silence** (`forget_after`), like the chat window does each time you open it, and after 6 questions in a row (`fresh_after`, see above). Follow-ups within 2 minutes still work. |
| **The clock in the prompt, with the conversation after it** | fast within the same minute, 12–18 s every time the minute changed: Ollama's log showed it re-reading ~2,000 tokens at ~140 tokens/s | prompt **v13**: no clock at all. Home Assistant answers "what time is it?" itself, without the brain. The calendar stays (it only changes once a day). |
| The ear's text didn't match my automation sentences | it wrote "**Uh** close the main light." and "Close the **bedlights**." | the program tidies the text before the brain sees it: drops "uh/um", fixes words from `[heard_fixes]` in `settings.toml` |

After the fixes: **~1.5–3 s** for most requests, ~1 s for sentences Home
Assistant matches itself.

### Check it worked
`logs\blood.log` shows each request like this:
```
Wake word (score 0.58)
Recorded 2.4s (0.9s of it speech)
Heard: 'Open the bed lights.' -> sent 'Open the bed lights'  ->  Blood: 'The bed lights are on.'  (ear 2.2s, total 4.6s)
```
"ear" includes the time you spend talking, so the real wait is shorter.

### What went wrong for me
| Problem | Cause | Fix |
|---|---|---|
| It heard only "Yeah." or "Two dogs." | the echo of "Yes, Tudor?" started the recording, and my normal reaction pause ended it after ~1 s | the recording rules above |
| 12–18 s answers | endless conversation + the clock, see the table above | fresh conversation, prompt v13 |
| The dimming "didn't work" | it set 50% when the light was already at 54% | v13: "dim" means about half the current brightness |
| "Make it brighter **and** blue" → "brighter and blue", only brightness changed | two actions in one sentence is the small model's weak spot | one action per sentence; a known limitation |
| After ~20 questions in one chat: "I don't have any lights in an area called bed", 29 s per answer | the brain's memory was full, so its instructions were cut | a fresh conversation after 6 questions |
| It answered "I'll use the live context tool to get this information" and stopped | the model promised instead of acting (a cold start) | the program replies "Go ahead." once to answers that only promise to look something up |

---

## Part 4 · Start it by itself at login

1. **Task Scheduler** task *"Blood - Voice program"*: at login (+45 s, after
   the VM), runs `.venv\Scripts\pythonw.exe blood\blood.py`. `pythonw` is
   Python without a window. No time limit. The "restart every minute" setting
   only helps if the task can't start at all, **not** if Python starts and then
   crashes, so Blood restarts itself (point 2). Same idea as the VM's task in chapter 03. In PowerShell (no admin needed):
   ```powershell
   $root = "D:\path\to\this\repo"
   $action = New-ScheduledTaskAction -Execute "$root\.venv\Scripts\pythonw.exe" -Argument "`"$root\blood\blood.py`"" -WorkingDirectory $root
   $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"; $trigger.Delay = "PT45S"
   $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
   $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable
   Register-ScheduledTask -TaskName "Blood - Voice program" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
   ```
2. The program is built to run unattended:
   - **waits for Home Assistant** after a reboot (checks every 10 s) instead of crashing
   - **starts its log first, then loads its parts**, and if loading fails it
     waits 30 s and tries again (up to 10 times). Right after login, Windows can
     still be setting up sound and USB: one morning the mic library failed to
     load, and Blood died before writing a single line, so the log looked fine
     and Blood was just deaf
   - **restarts itself after a crash** (30 s later), looking for sound devices again
   - **only one copy at a time** (a second one sees the first and quits)
   - a failed request gives a **low beep**, gets logged, and it keeps listening
   - the log is capped at 3 files of ~1 MB
3. After changing `settings.toml`, double-click [`tools\blood-restart.cmd`](../../tools/blood-restart.cmd).
4. Before games, stop it together with the VM and Ollama (my private
   "gaming mode" script does all three). Start it again afterwards with
   `Start-ScheduledTask "Blood - Voice program"`.

### Check it worked
Restart the laptop, log in, wait ~2 minutes, say "Hey Blood". No window
appears; `logs\blood.log` shows `Ready. Listening for 'hey_blood'`.
