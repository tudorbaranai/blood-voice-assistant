# 08 · Lights and plugs

## Goal
Home Assistant (and so Blood) can switch your lights and plugs, **locally**,
without any cloud.

## Why it depends on the device
Every brand speaks its own "language". First find out **what you actually
have**. In the brand's app or in Google Home → tap the device → ⚙️ / device info
→ look for the maker, model or the app it uses. Then:

| What you have | How it talks | Home Assistant integration | Local, no internet? |
|---|---|---|---|
| **WiZ** bulbs (Philips/Signify) | Wi-Fi | **WiZ** (official) | ✅ |
| **Philips Hue Bluetooth** bulbs, no bridge | Bluetooth | **Philips Hue BLE** (needs chapter 07) | ✅ |
| Philips Hue with a Hue Bridge | Zigbee via the bridge | **Philips Hue** | ✅ |
| **Tuya-based** (Smart Life, Tuya Smart, LSC Smart Connect, Gosund, Nous, …) | Wi-Fi | **Tuya** (cloud) or **Tuya Local** (HACS, local) | only with Tuya Local |
| TP-Link Tapo/Kasa, Shelly, Meross | Wi-Fi | their own integrations | mostly ✅ |
| Matter devices | Wi-Fi/Thread | **Matter** | ✅ (but see the NAT note) |

### ⚠️ The NAT note (affects every Wi-Fi device)
Our VM uses **NAT** networking (chapter 03). From inside the VM, Home Assistant
**can reach** devices on your home network, but it **can't discover** them
automatically. So:
- add Wi-Fi devices **by IP address**,
- give each device a **fixed IP** in your router (a "DHCP reservation"),
  otherwise the address can change after a router restart and Blood loses
  the device.

---

## Part 1 · A WiZ bulb ✅

### 1. Make sure the bulb is on the same network as the laptop
The bulb must be reachable from the laptop. WiZ app → tap the bulb → ⚙️ → the
device info shows its **IP address**. Compare it with the laptop's own IPv4
address (`ipconfig` in PowerShell): the first three numbers should match, for
example `192.168.1.x` on both.

Quick test from the laptop (needs Python, read-only):
```powershell
python tools\find_wiz_bulbs.py 192.168.1        # your network's first three numbers
```
It lists every WiZ bulb that answers, with its address, firmware and Wi-Fi signal.

> 💡 **If this is your case: the bulb is on a different router or Wi-Fi.**
> Many homes have two routers (for example, the internet provider's box plus
> your own router behind it), or a "guest" Wi-Fi. Devices on another router's
> Wi-Fi, or on a guest network, are often **walled off**: the laptop can't
> reach them at all, and Home Assistant says *"cannot connect"*.
> **What helped in our case:** move the bulb onto the **same router as the
> laptop**, on its **2.4 GHz** Wi-Fi (smart bulbs and plugs only use 2.4 GHz):
> 1. Connect your **phone** to that 2.4 GHz Wi-Fi.
> 2. WiZ app → bulb → ⚙️ → **Remove**.
> 3. Reset the bulb: wall switch **off–on 3 times** (about 2 s each), leave it on,
>    and it pulses.
> 4. WiZ app → **+ → Add light** (the phone uses Bluetooth to hand over the Wi-Fi
>    password, which is normal) → choose that 2.4 GHz network → same room and name.
> 5. Google Home usually picks it up again by itself ("sync my devices" if not).
>
> The laptop itself can stay on 5 GHz. Same router = same network.

### 2. Check "Allow local communication"
WiZ app → menu (top left) → **Settings → Security** → **Allow local
communication: on**. It's usually on by default.

### 3. Give the bulb a fixed IP in your router
Router admin page → **DHCP → Address Reservation** (the name varies by brand) →
add the bulb's **MAC address** (in the WiZ app's device info, or the router's
client list, where WiZ bulbs show up as `wiz_xxxxxx`) → its current IP → save.

### 4. Add it to Home Assistant
**Settings → Devices & services → + Add Integration → WiZ** → enter the bulb's
**IP address** → Submit → assign an **Area** (e.g. Bedroom).

### Check it worked
Open the light in Home Assistant: on/off, brightness and colour all react
within a second.
Expected in our NAT setup: if you change the bulb from the WiZ app or Google
Home, Home Assistant may take a few seconds to notice.

### What went wrong for us
| Problem | Cause | Fix |
|---|---|---|
| We planned for Hue Bluetooth bulbs, but the light was **WiZ** | never checked the brand | always check the device info first (table above) |
| Network scan found no bulb; the WiZ app showed it on the **other** router's network | the bulb had been set up on the internet provider's Wi-Fi, which walls devices off | moved it to our router's 2.4 GHz Wi-Fi (box above) |
| After a first, unfinished re-pairing, the bulb showed up for a moment, then vanished after a router restart | setup didn't finish, so the bulb fell back to its old saved network | remove it in the WiZ app and pair it again properly, with the phone on the 2.4 GHz network |
| *"Cannot connect"* when adding the WiZ integration | the bulb wasn't on a reachable network at that moment | fix the network first, then add by IP |

---

## Part 2 · A Tuya-based Wi-Fi plug (LSC Smart Connect) ✅

LSC Smart Connect (sold at Action) is a rebranded **Tuya** app. Tuya devices
can be controlled two ways:
- **Cloud** (official *Tuya* integration): easy, but every command goes
  through Tuya's internet servers. ❌ Not offline.
