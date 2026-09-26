# EasyQuestUpdater

**EasyQuestUpdater** solves one frustrating problem: Meta's firmware download page times out before the file finishes downloading, especially on slow internet connections. This app downloads the firmware reliably in the background — with automatic resume if interrupted — then installs it directly onto your Quest headset via USB.

---

## What it does

1. Opens the Meta firmware page inside a monitored browser window
2. The moment you click **Start Download**, the app intercepts the URL silently
3. Downloads the firmware (~1.3 GB) to your PC with full resume support — if your connection drops, it picks up where it left off
4. Installs the firmware onto your Quest via ADB sideload over USB

---

## Before you start — two things to set up

### 1. Enable Developer Mode on your Quest headset

Developer Mode is required for ADB (the USB tool that installs the firmware). You only need to do this once.

1. Install the **Meta Quest** mobile app on your phone
2. In the app, tap on your headset
3. Go to **Settings → Developer Mode** and toggle it **ON**
4. A confirmation message will appear on your headset — put it on and **Accept**

> If you don't see Developer Mode, you may need to register a developer organisation at [developer.oculus.com](https://developer.oculus.com) — it's free and takes about 30 seconds.

---

### 2. Install ADB (Android Debug Bridge)

ADB is a free tool from Google that lets a PC communicate with Android devices over USB. EasyQuestUpdater will tell you if it's missing and show you exactly what to do.

**Quick setup:**

1. Download **SDK Platform Tools for Windows** from:  
   [developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools)
2. Extract the ZIP — you'll get a folder called `platform-tools`
3. Move or copy that folder to **`C:\platform-tools`**
4. Launch EasyQuestUpdater — the badge in the top-right corner should turn green

> If it stays red, click **Check Again** inside the app.

---

## How to use EasyQuestUpdater

### Step 1 — Get the firmware URL

1. Launch **EasyQuestUpdater** from your desktop
2. Make sure the **ADB: ready** badge is green (if not, complete the ADB setup above)
3. Click **Open Browser & Capture URL**
4. A browser window opens on the Meta firmware page
5. Log in to your Meta account if prompted
6. Connect your Quest headset to your PC via USB
7. Put on the headset and **Accept** the "Allow USB Debugging" prompt
8. Back in the browser, click **Start Download**
9. EasyQuestUpdater silently captures the URL — you'll see "URL captured" in the app

> **You can close the browser immediately after this.** The app has taken over the download — downloading in the browser at the same time wastes bandwidth.

---

### Step 2 — Wait for the download

The app shows download progress with a percentage and speed. The firmware is around 1.3 GB.

- If the download is interrupted (power cut, sleep, network drop), just relaunch the app and capture the URL again — it will resume from where it left off
- The file is saved to `Downloads\quest-firmware` on your PC

---

### Step 3 — Install the firmware

Once the download reaches 100%:

1. Make sure your Quest is connected via USB with USB Debugging accepted
2. Click **Install via ADB**
3. The app reboots your headset into **recovery mode** automatically
4. Put on the headset — you may see a black screen saying **"No command"**. This is normal. To reveal the menu: **hold the Power button, then press Volume Up once**
5. Use the **Volume Down** button to scroll to **"Apply update from ADB"**
6. Press the **Power button** to select it
7. The screen will show **"Now send the package via ADB sideload…"**
8. Click **OK** in the EasyQuestUpdater dialog
9. The firmware transfers over USB — this takes **10–20 minutes**. Do not disconnect the cable
10. The headset reboots automatically when done

> If the headset stays on the recovery screen after the transfer, use Volume to select **"Reboot system now"** and press Power.

---

## Why does this exist?

Meta's download page has a session timeout that kicks in while the 1.3 GB file is still downloading. On fast connections this isn't a problem, but on slower connections (or with network interruptions) the download never completes. EasyQuestUpdater captures the URL the moment it's generated and downloads it independently, with full resume support, so the Meta session timeout doesn't matter.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| ADB badge stays red after setup | Check that `adb.exe` is in `C:\platform-tools` and re-launch the app or click **Check Again** |
| "No Quest headset detected" | Re-seat the USB cable; accept the "Allow USB Debugging" prompt inside the headset; set USB mode to File Transfer |
| Download fails immediately | The URL has probably expired — click **Open Browser & Capture URL** again to get a fresh one |
| Download stuck at 0% | The URL may have expired; capture a new one |
| Headset doesn't enter sideload mode | Make sure you selected "Apply update from ADB" in the recovery menu, not just "Apply update" |
| See "No command" screen | Normal — hold Power, then press Volume Up once to reveal the recovery menu |
| Recovery menu won't appear | Try holding Power + Volume Down together for 10 seconds to force recovery mode |

---

## ⚠ Disclaimer

EasyQuestUpdater installs firmware via **ADB sideload**, which is an unofficial installation method. By using this tool you accept that:

- **The authors accept no responsibility for device damage, data loss, warranty voidance, or any other consequence** of using this software
- Sideloading firmware is done entirely at your own risk
- This tool is not affiliated with, endorsed by, or supported by Meta Platforms, Inc.

---

## Requirements

- Windows 10 or 11
- Google Chrome or Microsoft Edge
- ADB (see setup above)
- Meta Quest 3 headset with Developer Mode enabled
- USB cable (use the one that came with your Quest)
