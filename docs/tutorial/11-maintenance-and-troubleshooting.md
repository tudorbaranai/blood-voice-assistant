# 11 · Maintenance and troubleshooting

## Routine
| When | What |
|---|---|
| Before **every** Home Assistant update | Take a VirtualBox **snapshot** (VM → Snapshots → Take). Update, test one voice question, and delete the snapshot after a few days (they grow and eat disk space). |
| Monthly | Home Assistant updates (with a snapshot first). |
| Every few months | Clean the laptop vents. If it feels hot, check temperatures (e.g. HWiNFO, free). |
| After any reboot | Wait about 2 minutes before testing: the VM, Home Assistant and Ollama need time to start. |

## Blood stopped answering? Check in this order
1. **Is the VM running?** VirtualBox shows *Running*, or http://127.0.0.1:8123 opens.
2. **Is Ollama running?** Llama icon in the tray, or `ollama ps` in PowerShell.
3. **Are the add-ons started?** Home Assistant → Settings → Add-ons (*Apps* in
   newer versions) → Whisper and Piper show *Started*.
4. **Which stage fails?** Settings → Voice assistants → ⋮ → **Debug** shows each
   stage (speech-to-text, conversation, text-to-speech) with its timing or error.
5. **A device stopped responding?** Check it still has the same IP (router's
   client list), and that the router is on (chapter 00: Wi-Fi devices need the router).

## Things we learned the hard way (collected from every chapter)
- **Bluetooth passthrough "Captured" but nothing arrives** → Bluetooth was off in
  Windows. Turn it on (chapter 07).
- **Home Assistant in this VM listens on port 80 inside the VM**, not 8123. The
  NAT rule must forward host 8123 → **guest 80** (chapter 03).
- **Wi-Fi devices on another router or guest Wi-Fi** can't be reached. Move them
  to the laptop's router, on 2.4 GHz (chapter 08).
- **Keep changing parts of an AI prompt at the end** (like the clock): a clock at
  the top made every answer re-read the whole prompt, which cost 4–7 s
  (chapter 04).
- **Small models sometimes write non-English letters** even when told not to.
  The prompt's English-only rule catches most of it; the planned voice program
  will clean the text before speaking (chapter 09).

## Ideas for later
- **Weather without sending your voice anywhere:** Home Assistant's free *Met.no*
  integration fetches the forecast. Only that request goes online.
- **Phone control away from home:** Tailscale (free, private tunnel). Never open
  router ports.
- **A faster ear:** Whisper on the graphics card, but it competes with the brain
  for graphics memory, so test first.
- **Free up 2.5 GB of RAM:** move Home Assistant to a spare old laptop or mini-PC
  with a backup/restore.
- **Re-test brains** when new small models come out (`tests/compare-brains.ps1`).
