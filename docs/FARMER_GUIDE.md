# Navamesh Farm App — Farmer Guide

Everything you need to check on your farm, and adjust your sensors, from your phone.

---

## What it does

The Navamesh Farm app talks to the gateway on your farm, a small computer (Raspberry Pi) that collects readings from every soil sensor in the field. Your phone reaches it over a HaLow Wi-Fi radio (the white HT-HD01 box), which carries much farther than ordinary Wi-Fi.

With the app you can:

- **Check on the farm:** soil moisture, sensor batteries, sensor locations, signal strength and maps.
- **Adjust a sensor:** change how often it reports, update its location, turn its Bluetooth on for maintenance, or pause and resume it.
- **Message other farmers** who have the app.

The app does not need the internet or cell service. It only needs to be in range of the farm's HaLow radio.

---

## First-time setup

### Step 1 — Install the app

Your installer will normally do this for you. If not:

1. Connect your phone to a computer with a USB cable.
2. On the computer, run:

   ```
   adb install navameshfarm-<version>-arm64-v8a-debug.apk
   ```

3. The **Navamesh Farm** icon appears on your home screen.

After this first install, the app updates itself from the farm gateway (see [Updates](#updates)).

### Step 2 — Join the farm's HaLow Wi-Fi

In your phone's **Settings → Wi-Fi**, connect to the network broadcast by the HT-HD01 box. Your installer will give you its name and password. This network has no internet, which is normal. If the phone asks whether to stay connected, choose **Yes / Keep connection**.

### Step 3 — Find your gateway

1. Open the app. It opens on the **💬 Talk** tab, which lists every device it can hear.
2. Wait up to a minute. The farm gateway appears as **"Navamesh Gateway"**.
3. Tap it. This opens the **Gateway commands** screen and remembers the gateway, so next time it is already selected, even after a restart.

---

## Checking on your farm

On the **Gateway commands** screen, tap a button and wait up to 30 seconds for the reply card. These buttons only read information; they never change anything in the field.

| Button | What it shows |
|--------|--------------|
| ❓ Help | Quick reference for every command |
| 📋 Farm status | How every sensor is doing |
| 💧 Soil moisture | How wet the soil is at each sensor |
| 🔋 Battery | Each sensor's battery charge, and time since it last restarted |
| 📍 Position | Where each sensor is |
| 📡 Sensor strength | How strong each sensor's radio signal is |
| 🗺 Map — all nodes | A map picture of every sensor |
| 🗺 Map — one node | A map of one sensor; pick it from the list |
| 🛰 List nodes | Every sensor the gateway knows. A ⚠️ means it has not been heard from recently |

**Maps** appear inside the reply card. Pinch to zoom and drag to move around.

**Tip:** if a node list is empty when you need to pick a sensor, tap **🛰 List nodes** first.

---

## Adjusting a sensor

These buttons send a command over the radio to a sensor in the field. Because they change real equipment, the app always shows what will happen and asks you to **confirm** first.

| Button | What it does |
|--------|--------------|
| ⏱ Set Reporting Interval | How often the sensor sends a reading. Pick 5 min, 15 min, 30 min, 1 hour, 8 hours (normal) or 24 hours, or tap **Enter a time** to type minutes or hours. Takes effect immediately. Shorter intervals give finer data but use more battery. |
| 📍 Change Sensor Location | Saves a new location for the sensor. **Stand next to the sensor**, then tap **Use my current location** (the phone's GPS), or **Enter coordinates** to type them. |
| 🔧 Bluetooth on | Turns on the sensor's Bluetooth for 5 min to 2 hours so a technician can connect to it. It switches off again by itself. |
| 🔇 Pause messaging | The sensor stops sending but keeps listening. It resumes by itself after one day, or immediately if it restarts. |
| 🔊 Resume messaging | The sensor starts sending readings again. |

### How to send one

1. Tap the button.
2. Pick the sensor from the list, or **ALL FIELD NODES** to change every sensor at once (not available for Change Sensor Location).
3. Pick a value, if the command needs one.
4. Read the confirmation and tap to send.

### What the reply means

| Reply | Meaning |
|-------|---------|
| ✅ | The sensor confirmed the change. The reply shows the value it actually applied. |
| ❌ | The sensor refused the change. The reply says why. |
| ⏱ | The sensor did not answer in time. It may be out of range, out of battery, or switched off. Try again later. |
| ⚠️ | Something went wrong at the gateway. Try again; if it repeats, tell your installer. |

---

## Messaging other farmers

Other phones running the app also appear in the **💬 Talk** tab. Tap one to open a chat and send text messages, over the same HaLow radio, with no internet needed.

Inside a chat, tap **Rename** to give that device a name you will recognise, for example the farmer's name. The new name is only saved on your phone.

Chats show the current session only and start fresh each time you open them.

---

## Updates

When a new version is available on the farm gateway, an **"Update available — tap to install"** card appears in the Talk tab.

1. Tap the card.
2. The first time, Android asks you to **allow updates from this app**. Allow it, go back, and tap the card again.
3. Confirm Android's **"Update this app?"** prompt.

Your gateway, chats and settings are kept. The download only works while you are connected to the farm's HaLow Wi-Fi.

---

## Radio status

The status line at the top of the app tells you whether the radio link is working:

| Status | Meaning |
|--------|---------|
| **Mesh active** | Everything is working. |
| **Listening for mesh…** | The app has just started and has not heard the gateway yet. Wait a minute. |
| **Mesh quiet** | Nothing heard recently. Check that you are connected to the HaLow Wi-Fi and within range of the white box. |
| **Service offline** | The app's background service stopped. Close and reopen the app. |

---

## Troubleshooting

| Problem | What to check |
|---------|--------------|
| "No devices heard yet" in the Talk tab | Is the phone connected to the farm's HaLow Wi-Fi? Is the white HT-HD01 box powered on? |
| "None selected — tap a gateway in the Talk tab" | Go back to Talk and tap **Navamesh Gateway**. |
| Commands show "Send failed" or never get a reply | The gateway may be off or restarting. Wait a few minutes and try **❓ Help**, which only needs the gateway to answer. |
| A sensor change keeps timing out (⏱) | Check **🛰 List nodes**. If the sensor has a ⚠️, the gateway has not heard from it recently and it may need a visit. |
| Map picture does not appear | Try **❓ Help** first to check the gateway is answering, then try the map again. |
| App will not start | Reinstall it. Android 8 or newer is required. |

---

*For gateway (Raspberry Pi) and HT-HD01 radio setup, see `docs/DEPLOYMENT.md`.*
