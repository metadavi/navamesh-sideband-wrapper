# Field Test Plan — Navamesh Farm App

Real-hardware validation against the actual Pi gateway running
`reticulum_bridge.py` over the HT-HD01 HaLow Wi-Fi link.

Complete these steps in order.  Each step has an **Expected:** line.
Tick each box when the expected result is observed.

---

## Prerequisites

- Android device with the sideloaded `dist/navameshfarm-1.9.7-arm64-v8a-debug.apk`
- Pi running `reticulum_bridge.py` and `rns` with the `HTHD01_UDP` interface configured
- HT-HD01 radio bridging the Android device and Pi on the same LAN segment (or direct HaLow link)
- Stock Sideband installed on a second device (for parallel verification, step 10)

---

## Step 1 — Install APK

Sideload the APK: `adb install dist/navameshfarm-1.9.7-arm64-v8a-debug.apk`

**Expected:** Install succeeds; "Navamesh Farm" icon appears on the device.

---

## Step 2 — Configure UDP interface

Open the app → Settings → enter the Pi's HT-HD01 IP address and UDP port
(defaults: broadcast group, port matching `HTHD01_UDP` on the Pi).

**Expected:** Settings screen accepts the IP/port; no validation error; config is saved on exit.

---

## Step 3 — App launches; service starts

Force-stop the app, re-open it from the launcher.

**Expected:** App opens on the Conversation screen within 5 seconds; the status
chip at the top shows a non-error state (may say "starting…" briefly then
stabilize).

---

## Step 4 — Three screens reachable

Tap each bottom-tab icon: Announce, Stream, Conversation.

**Expected:** All three screens load without crash; navigation is smooth and
no "back stack" errors appear in the UI.

---

## Step 5 — Send announce

Open the Announce screen; tap the large "Send Announce" button.

**Expected:** Button briefly shows a "sending…" indicator; within 10 seconds
the app's own LXMF address appears in the Announce Stream on the gateway Pi's
log (`tail -f /var/log/rns.log` or equivalent).

---

## Step 6 — Gateway announce heard in stream

Open the Stream screen; wait up to 60 seconds.

**Expected:** An entry for "Navamesh Gateway" (or the configured display name)
appears in the announce stream; tapping it shows the option "Set as my farm gateway".

---

## Step 7 — Pin the farm gateway

Tap the gateway announce → "Set as my farm gateway" → confirm.

**Expected:** Gateway is marked as pinned in the Stream screen; the status chip
on all screens now reflects whether the gateway is reachable.

---

## Step 8 — All 9 command buttons produce replies

On the Conversation screen, tap each command button in turn and wait for the
reply card to appear before tapping the next:

1. 📋 Farm status
2. 💧 Soil moisture
3. 🔋 Battery
4. 📍 Locations
5. 📡 Signal (RSSI)
6. 🗺 Map — all nodes
7. 🛰 List nodes — note one node ID from the reply
8. 🗺 Map — one node (use node ID from step 8.7 in the picker)
9. ❓ Help

**Expected (each):** A reply card appears with non-empty text within 30 seconds.
For "Map — all nodes" and "Map — one node": an inline map image is visible.
For "List nodes": a list of node IDs appears.

---

## Step 9 — Soil command round-trip wire check (on Pi)

While tapping 💧 Soil moisture in step 8.2, simultaneously run on the Pi:

```bash
grep "soil" /var/log/rns.log | tail -3
```

or watch `reticulum_bridge.py` stdout for the received command line.

**Expected:** The Pi log shows the gateway received the string `"soil"` (not a
binary blob, not a modified string) from the farm app's LXMF address.

---

## Step 10 — Stock Sideband works in parallel

On the second device with stock Sideband installed, send a message "status"
to the same Pi gateway from the Sideband conversation screen.

**Expected:** Stock Sideband receives a reply; the Pi gateway serves both
devices simultaneously with no interference; the farm app is still responsive.

---

## Step 11 — App backgrounds and foregrounds cleanly

While a reply is pending (tap a command then immediately background the app):
press Home, wait 15 seconds, re-open the app.

**Expected:** The reply card appears after re-opening (reply was received by the
foreground service); no ANR or crash dialog.

---

## Step 12 — Gateway unreachable path

Disable Wi-Fi on the Android device, then tap a command button.

**Expected:** A plain-language error card appears ("Gateway not reachable")
within 30 seconds; re-enabling Wi-Fi and tapping the same command again
produces a normal reply.

---

## Step count check

Steps: 12
Expected lines: 12 (one **Expected:** per step — counts match)

---

## Recording results

Fill in the table below after completing the field test:

| Step | Result | Notes |
|---|---|---|
| 1 — Install APK | ☐ Pass / ☐ Fail | |
| 2 — Configure UDP | ☐ Pass / ☐ Fail | |
| 3 — Service starts | ☐ Pass / ☐ Fail | |
| 4 — Three screens | ☐ Pass / ☐ Fail | |
| 5 — Send announce | ☐ Pass / ☐ Fail | |
| 6 — Gateway heard | ☐ Pass / ☐ Fail | |
| 7 — Pin gateway | ☐ Pass / ☐ Fail | |
| 8 — All 9 commands | ☐ Pass / ☐ Fail | |
| 9 — Wire check | ☐ Pass / ☐ Fail | |
| 10 — Stock parallel | ☐ Pass / ☐ Fail | |
| 11 — Background | ☐ Pass / ☐ Fail | |
| 12 — Unreachable | ☐ Pass / ☐ Fail | |