- **Local** ([*Tuya Local*](https://github.com/make-all/tuya-local), a community
  integration): Home Assistant talks to the plug directly, using a secret
  **local key** fetched once. ✅ Offline. **Our choice.**

*Why a key?* Tuya plugs encrypt their local messages, so nobody else on your
Wi-Fi can switch them. Tuya Local borrows the key once from your Smart Life
account, then never needs the internet again.

### 1. Move the plug to the Smart Life app
Tuya Local logs in with **Smart Life** (Tuya's own app), not with rebranded apps like LSC.
1. Phone on the **same 2.4 GHz Wi-Fi** as the laptop's router. Install **Smart Life**, create an account.
2. LSC Smart Connect app → the plug → **Remove device**.
3. Reset the plug: hold its button ~5 s until the light **blinks fast**.
4. Smart Life → **+ → Add Device** (it usually finds it by Bluetooth; otherwise
   *Electrical → Socket (Wi-Fi)*) → choose that 2.4 GHz Wi-Fi → name it.
5. Optional: Google Home → **+ → Works with Google → Smart Life** to keep it in Google Home.

> The "IP" shown in Smart Life's device info is your home's **public internet
> address** (what Tuya's cloud sees), not the plug's address inside your home.
> Find the local one in your router's client list (Tuya plugs often show up as
> `lwip0`), and reserve it there like the bulb's.

⚠️ **From now on, don't reset or re-pair the plug:** each re-pair changes its key.

### 2. Get Tuya Local into Home Assistant
**Normal way, through HACS** (the community "app store" for Home Assistant):
1. Settings → Add-ons/Apps → store → ⋮ → **Repositories** → add `https://github.com/hacs/addons`.
2. Install and start **Get HACS**, and follow its log. Then **restart Home Assistant**.
3. Settings → Devices & services → **+ Add Integration → HACS** → tick the boxes →
   enter the shown code at https://github.com/login/device.
4. HACS → search **Tuya Local** → Download → restart Home Assistant.

> 💡 **If this is your case: HACS says "Could not register" and shows no code.**
> In October 2026 the Home Assistant log showed
> `Request exception for 'https://github.com/login/device/code' with - 400, message='Got more than 8190 bytes when reading'`.
> GitHub's reply carried a ~9 KB security header, bigger than the 8 KB limit of
> the library HACS uses. That's a GitHub-side problem, nothing in your setup.
> **What helped in our case: install Tuya Local by hand**, the same files from the
> same place. In the VM console, type `login` at the `ha >` prompt, then (use
> the [latest release](https://github.com/make-all/tuya-local/releases) number instead of `2026.10.0`):
> ```sh
> docker exec homeassistant sh -c "cd /tmp && curl -sL -o tl.zip https://github.com/make-all/tuya-local/archive/refs/tags/2026.10.0.zip && unzip -q tl.zip -d tl && cp -r tl/*/custom_components/tuya_local /config/custom_components/ && rm -rf tl tl.zip"
> exit
> ```
> Then restart Home Assistant. (Downside: no automatic update notices until
> HACS works again.)

### 3. Add the plug
1. **Settings → Devices & services → + Add Integration → Tuya Local** →
   **cloud-assisted** setup → log in with the Smart Life account (it may ask for
   the **User Code**: Smart Life → *Me → ⚙️ → Account and Security*, and a QR
   code to scan with Smart Life).
2. Pick the plug. The device ID and local key fill in by themselves.
   **Host:** the plug's local IP. **Protocol:** `auto`.
3. Pick the matching type (a plug **with energy monitoring**), give it a sayable name, and finish.

### Check it worked
Switch it from Home Assistant; power readings (watts) appear.
If it misbehaves, **close the Smart Life app on your phone**: many Tuya plugs
accept only one local connection at a time.

### What went wrong for us
| Problem | Cause | Fix |
|---|---|---|
| Smart Life showed an IP that wasn't the plug's home address | it shows the home's public internet address | use the router's client list for the local IP |
| HACS: "Could not register", no code | GitHub's oversized header (see box) | installed Tuya Local by hand |

---

## Part 3 · Names, rooms and what Blood may touch ✅

Good names matter more than prompt wording for small models:
1. A short, unique, sayable **name** for each device. Ours are "Main light"
   (the bulb) and "Bed lights" (the plug). Avoid "Light 1", and avoid vague,
   descriptive names like "big light": they confused Blood.
2. An **Area** for each (e.g. Bedroom).
3. **If a plug powers a lamp, show it as a light.** Home Assistant adds a plug as
   a *switch*, so "turn on all the lights" or "it's too dark" would skip it. My
   plug runs the bed lights, so I changed it: Settings → Devices & services →
   **Entities** → the plug → ⚙️ → **Show as: Light**. It's still a plug; Home
   Assistant (and Blood) just treat it as a light. The bench models it the same
   way.
4. **Aliases** for other names you might say: device → ⚙️ → *Voice assistants →
   Aliases* (e.g. "ceiling light" for the main light).
5. **Settings → Voice assistants → Expose**: expose **only** your lights and plugs.
   Anything not exposed is invisible to Blood.
6. Then switch the conversation agent to **Control Home Assistant: Assist** and
   use the device-aware prompt [`prompts/prompt_v12_devices.txt`](../../prompts/prompt_v12_devices.txt)
   with the `blood-brain` model (chapter 04).

Test sentences (check *Voice assistants → ⋮ → Debug* each time):
| Say | Expect |
|---|---|
| "Turn on the bedroom light" | on; fast; *Processed locally = true* |
| "Is the bedroom light on?" | answers, **changes nothing** |
| "It's too dark in here" | the AI turns the lights on (a few seconds: it has to think, then call the switch) |
| "I can't really read with this light" | the AI makes the bulb brighter |
| "Turn on the garage" (doesn't exist) | says it can't find it, **never claims success** |
