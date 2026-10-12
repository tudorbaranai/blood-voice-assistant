# 07 · Bluetooth into the VM (optional)

## Goal
Give Home Assistant (inside the VM) the laptop's own Bluetooth, so it can
control **Bluetooth** devices directly: for example Philips Hue Bluetooth bulbs
(no Hue Bridge), Bluetooth sensors, and so on.

> **Do you need this?** Only for Bluetooth devices. Our bulb turned out to be
> **WiZ (Wi-Fi)**, which doesn't need Bluetooth at all (chapter 08). We kept it
> anyway, ready for future Bluetooth gadgets.

## Why it has to be "passed through"
Home Assistant's Bluetooth support only works on Linux. The VM is a separate
little Linux computer with **no Bluetooth of its own**. VirtualBox can
**unplug** a USB device from Windows and **plug** it into the VM. Inside most
laptops, the Bluetooth chip is a USB device.

⚠️ **The trade-off:** while the VM runs (always), **Windows has no Bluetooth**:
no Bluetooth headphones, mouse or keyboard. If you need those, use a cheap USB
Bluetooth dongle just for the VM instead, or an ESP32 flashed as an
[ESPHome Bluetooth proxy](https://esphome.io/projects/?type=bluetooth).

## Steps

### 0. Check your Bluetooth is a USB device
Device Manager → View → **Devices by connection** → find your Bluetooth adapter.
It should sit under a **USB Root Hub**. Then, in PowerShell:
```powershell
& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" list usbhost
```
(Use your own VirtualBox folder if you installed it elsewhere.) Note the entry
for your Bluetooth chip: its **VendorId / ProductId**. Ours shows up under the
name of the module maker ("IMC Networks") rather than "Bluetooth", and **the
webcam had the same maker name**, so go by the product ID, not the name.

### 1. Turn Bluetooth ON in Windows ⚠️
Settings → Bluetooth & devices → **Bluetooth: On**. This sounds backwards, but
if it's off, the chip is powered down and VirtualBox can't take it. See
"What went wrong" below.

### 2. Shut the VM down cleanly
```powershell
& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" controlvm "Home Assistant" acpipowerbutton
```
Wait until VirtualBox shows **Powered Off**.

### 3. Add the USB filter
VirtualBox → select the VM → **Settings → USB**:
1. Tick **Enable USB Controller** and choose **USB 3.0 (xHCI) Controller**.
   (On VirtualBox 7 this is built in; no Extension Pack needed.)
2. Click the **USB plug icon with the green +** and pick your Bluetooth chip.
   This "filter" makes the VM grab it every time it starts.
3. **OK**.

### 4. Start the VM again
From VirtualBox, or with your auto-start task (chapter 03).

## Check it worked
1. From Windows:
   ```powershell
   & "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" showvminfo "Home Assistant" | Select-String -Context 0,5 "Currently attached USB"
   ```
   Your chip's VendorId/ProductId should be listed. (`list usbhost` saying
   *Captured* is **not** enough, see below.)
2. In Home Assistant: **Settings → Devices & services**. **Bluetooth** appears
   under *Discovered* → **Add**. Its device page shows an adapter **hci0** with
   the chip's name (ours: "Bluetooth Radio … by Realtek").

## What went wrong for us
| Problem | Cause | Fix |
|---|---|---|
| `VBoxManage list usbhost` said **Captured**, but nothing appeared in Home Assistant. Inside the VM, `lsusb` showed only empty hubs; in Windows the chip still used its normal Bluetooth driver. `usbattach` said *"busy with a previous request"* | **Bluetooth was switched off in Windows**, so the chip was powered down and VirtualBox couldn't take it over | Turn Bluetooth **on** in Windows. It attached immediately |
| Two devices with the same maker name in the list | the Bluetooth chip and the webcam come from the same module maker | pick by **ProductId**, not by name |

Handy for debugging: the Home Assistant VM's console has a root shell. At the
`ha >` prompt type `login`, then `lsusb` (USB devices the VM sees) or
`dmesg | grep -i blue` (Bluetooth driver messages). Type `exit` to go back.

## Next: Bluetooth devices
With Bluetooth in place, Philips Hue **Bluetooth** bulbs (no bridge) can be added
with the [Philips Hue BLE integration](https://www.home-assistant.io/integrations/hue_ble/).
Put the bulb in pairing mode (Hue app → Settings → Voice Assistants → Google Home
or Alexa → **Make Discoverable**), then add it from *Discovered*. We haven't
done this ourselves (we have no Hue bulbs), so follow the official page.
