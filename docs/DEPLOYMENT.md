# Navamesh Farm App — Deployment Guide

This guide covers the server-side (Raspberry Pi) and radio (HT-HD01) setup, plus APK sideloading onto the Android device.

---

## Architecture overview

```
Android phone
  └─ Navamesh Farm APK
       └─ LXMF over Reticulum
            └─ HT-HD01 (HaLow Wi-Fi, UDP bridge, 900 MHz)
                  └─ Raspberry Pi
                       └─ reticulum_bridge.py  (gateway)
                            └─ farm sensors / nodes
```

---

## 1. Raspberry Pi gateway

### 1.1 Requirements

- Raspberry Pi 3B+ or newer (or any Linux host with Python 3.9+)
- Ethernet or Wi-Fi connection to the HT-HD01 box
- Python 3.9+ with pip

### 1.2 Install RNS and LXMF

```bash
pip3 install rns==1.3.5 lxmf==1.0.1
```

Exact versions matter — the Android app is pinned to these.

### 1.3 Configure RNS (Reticulum) with the HT-HD01 interface

Edit `~/.reticulum/config` (created automatically on first `rnsd` run):

```ini
[reticulum]
  enable_transport = True
  share_instance   = Yes

[interface:HTHD01_UDP]
  type             = UDPInterface
  enabled          = Yes
  listen_ip        = 0.0.0.0
  listen_port      = 4242
  forward_ip       = <HT-HD01 bridge IP>
  forward_port     = 4242
```

Replace `<HT-HD01 bridge IP>` with the LAN IP address of your HT-HD01 unit (printed on the label or found via DHCP leases).

### 1.4 Start the Reticulum daemon

```bash
rnsd --verbose
```

For a persistent service:

```bash
sudo tee /etc/systemd/system/rnsd.service > /dev/null <<'EOF'
[Unit]
Description=Reticulum Network Stack
After=network.target

[Service]
ExecStart=/usr/local/bin/rnsd
Restart=on-failure
User=pi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now rnsd
```

### 1.5 Run the farm gateway bridge

```bash
python3 reticulum_bridge.py --display-name "Navamesh Gateway" --verbose
```

The `--display-name` value **must** be `"Navamesh Gateway"` — the app's Stream screen highlights only entries with this exact name.

For a persistent service:

```bash
sudo tee /etc/systemd/system/reticulum-bridge.service > /dev/null <<'EOF'
[Unit]
Description=Navamesh Farm Gateway Bridge
After=rnsd.service

[Service]
ExecStart=/usr/bin/python3 /home/pi/reticulum_bridge.py --display-name "Navamesh Gateway"
Restart=on-failure
User=pi
WorkingDirectory=/home/pi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now reticulum-bridge
```

### 1.6 Verify the gateway is announcing

```bash
rnstatus               # shows local RNS identity and uptime
rnpath <gateway-hash>  # resolves the gateway address
```

Or watch the bridge log:

```bash
journalctl -fu reticulum-bridge
```

---

## 2. HT-HD01 HaLow radio setup

The HT-HD01 is a 900 MHz HaLow (802.11ah) radio that bridges the Android phone and the Pi over long-range Wi-Fi. It operates as a transparent UDP bridge.

### 2.1 Factory defaults

| Setting | Default |
|---------|---------|
| Management IP | `192.168.1.1` |
| Radio mode | AP (access point) |
| UDP bridge port | `4242` |
| Frequency | 902–928 MHz (US) |

### 2.2 Configure the bridge

1. Connect a laptop to the HT-HD01 management port.
2. Open `http://192.168.1.1` in a browser (default credentials in the unit's manual).
3. Set **UDP forward IP** to the Pi's LAN IP address.
4. Set **UDP forward port** to `4242` (must match `listen_port` in the RNS config).
5. Set **SSID** and **password** so the Android phone can connect.
6. Save and reboot the unit.

### 2.3 Android phone Wi-Fi

Connect the Android device to the HT-HD01's SSID before launching the Navamesh Farm app. The phone does not need internet access — only the HaLow radio link to the Pi matters.

---

## 3. APK sideload onto Android

### 3.1 Enable USB debugging

On the Android device:

1. **Settings → About phone** — tap **Build number** 7 times to enable Developer options.
2. **Settings → Developer options** — turn on **USB debugging**.

### 3.2 Install via adb

```bash
# Verify the device is detected
adb devices

# Install (allow the "USB debugging" prompt on the phone if prompted)
adb install dist/navameshfarm-1.9.7-arm64-v8a-debug.apk
```

Expected output: `Success`

The "Navamesh Farm" icon will appear in the app drawer.

### 3.3 Verify USB device filter (for future USB serial accessories)

The APK ships with a `res/xml/device_filter.xml` that lists USB vendor/product IDs for common LoRa and serial adapters. No further setup is needed for HaLow radio operation (which uses Wi-Fi, not USB).

---

## 4. End-to-end smoke test

After completing all three sections above:

1. **On the Pi:** confirm `rnsd` and `reticulum-bridge` are running:
   ```bash
   systemctl is-active rnsd reticulum-bridge
   ```
2. **On the phone:** open Navamesh Farm → **📡 Stream** tab → wait 60 s → "Navamesh Gateway" should appear highlighted in green.
3. **Tap "Set as farm GW"**, then go to **💬 Commands** → tap **📋 Farm status** → a reply card should appear within 30 s.

If the gateway does not appear, see the Troubleshooting section in `docs/FARMER_GUIDE.md`.

---

## 5. Updating the APK

When a new APK is released, sideload it over the existing install:

```bash
adb install -r dist/navameshfarm-<version>-arm64-v8a-debug.apk
```

The `-r` flag replaces the app **in place**, preserving all app data — including
this device's unique Reticulum identity and its pinned gateway.

### Stable signing key (why updates work)

Every build signs the APK with one fixed debug keystore committed to the repo at
`keystore/navamesh-debug.keystore` (standard `androiddebugkey` / `android`
credentials). `scripts/build_apk.sh` seeds it onto a persistent `~/.android` Docker
volume before the build, so consecutive APKs share the same signer and Android
accepts them as updates rather than as a different app.

To confirm two builds share the same signer:

```bash
keytool -printcert -jarfile dist/<apk>   # APK signer fingerprint
keytool -list -v -keystore keystore/navamesh-debug.keystore -storepass android
```

> **Note on identities.** The signing key only identifies the *build*, not the
> device. Each phone generates and stores its own Reticulum identity in the app's
> private storage (`app_storage/primary_identity`), so a shared signing key does
> **not** share identities between devices — every phone keeps its own. The trade-off
> is the usual one: `adb install -r` keeps that identity, but a full **uninstall**
> deletes app storage and therefore wipes the identity + pinned gateway.

---

*For day-to-day use instructions, see `docs/FARMER_GUIDE.md`.*
