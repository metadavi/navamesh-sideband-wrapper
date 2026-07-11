# Navamesh Farm — Pi update server

The phones poll `http://192.168.100.10:8080/version.json` for over-the-air
updates (see `sbapp/farmui/updater.py`). This folder sets the Pi up as that
host. It is a plain static file server — no wrapper code runs on the Pi, and
it is completely independent of the `rnsd`/gateway job.

## One-time Pi setup (via Pi Connect / SSH)

1. **Give the Pi the conventional static IP on the HT-HD01 subnet.**
   The phones are baked to look for `192.168.100.10`. On Raspberry Pi OS
   (Bookworm, NetworkManager):

   ```bash
   sudo nmcli con mod "Wired connection 1" \
     ipv4.addresses 192.168.100.10/24 ipv4.method manual
   sudo nmcli con up "Wired connection 1"
   ```

   (Adjust the connection name / interface to whichever port faces the
   HT-HD01. If the Pi needs a different address, change `update_urls` in each
   phone's `farmui_settings.json` instead — but the static IP is simpler.)

2. **Create the updates folder and install the service:**

   ```bash
   mkdir -p /home/pi/navamesh-updates
   sudo cp navamesh-update-server.service /etc/systemd/system/
   sudo systemctl enable --now navamesh-update-server
   ```

3. **Check it:** from any device on the farm network,
   `http://192.168.100.10:8080/` should list the folder.

## Publishing a release (from the build Mac)

```bash
bash scripts/publish_update.sh pi@<pi-address>
```

That builds nothing — it takes the newest APK already in `dist/`, writes a
matching `version.json`, and copies both to the Pi. Within 6 hours (or on next
app launch) every phone shows "Update available — tap to install".

Requirements for the update to be offered/installable on phones:
- `__version__` in `sbapp/main.py` must be **higher** than what's installed
  (dotted numeric compare, e.g. 1.9.9 > 1.9.8).
- `android.numeric_version` in `sbapp/buildozer.spec` must also be bumped
  (Android refuses to update to a lower/equal versionCode).
- Same keystore as always (automatic — it's committed in the repo).

## version.json format

```json
{"version": "1.9.9",
 "apk": "navameshfarm-1.9.9-arm64-v8a-debug.apk",
 "notes": "optional one-liner"}
```
