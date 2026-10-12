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

## Part 2 · A Tuya-based Wi-Fi plug (LSC Smart Connect) 🟡 next

LSC Smart Connect (sold at Action) is a rebranded **Tuya** app. Tuya devices
can be controlled two ways:
- **Cloud** (official *Tuya* integration): easy, but every command goes
  through Tuya's internet servers. ❌ Not offline.
- **Local** (*Tuya Local* from HACS): Home Assistant talks to the plug directly
  using a secret **local key**, fetched once. ✅ Offline. **Our choice.**

Plan (to be completed and written up):
1. Move the plug from the LSC app to the **Smart Life** app, on the same 2.4 GHz
   network as the laptop.
2. Install **HACS** (the community store for Home Assistant; needs a GitHub login).
3. Install **Tuya Local** from HACS and add the plug, fetching the local key once.
4. Fixed IP in the router, as for the bulb.

Warnings we already know: **don't reset or re-pair the plug afterwards**, since
the local key changes. And close the Smart Life app if the plug acts up, because
some Tuya plugs accept only one local connection at a time.

---

## Part 3 · Names, rooms and what Blood may touch ⬜

Good names matter more than prompt wording for small models:
1. A clear, unique, sayable **name** for each device: "Bedroom light", "Desk
   lamp", "Fan plug". Avoid "Light 1".
2. An **Area** for each (e.g. Bedroom).
3. **Aliases** for other names you might say: device → ⚙️ → *Voice assistants →
   Aliases* (e.g. "big light").
4. **Settings → Voice assistants → Expose**: expose **only** your lights and plugs.
   Anything not exposed is invisible to Blood.
5. Then switch the conversation agent to **Control Home Assistant: Assist** and
   use the device-aware prompt [`prompts/prompt_v7_devices.txt`](../../prompts/prompt_v7_devices.txt) (chapter 04).

Test sentences (check *Voice assistants → ⋮ → Debug* each time):
| Say | Expect |
|---|---|
| "Turn on the bedroom light" | on; fast; *Processed locally = true* |
| "Is the bedroom light on?" | answers, **changes nothing** |
| "It's too dark in here" | the AI decides, probably turns on a light |
| "Turn on the garage" (doesn't exist) | says it can't find it, **never claims success** |
