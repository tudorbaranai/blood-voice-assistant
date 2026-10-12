# Blood: the road to the finish

Your offline voice assistant. This file is the full plan from where we are (12 October 2026) to the end.
Work through it **one part at a time**. Each step says **what**, **why**, and **how to check it worked**.
Tick the boxes `[x]` as you go.

> **Resuming with Claude later:** open a new chat in the `D:\Claude Projects\jarvis` folder and say
> *"Continue the Blood project, read ROADMAP.md, I'm at step X."* Claude's memory already knows the project.
> The full step-by-step guide (what we did, for others too) is in `docs/tutorial/`.

---

## Where we are ✅

| Piece | Status |
|---|---|
| Laptop ready for 24/7 (battery cap, no sleep, lid = nothing) | ✅ |
| Home Assistant OS in VirtualBox (NAT, 4 CPU, 2.5 GB), auto-starts at login | ✅ |
| Brain: Ollama + `qwen3:4b-instruct`, prompt **v6**, context 4096 | ✅ |
| Ear: Parakeet (Whisper add-on, `local_files_only` on), mic tuned (Realtek effects off, boost 0 dB, volume 100) | ✅ |
| Voice: Piper `en_US-libritts_r-medium` | ✅ |
| HA updated to 2026.10.1 | ✅ |
| Bluetooth passed into the VM (B1) | ✅ 13 Oct (not needed for now: no Hue bulbs) |
| Bedroom light = **WiZ** Wi-Fi bulb (not Hue!), in HA via the WiZ integration, fixed IP | ✅ 13 Oct |
| LSC plug, local (Tuya Local) | 🟡 next: B3 |
| Names, rooms, prompt v7 | ⬜ B4–B6 |
| "Hey Blood" + our own voice program | ⬜ Part C |
| Screen window | ⬜ Part D |

**The "doors" (port forwards) you'll see mentioned:**
`127.0.0.1:8123` → Home Assistant · `127.0.0.1:10300` → ear · `127.0.0.1:10200` → voice · from inside the VM, `10.0.2.2:11434` → Ollama.

---

## Part A: Tidy up (10 minutes, any time)

- [ ] **A1. Delete the update snapshot after 2–3 days** if everything still works.
  VirtualBox → select "Home Assistant" → **Snapshots** → select "before 2026.10.1" → **Delete**.
  *Why:* snapshots grow over time and eat disk space. Take a new one before every future update.
- [ ] **A2. Optional: remove the thinking model** (2.5 GB, too slow for voice):
  ```powershell
  ollama rm qwen3:4b-thinking
  ```
  Keep `qwen3:1.7b` and `qwen3:4b-instruct`.
- [ ] **A3. Optional: delete the extra Piper voices** you won't use. They live inside the VM. Not urgent, they're small.

---

## Part B: Lights and plugs (end of Stage 3)

