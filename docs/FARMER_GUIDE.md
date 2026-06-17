# Navamesh Farm App — Farmer Guide

Everything you need to check on your farm from your phone.

---

## What it does

The Navamesh Farm app talks to a small gateway computer (a Raspberry Pi) on your farm over a HaLow Wi-Fi radio (the white HT-HD01 box). You can check soil moisture, battery levels, node locations, and more from your Android phone — even when you are far from regular Wi-Fi.

The app works over the Reticulum mesh radio network. It does not use the internet.

---

## First-time setup

### Step 1 — Install the app

1. Connect your phone to your computer with a USB cable.
2. Open a terminal on your computer and run:

   ```
   adb install navameshfarm-1.9.7-arm64-v8a-debug.apk
   ```

3. The app icon "Navamesh Farm" will appear on your home screen.

### Step 2 — Enter the radio address

1. Open the app and tap the **📢 Announce** tab at the top.
2. Scroll down to find the **HT-HD01 IP** field.
3. Enter the IP address shown on the label on your HT-HD01 box (example: `192.168.1.50`).
4. Leave the port at `4242` unless your installer told you otherwise.
5. The setting saves automatically when you leave the field.

### Step 3 — Find your gateway

1. Tap the **📡 Stream** tab.
2. Wait up to 60 seconds. The Pi gateway will announce itself as **"Navamesh Gateway"** and appear highlighted in green.
3. Tap the row and then tap **"Set as farm GW"**.
4. Done — the gateway is now pinned. You will see its name at the top of the Commands screen.

---

## Checking on your farm

Tap the **💬 Commands** tab to see all 9 buttons:

| Button | What it shows |
|--------|--------------|
| 📋 Farm status | Overall system summary |
| 💧 Soil moisture | Moisture reading from all soil sensors |
| 🔋 Battery | Battery voltage and charge % |
| 📍 Locations | GPS coordinates of all nodes |
| 📡 Signal strength | Radio signal level (RSSI) for each node |
| 🗺 Map — all nodes | Map image showing all node positions |
| 🛰 List nodes | List of node IDs (use before "Map — one node") |
| 🗺 Map — one node | Tap, then pick a node ID from the list |
| ❓ Help | Quick reference from the gateway |

Tap any button and wait up to 30 seconds for the reply to appear below.

**Map buttons** return an image that is shown inline in the reply card.

---

## Status dot

- **Green dot** (● Radio connected) — the radio link to the gateway is working.
- **Red dot** (○ Radio not responding) — check that the white HT-HD01 box is powered on and within range.

---

## Large text

If the text is too small, tap the **📢 Announce** tab, scroll down, and flip the **Large text** switch on. Then close and re-open the app to apply.

---

## Troubleshooting

| Symptom | What to check |
|---------|--------------|
| "No announces heard yet" in the Stream tab | Is the white HT-HD01 box powered? Is it on the same network as the Pi? |
| Commands time out with "Send failed" | Is the Pi gateway running? Check `sudo systemctl status reticulum-bridge` on the Pi. |
| App crashes on startup | Re-install the APK; make sure Android is version 8 or newer. |
| Map image does not appear | The Pi's map service may be offline; try the "Help" command first to verify the gateway is responding. |

---

*For Pi-side installation and HT-HD01 setup, see `docs/DEPLOYMENT.md`.*
