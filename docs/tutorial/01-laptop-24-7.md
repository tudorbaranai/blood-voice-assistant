# 01 · Prepare the laptop for 24/7

## Goal
The laptop becomes a small home server: always on, never sleeping, and not
wearing itself out.

## Why
A voice assistant that's asleep can't hear you. Laptops are built to sleep, to
charge their battery to 100% and to restart for updates whenever they like. All
three are bad for a server. The good news: **heat and wear come from heavy
load, not from being switched on**. An idle laptop draws roughly 10–20 W
(about €2 a month).

## Steps

### 1. Cap the battery charge (the most important one)
A battery kept at 100% all day ages fast. Most brands can stop charging at 60–80%.
- **ASUS:** MyASUS (or Armoury Crate) → **Battery Health Charging** →
  *Maximum lifespan (60%)* or *Balanced (80%)*.
- Lenovo: Vantage → *Conservation mode*. Dell: Power Manager → *Primarily AC use*.
  HP / others: look in the BIOS or the maker's app for "battery care / charge limit".

### 2. Never sleep when plugged in
Settings → System → **Power & battery** → *Screen, sleep & hibernate timeouts*:
- *Put my device to sleep when plugged in* → **Never**
- *Turn off my screen* → 10 minutes is fine. **A dark screen is not sleep**:
  everything keeps running.

### 3. Closing the lid does nothing
Settings → System → Power & battery → *Lid & power button controls* →
*Closing the lid, when plugged in* → **Do nothing**.
(Or Start → type "lid" → *Change what closing the lid does*.)

### 4. Airflow
Hard, flat surface (not a bed or sofa), vents free. Clean the vents every few months.

### 5. Windows Update shouldn't restart it in the middle of the day
Settings → Windows Update → Advanced options → **Active hours** → set them to
cover when you use Blood (I use 10:00–04:00).
Optional: Settings → Accounts → Sign-in options → *Use my sign-in info to
automatically finish setting up after an update*, so the laptop logs back in
(and Blood starts) after an update restart.

### 6. Update the graphics driver (NVIDIA)
Through the NVIDIA App / GeForce Experience. A recent driver helps Ollama use the GPU.

## Check it worked
In PowerShell:
```powershell
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE   # "Current AC Power Setting Index: 0x00000000" = never sleep
powercfg /query SCHEME_CURRENT SUB_BUTTONS LIDACTION   # AC index 0 = do nothing
```
After a day plugged in, the battery should sit at your cap (mine sits at ~60–63%).

## What went wrong for me
- Nothing broke here, but **I never actually updated the NVIDIA driver** at
  first and only noticed later (`nvidia-smi` showed a 2024 driver). It still
  works; it's just a "do it when convenient".
- Auto-start of the VM and Ollama after a reboot is covered in chapter 03.