### B0. First, know the trade-off ⚠️
When we pass the laptop's Bluetooth into the VM, **Windows loses Bluetooth while the VM runs**: no Bluetooth headphones, mouse or keyboard on Windows.
- If you **don't use** Bluetooth devices on Windows → go ahead with B1.
- If you **do** → better options:
  1. **A cheap USB Bluetooth dongle** (about €10) given only to the VM. Windows keeps its own Bluetooth. Not €0, but the cleanest.
  2. **An ESP32 as a "Bluetooth proxy"** (you own ESP32 boards, so €0): it listens to the bulbs over Bluetooth and talks to HA over Wi-Fi. Flashed from the browser at *esphome.io → Bluetooth proxy*. Windows keeps its Bluetooth, and range gets better too. ⚠️ HA in NAT mode can't *discover* it, so you'd add it by IP (Settings → Add integration → ESPHome → the ESP32's IP).

### B1. Pass the Bluetooth adapter into the VM
*Why:* HA's Bluetooth only works on Linux, so the VM needs its own Bluetooth.
1. Shut down the VM: `& "D:\Oracle VirtualBox\VBoxManage.exe" controlvm "Home Assistant" acpipowerbutton`, then wait for **Powered Off**.
2. VirtualBox → VM **Settings → USB** → tick **Enable USB Controller** → choose **USB 3.0 (xHCI) Controller**.
   - If it complains that you need the **Extension Pack**: download "Oracle VirtualBox Extension Pack" **for exactly 7.2.20** from virtualbox.org (free for personal use) and double-click it.
3. Click the **USB plug icon with a green +** → pick **"Realtek Bluetooth …"** from the list. That creates a filter, so whenever the VM starts, it grabs that device.
4. **OK** → start the VM: `Start-ScheduledTask -TaskName "Jarvis - Start Home Assistant VM"`.
5. **Check:** in HA, **Settings → Devices & services**. A **Bluetooth** integration should appear as "Discovered" → **Add**. Its page should show an adapter (hci0) as **connected**.
   - Not showing up? Settings → System → Hardware (⋮ → All hardware) and look for Bluetooth. If nothing is there, Linux may lack the driver for this Realtek chip, and plan B is the dongle or the ESP32 proxy from B0.

- [x] **B1 done 13 Oct.** Gotcha: Bluetooth must be switched **ON in Windows** first, or VirtualBox can't take the chip.

### B2. The bedroom light ✅ (it's WiZ, not Hue)
- [x] The light is a **WiZ** Wi-Fi bulb, so no Bluetooth is needed. It was on the internet provider's router Wi-Fi (walled off) → re-paired in the WiZ app onto our router's **2.4 GHz** Wi-Fi, DHCP reservation in the router, added in HA with **Add Integration → WiZ → its IP**. Works.
- Hue Bluetooth bulbs (if ever bought): Bluetooth is ready (B1) → "Philips Hue BLE" integration, see `docs/tutorial/07`.

### B3. The LSC plug, local (next session)
The plug is already on our router's 2.4 GHz Wi-Fi with a reserved IP. LSC Smart Connect = a rebranded Tuya app. Plan (**option B, local**, so it works without internet):
1. Move the plug from the **LSC Smart Connect** app to the **Smart Life** app (remove in LSC → hold the plug's button until it blinks fast → add in Smart Life on the same 2.4 GHz Wi-Fi). Re-link Google Home to Smart Life if wanted.
2. Install **HACS** in HA (needs a GitHub login).
3. Install **Tuya Local** from HACS → add the plug, fetching its local key once.
4. **Check:** you can switch the plug from HA, and the power-meter readings show up.
- ⚠️ Don't reset or re-pair the plug afterwards: the local key changes.

### B4. Names, rooms and exposure (this is what makes Blood accurate)
*Why:* earlier research showed **good names matter more than prompt wording** for small models.
1. Give every light and plug a **clear, unique, sayable name**: "Desk lamp", "Ceiling light", "Bed lamp", "Fan plug". Avoid "Light 1".
2. Assign each one to an **Area** (e.g. "Bedroom").
3. Add **aliases** (other names you might say): device → ⚙️ → **Voice assistants → Aliases**, e.g. "big light" for the ceiling light.
4. **Settings → Voice assistants → Expose tab:** expose **only** your lights and plugs. Anything not exposed is invisible to Blood, so it can't touch it by mistake.

### B5. Let Blood control the devices
1. Blood agent ⚙️ → **Control Home Assistant: Assist** → Submit.
2. Replace the Instructions with **`prompts\prompt_v7_devices.txt`**. It's v6 with the "I can't control devices yet" part replaced by real control rules: act only when clearly asked, ask when unsure, never claim success that didn't happen, confirm big group actions.
3. Make sure **Prefer handling commands locally = ON** (the fast lane for simple commands).

### B6. Test it (and look at Debug every time)
Say or type these. In **Voice assistants → ⋮ → Debug**, check **"Processed locally"** (true = the fast lane, no AI involved):

| Say | Expect |
|---|---|
| "Turn on the desk lamp" | On. Processed locally = true, very fast |
| "Turn off all the lights" | All off, no confirmation needed |
| "Is the ceiling light on?" | Answers. **Changes nothing** |
| "It's too dark in here" | AI decides, probably turns on a light in your area |
| "Turn on the light" (with 2+ lights) | Asks which one |
| "Turn on the garage" (doesn't exist) | Says it can't find it. **Never claims success** |

If something misbehaves: check names/aliases first, then the prompt. Note what happened for Claude.

---

## Part C: "Hey Blood" and our own voice program (Stage 4)

**The goal:** you say "Hey Blood", hear "Yes, Tudor?" (your name pronounced right), speak, and hear the answer on the AUX speakers. No browser, no clicking.

```
mic → [wake word "Hey Blood"] → play "Yes, Tudor?" → record until you stop talking
    → send to HA (ear + brain) → get the answer text
    → clean it (remove Korean letters etc., swap "Tudor" for the sound spelling)
    → Piper speaks it (port 10200) → AUX speakers
```
*Why we do the speaking ourselves instead of letting HA do it:* code-level control. We can **guarantee** no unpronounceable characters, and make your name sound right every time.

### C1. Train the "Hey Blood" wake word
There's no ready-made "Hey Blood", so we train one with **openWakeWord** (free).
1. The easiest way is openWakeWord's **automatic training notebook** on **Google Colab** (free, runs in the browser, about 1 hour). It generates thousands of computer-voiced "Hey Blood" clips and trains a small model. Find it from the openWakeWord GitHub page (github.com/dscripka/openWakeWord → "Training New Models").
   - Target phrase: `hey blood`. It also catches "hey blud", since they sound identical.
   - Note: this one step uses Google's computers online. Only the *training* happens there. The finished model runs fully offline on your laptop.
2. Download the result (`hey_blood.onnx`) into `D:\Claude Projects\jarvis\models\`.
3. *(Better accuracy, optional)* Record about 20 clips of **your own** "Hey Blood" plus room noise for a "custom verifier". Claude can help. It reduces false triggers a lot.
4. **Meanwhile**, Claude can build the program with the ready-made `hey_jarvis` model as a stand-in, then swap.

### C2. Create a Home Assistant access token
*Why:* our program has to log into HA like an app does.
1. In HA, click your **profile** (bottom left) → **Security** tab → **Long-lived access tokens → Create token**, named "Blood program".
2. **Copy it once** (it's shown only once) and paste it into a new file `D:\Claude Projects\jarvis\.env` as:
   `HA_TOKEN=paste-it-here`
3. Treat it like a password: don't share it or paste it in chats. **You** do this step, not Claude.

### C3. Claude writes the program (`jarvis\blood\`)
What it will contain, so you know what to expect:
- **Wake word listener** (openWakeWord, always on, about 1–3% CPU).
- **Greeting:** a pre-made "Yes, Tudor?" audio file in the libritts_r voice with your name's sound spelling. First we redo the name test for **libritts_r** (test #8 was done with Ryan).
- **Recorder with "end of speech" detection** (VAD), so it stops when you stop talking.
- **HA connection** (the websocket API): sends the audio, receives what the ear heard and the brain's answer. It keeps a short conversation memory, so follow-ups like "and the other one?" work.
- **Text cleaner:** removes non-English characters and emojis, and swaps "Tudor" for the sound spelling.
- **Piper speaker** via port 10200 → plays on the default output (your AUX speakers).
- **Logs** in a file, so problems can be diagnosed.
- **Settings** in one config file (mic, volume, wake word sensitivity).

### C4. Run it automatically
A Task Scheduler task at login (like the VM one), running with `pythonw.exe` (no window). Claude gives you the exact commands.

### C5. Test it like a pro
- [ ] **Distance:** "Hey Blood" from your desk, the bed, and across the room. 10 tries each, count the hits.
- [ ] **False triggers:** play YouTube or TV for 1 hour with the program running, and count wrong wake-ups. Aim for 0–1 per hour; tune the sensitivity otherwise.
- [ ] **Speed:** from end of your sentence to Blood's first word. Target about 2–3 s.
- [ ] **Name:** does "Yes, Tudor?" sound right?

---

## Part D: The screen window (Stage 5)

**The goal:** a full-screen window on the Asus showing **what you said**, **Blood's answer**, and an animation for **listening / thinking / speaking**. The screen wakes up on "Hey Blood".

1. Claude builds it as part of the program (likely a simple Python window, or a local web page shown in a borderless browser window). Same idea either way.
2. States: **idle** (dark or clock) → **listening** (pulsing circle) → **thinking** (spinning) → **speaking** (wave synced to the voice) → back to idle after about 10 s.
3. **Screen wake:** the program tells Windows "user activity" on the wake word, which switches the display on, and lets it sleep again afterwards.
4. Your name is shown as **"Tudor"** on screen, even though the voice uses the sound spelling.

---

## Part E: Living with Blood (maintenance)

- **Monthly:** HA updates → **snapshot first**, update, test one voice question, delete the snapshot a few days later.
- **Every few months:** clean the laptop vents. Check temperatures if it feels hot (HWiNFO, free).
- **After any reboot:** wait about 2 minutes before testing. The VM, HA and Ollama need time to start.
- **If Blood stops answering, check in this order:**
  1. Is the VM running? (VirtualBox shows "Running", or open http://127.0.0.1:8123)
  2. Is Ollama running? (llama icon in the tray, or `ollama ps` in PowerShell)
  3. In HA: Settings → Add-ons/Apps → are Whisper and Piper "Started"?
  4. Voice assistants → Debug: which stage shows an error?
- **Ideas for later (optional):**
  - **Weather without sending your voice anywhere:** add HA's free "Met.no" weather integration. HA fetches the forecast, and Blood reads it locally. Only the forecast request goes online.
  - **Phone control away from home:** Tailscale (free, private tunnel). Never open router ports.
  - **A faster ear:** run Whisper on the graphics card. It competes with the brain for graphics memory, so test first.
  - **Free 2.5 GB of RAM:** move Home Assistant OS onto the old 4 GB laptop as a dedicated server.
  - **Re-test brains** when new small models come out: `tests\compare-brains.ps1` with `tests\questions-limits.txt`.

---

## Useful files

| File | What |
|---|---|
| `prompts\prompt_v6.txt` | the current brain instructions (no device control) |
| `prompts\prompt_v7_devices.txt` | the next version, for step B5 |
| `tests\compare-brains.ps1` + `tests\questions-limits.txt` | brain comparison bench |
| `tests\stt\` | ear test bench (`record.py`, `bench_stt.py`, `audio_check.py`) |
| `tests\tts\` | voice audition (`tts_audition.py`) and name pronunciation test (`name_test.py`) |
| `docs\how-blood-works.html` | the visual explainer of the pipeline |
