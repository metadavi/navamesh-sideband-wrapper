# Navamesh Farm — Pi update server

The phones poll `http://192.168.100.10:8090/version.json` for over-the-air
updates (see `sbapp/farmui/updater.py`). This folder sets the Pi up as that
host. It is a plain static file server — no wrapper code runs on the Pi, and it
is independent of the farm gateway stack.

**Port 8090, not 8080:** the Pi's farm Docker stack already serves map tiles on
8080 (`navamesh_tiles`, an nginx container), so the OTA update server uses
8090 to avoid the conflict. If you ever move the tiles server, you could switch
back to 8080 — but then you must also change `DEFAULT_UPDATE_URLS` in
`updater.py` and re-point each phone's `update_urls`.

## As-built config (farm Pi "pampi")

- **SSH from the build Mac:** `ssh pi@pampi.local` (key-based, no password).
- **Two-interface separation (do not break this):**
  - `wlan0` → internet uplink (edu / Starlink) and remote management. Owns the
    default route. This is how you reach the Pi from off-site.
  - `eth0` → the HT-HD01 HaLow mesh (`192.168.100.0/24`), local-only. The
    `halow-bridge` NetworkManager profile has `ipv4.never-default yes` +
    `ipv4.ignore-auto-dns yes`, so the mesh can never hijack the Pi's internet
    path. Leave those settings alone.
- **Fixed mesh address:** the Pi's `eth0` MAC `d8:3a:dd:ea:66:c3` has a **DHCP
  reservation on the Heltec HT-HD01** → always `192.168.100.10`. (eth0 stays a
  DHCP client; the Heltec just always hands it `.10`. This is why the phones
  can hardcode `.10`.)

## One-time setup (if rebuilding the Pi)

1. **Give the Pi a fixed `192.168.100.10` on the mesh side.** Preferred: add a
   DHCP reservation on the Heltec admin (`http://192.168.100.1`) mapping the
   Pi's `eth0` MAC to `192.168.100.10`. (Alternative: set the `halow-bridge`
   profile to `ipv4.method manual`, `ipv4.addresses 192.168.100.10/24`, **no
   gateway**, keeping `ipv4.never-default yes`.)

2. **Create the updates folder and install the service:**

   ```bash
   mkdir -p /home/pi/navamesh-updates
   sudo cp navamesh-update-server.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now navamesh-update-server
   ```

3. **Check it:** from any device on the farm network,
   `http://192.168.100.10:8090/` should respond (a 404 on an empty folder is
   fine — it means the server is up).

## Publishing a release (from the build Mac)

```bash
bash scripts/publish_update.sh pi@pampi.local
```

That builds nothing — it takes the newest APK already in `dist/`, writes a
matching `version.json`, and `scp`s both to the Pi. Within 6 hours (or on next
app launch) every phone shows "Update available — tap to install".

Requirements for the update to be offered **and installable** on phones:
- `__version__` in `sbapp/main.py` must be **higher** than what's installed
  (dotted numeric compare, e.g. 1.9.9 > 1.9.8).
- `android.numeric_version` in `sbapp/buildozer.spec` must **also** be bumped —
  Android refuses to install an APK whose versionCode isn't higher, even if
  `version.json` advertises a newer name.
- Same keystore as always (automatic — it's committed in the repo).

## version.json format

```json
{"version": "1.9.9",
 "apk": "navameshfarm-1.9.9-arm64-v8a-debug.apk",
 "notes": "optional one-liner"}
```

## Notes

- The current baseline published to the Pi is `1.9.8` (matches what the phones
  run), so phones correctly show *no* update until you publish a higher build.
- Field-verified end-to-end: a phone on the HaLow WiFi (`192.168.100.110`)
  fetched `version.json` and downloaded the 91 MB APK from the Pi over the mesh,
  and the Android installer engaged. (2026-07-13.)
