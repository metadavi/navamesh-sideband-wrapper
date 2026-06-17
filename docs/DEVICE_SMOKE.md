# Navamesh Farm — Device Smoke Checklist

Verify the APK on an Android device or emulator before field deployment.

**APK:** `dist/navamesh-farm-*-debug.apk`  
**Min SDK:** Android 7.0 (API 24)  
**Target SDK:** Android 13 (API 33)

Legend: ✅ Pass · ❌ Fail · ⏩ User field test (device/emulator required)

---

## Install

| # | Step | Expected | Result |
|---|------|----------|--------|
| 1 | `adb install -r dist/navamesh-farm-*-debug.apk` | Exit 0, "Success" | ⏩ user field test |
| 2 | App icon visible in launcher | "Navamesh Farm" label + sprout icon | ⏩ user field test |

## Service

| # | Step | Expected | Result |
|---|------|----------|--------|
| 3 | Launch app | Foreground service notification appears in notification tray: "Sideband Service" or "Navamesh Service" | ⏩ user field test |
| 4 | Pull down notification drawer | Service notification persists | ⏩ user field test |

## Screen navigation

| # | Step | Expected | Result |
|---|------|----------|--------|
| 5 | App opens | Three tabs visible: Announce, Stream, Commands | ⏩ user field test |
| 6 | Tap "Announce" tab | Own LXMF address shown; "Send Announce" button present | ⏩ user field test |
| 7 | Tap "Stream" tab | Announce stream list shown (empty is OK on first launch) | ⏩ user field test |
| 8 | Tap "Commands" tab | 3×3 grid of 9 command buttons shown | ⏩ user field test |

## Radio — Wi-Fi UDP (run with Pi or laptop rig on same Wi-Fi)

| # | Step | Expected | Result |
|---|------|----------|--------|
| 9 | Configure HT-HD01 IP in settings (gear icon) | IP saved; StatusChip shows "● Radio connected" | ⏩ user field test |
| 10 | Tap "Send Announce" | No error; status chip stays green | ⏩ user field test |
| 11 | Gateway announce heard | Gateway row appears in Stream tab, highlighted green | ⏩ user field test |
| 12 | Tap "Set as farm GW" on gateway row | Commands tab header shows gateway name | ⏩ user field test |

## Command round-trips (requires gateway reachable)

| # | Step | Expected | Result |
|---|------|----------|--------|
| 13 | Tap "💧 Soil moisture" | Reply card with soil % values appears | ⏩ user field test |
| 14 | Tap "📋 Farm status" | Status card with all nodes appears | ⏩ user field test |
| 15 | Tap "🗺 Map — all nodes" | Reply card with map image rendered inline | ⏩ user field test |
| 16 | Tap "🛰 List nodes" then "🗺 Map — one node" | Single-node map image shown | ⏩ user field test |

## No-radio state

| # | Step | Expected | Result |
|---|------|----------|--------|
| 17 | With no gateway / radio, tap any command | Reply card: "Gateway not pinned or radio unavailable / Would send: '…'" | ⏩ user field test |
| 18 | StatusChip shows | "○ Radio not responding — check the white box" | ⏩ user field test |

## APK structural verification (no device needed)

| # | Step | Expected | Result |
|---|------|----------|--------|
| S1 | `unzip -l dist/*.apk \| grep farmui` | farmui package entries present | see build log |
| S2 | `unzip -l dist/*.apk \| grep sidebandservice` | service entry present | see build log |
| S3 | `unzip -l dist/*.apk \| grep farm/icon` | farm icon asset present | see build log |
| S4 | `aapt dump badging dist/*.apk \| grep package` | `package: name='farm.navamesh.navameshfarm'` | see build log |

---

## Notes

- Rows 1–18 are marked ⏩ **user field test** — they require a physical Android device
  or a configured Android emulator, which is not available in this build environment.
- Rows S1–S4 (structural) can be verified from the APK file directly; fill these in
  after the Docker build completes.
- For the HT-HD01 Wi-Fi path (rows 9–16), the phone and the Pi-side HT-HD01 must be
  on the same Wi-Fi subnet.  See `deploy/rns_udp_hthd01.conf.example` for config.
