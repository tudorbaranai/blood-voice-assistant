# 03 · Home Assistant in a VirtualBox VM

## Goal
Home Assistant OS running in a virtual machine on the laptop, reachable in
the browser at **http://127.0.0.1:8123**, starting by itself after every reboot.

## Why a VM, and why VirtualBox
- **Home Assistant OS** (HAOS) is the full version: add-on store (we need
  Whisper and Piper), one-click updates and backups, official support. It's a
  whole Linux system, so on Windows it needs a VM.
- **Not Docker:** the Docker version has no add-on store, and USB/Bluetooth and
  network discovery don't reach the container on Windows.
- **Not Hyper-V:** built into Windows Pro, but it [has no USB support](https://www.home-assistant.io/installation/windows/),
  so the laptop's Bluetooth couldn't be passed in (chapter 07).
- **Cost:** about 2–2.5 GB of RAM held by the VM all the time, and ~32 GB of disk.

## Steps

### 1. Check virtualization is on
Task Manager → Performance → CPU → **Virtualization: Enabled**. If not, enable
it in the BIOS (AMD: "SVM", Intel: "VT-x").

### 2. Install VirtualBox
[virtualbox.org](https://www.virtualbox.org/) → Downloads → **Windows hosts** →
install with the defaults (we used **7.2.20**).
- A warning about **missing Python** dependencies can be ignored. It's only for
  optional scripting bindings.
- Allow the network driver installs if Windows asks.

> **`VBoxManage`** is VirtualBox's command-line tool. It's **not on the PATH**,
> so always call it with its full path. The default is
> `C:\Program Files\Oracle\VirtualBox\VBoxManage.exe` (ours is on another drive).
> Below we write `$vb` for it. Set it once per PowerShell window:
> ```powershell
> $vb = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
> ```

### 3. Download the Home Assistant OS disk image
[home-assistant.io/installation/windows](https://www.home-assistant.io/installation/windows/) →
**VirtualBox** → download the **`.vdi`** image (ours: `haos_ova-18.3.vdi.zip`).
Unzip it into a **permanent** folder (the VM runs from this file), e.g. `D:\Home Assistant VM\`.

### 4. Create the VM
VirtualBox → **New**:
| Setting | Value |
|---|---|
| Name | `Home Assistant` |
| Type / Version | Linux / **Oracle Linux (64-bit)** |
| ISO | leave empty |
| Memory | **2048 MB** to start (we later raised it to **2560 MB**) |
| Processors | **2** to start (we later raised it to **4**) |
| **Use EFI** | ✅ **required**, or it won't boot |

**Attaching the downloaded disk:** VirtualBox 7.2's basic wizard can only create
a *new empty* disk. Either:
- finish the wizard with any size, then **Settings → Storage → Controller: SATA**
  → remove the empty disk → **Add hard disk** → *Add* → pick the HAOS `.vdi`, or
- switch the wizard to **Expert** mode, which has *Use an existing virtual hard disk file*.

Also: **Settings → Audio → untick Enable Audio** (the VM doesn't need it).

### 5. Network: NAT + port forwarding
**Settings → Network → Adapter 1 → Attached to: NAT** → *Advanced* → **Port Forwarding** → ➕:

| Name | Protocol | Host IP | Host Port | Guest IP | Guest Port |
|---|---|---|---|---|---|
| `HA` | TCP | *(empty)* | **8123** | *(empty)* | **80** ⚠️ |

⚠️ **Guest port 80, not 8123.** In current Home Assistant OS versions,
Home Assistant listens on port **80** inside the VM. See "What went wrong".
Type each cell, then **press Enter**, or the dialog complains about "zero" ports.

Or from PowerShell (VM can be running):
```powershell
& $vb controlvm "Home Assistant" natpf1 "HA,tcp,,8123,,80"
```

*Why NAT and not "Bridged"?* Home Assistant's guide suggests Bridged, which
gives the VM its own address on your home network. Over **Wi-Fi** that was
unreliable for us (setup crawled at 4–5% for 30 minutes). NAT always works over
Wi-Fi. The price: Home Assistant can't *discover* devices on your network
automatically, so you add them by IP (chapter 08).

### 6. Start it and finish setup
Start the VM (no green turtle icon in the status bar = good; a turtle means
Hyper-V/WSL is slowing VirtualBox down). Wait a few minutes, then open
**http://127.0.0.1:8123**. The first start downloads Home Assistant ("Preparing…").
Then create your account (you choose the password), set your location and units,
and turn analytics off if you want it fully private.

### 7. Start the VM automatically (headless, no window)
A Task Scheduler task that starts the VM 30 s after you log in. In PowerShell:
```powershell
$vb = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
$action    = New-ScheduledTaskAction -Execute "C:\Windows\System32\conhost.exe" `
             -Argument "--headless `"$vb`" startvm `"Home Assistant`" --type headless"
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"; $trigger.Delay = 'PT30S'
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
             -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "Start Home Assistant VM" -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Description "Starts the Home Assistant VM headless after login"
```
- `conhost --headless` hides the console window.
- **At login, not at boot:** VirtualBox VMs belong to a user, and starting at boot
  would mean storing your Windows password in Task Scheduler. With Windows set to
  finish updates by signing in automatically (chapter 01), this is fine.
- Ollama already auto-starts itself (an `Ollama` shortcut in your Startup folder).

**Shut the VM down cleanly** (like pressing a power button) whenever you need to:
```powershell
& $vb controlvm "Home Assistant" acpipowerbutton
```

### 8. Give it more CPU and RAM (once you add the speech add-ons)
The speech-to-text add-on alone uses ~1 GB. With the VM **off**:
```powershell
& $vb modifyvm "Home Assistant" --cpus 4 --memory 2560
```
CPU cores are only used when the VM is busy, but RAM is held all the time. On an
8 GB laptop, 2.5 GB was the sweet spot next to the AI model.

## Check it worked
```powershell
& $vb showvminfo "Home Assistant" --machinereadable | Select-String '^(VMState|memory|cpus|Forwarding)'
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8123/     # 200 = Home Assistant answers
```
Then log out and back in (or restart): about 1–2 minutes later, http://127.0.0.1:8123 works on its own.

## What went wrong for us
| Problem | Cause | Fix |
|---|---|---|
| Setup crawled at 4–5% for 30 min | **Bridged over Wi-Fi** was unreliable on our Realtek Wi-Fi | switched to **NAT** |
| http://127.0.0.1:8123 wouldn't load, so "Preparing" *looked* stuck | Home Assistant listens on **guest port 80**; guest 8123 only redirects to port 80, so the browser bounced to http://127.0.0.1/ on Windows, where nothing listens | NAT rule **host 8123 → guest 80**. Clue: the VM console banner shows `http://homeassistant.local` with no port, and `core info` at the `ha >` prompt says `port: 80` |
| Port Forwarding dialog: "ports may not be zero" | the table cell wasn't committed, or an empty extra rule | press **Enter** after each cell, delete extra rules |
| VirtualBox wizard had no "use existing disk" | moved to Expert mode in 7.2 | attach the `.vdi` under Settings → Storage |
| `VBoxManage` "not recognized" | not on PATH | use the full path (`$vb` above) |
| Something fails right after a reboot | the VM, Home Assistant and Ollama are still starting | wait about 2 minutes and retry before debugging |

**Tip:** the VM console (VirtualBox window, or `VBoxManage controlvm … screenshotpng`)
shows an `ha >` prompt. Useful commands: `core info`, `network info`,
`apps info core_whisper`. `login` opens a full Linux root shell; `exit` returns.
(`clear` is not a command there.)
