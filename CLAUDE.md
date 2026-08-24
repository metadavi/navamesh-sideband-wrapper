# navamesh-sideband-wrapper — the farmer's Android app

A fork of Sideband (Reticulum's messenger). The mesh stack is upstream's; what we add is
`sbapp/farmui/` — a farmer-facing UI over the top that turns "send an LXMF message to the
gateway" into buttons a person can use standing in a field.

Cross-repo context, including how a command reaches a sensor and back, is in the
**Navamesh** repo's `CLAUDE.md`. This file is about this repo.

Branch: **`raw-adc-private-app`**. Current release **1.9.19** (`android.numeric_version = 20260828`), 2026-08-24.

**Most farmer-facing wording is not in this repo.** The app sends a verb and renders
whatever the gateway returns, so `help` and every reply body — soil, status, node list,
map summaries — are rendered by the Pi's `reticulum_bridge.py`. Rewording any of them
needs a Pi deploy and **no APK rebuild**. What lives here is the button labels, the
confirmation dialogs and the value presets in `command_registry.py`. When both are in
play, keep them saying the same thing: the Pi's `test_farmer_wording.py` pins its help
text to the same vocabulary as these buttons.

## Built 2026-08-24: manual interval entry, and a reply area that fits

**"Enter a time" beside the interval presets.** A number plus a Minutes/Hours button, in
`ConfirmCommandDialog._build_manual_value_step()`. A considered exception to the
presets-only rule, not a gap: farmers asked to time a specific node rather than pick from a
list. The precedent is `set_location`'s "Enter coordinates", but note the difference that
matters — a coordinate pair has no numeric bounds, so `get_wire()` skips its range check;
an interval is an int and the bounds *do* apply, so `validate_manual_value()` enforces them
before the confirm step and `get_wire()` still enforces them after. Bounds stay triplicated
(UI → `command_proto.py` → firmware clamp) and there is exactly **one** copy inside this
repo, so the manual and preset paths cannot disagree.

The wire string is unchanged (`interval <id> <seconds>`) — the app converts, so neither the
Pi nor the firmware had to learn units. The confirm step reads back in the farmer's units
("every 45 minutes", not "2700 seconds"), because that screen is the last thing between a
tap and a reconfigured node.

**The conversation screen scrolls as one page.** Previously only the reply area scrolled,
under a fixed gateway strip and a 14-tile grid that between them took most of a phone
screen. A `help` reply is 27 lines and arrived in a viewport showing about eight, so a
complete answer read as a truncated one. The grid now scrolls away with everything else;
only `BackBar` stays pinned. Two things that break if this is edited carelessly: the
scrolling column must track `minimum_height` or it collapses, and `EmptyState` stretches by
default so it needs an explicit height to survive in that column. A new reply calls
`_reveal_replies()`, deferred one frame because a `ResultCard`'s height comes from its label
texture and is still 0 at the moment it is added.

**Gateway reply text wraps at about 44 columns** on the deployed handsets (measured on a
moto g play, 2026-08-24). That is a *Pi-side* constraint, since the reply bodies are composed
in `reticulum_bridge.py` — its `test_farmer_wording.py` now pins the help text to 43 columns.
Worth knowing here because the symptom appears in this app: an over-wide line wraps to column
0 and collides with the deliberate 6-space continuation indents, which reads as corruption
rather than as wrapping.

## Where our code lives

`sbapp/farmui/` is ours. Nearly everything else is upstream Sideband, and
**`docs/DECISION.md` marks which upstream files are protected** — read it before editing
outside `farmui/`. The pattern throughout is to add alongside upstream rather than modify
it, so rebases stay possible.

| File | Does |
|---|---|
| `command_registry.py` | the button list: label, wire string, bounds, confirm text |
| `app.py` | app lifecycle, the update checker, command dispatch |
| `updater.py` | OTA: version check, DownloadManager, PackageInstaller |
| `location.py` | one-shot GPS fix for "Change sensor location" |
| `settings.py` | farmui-local JSON prefs (never touches RNS/Sideband config) |
| `widgets.py`, `screens/` | the UI itself |

## Building

```bash
bash scripts/build_apk.sh          # Docker; ~5-10 min warm, 30-60 cold
```

Output lands in `dist/navameshfarm-<version>-arm64-v8a-debug.apk`. The script never
bind-mounts the source — Docker Desktop's VirtioFS breaks python-for-android with
`EDEADLK`, so it `docker cp`s into a volume instead. That is deliberate; do not "simplify"
it.

**Both version fields must move together.** `__version__` in `sbapp/main.py` drives what
the OTA offers; `android.numeric_version` in `sbapp/buildozer.spec` is what Android checks.
Bump one without the other and the update is offered but refuses to install.

### The cleartext patch, which is load-bearing

`scripts/build_apk.sh` patches `android:usesCleartextTraffic="true"` into p4a's manifest
templates. Without it **DownloadManager cannot download at all** — Android blocks
plaintext HTTP for its own network stack (though never for `urllib`, which is why the
update *checker* worked over http for months and hid this).

Two things about that patch worth knowing before touching it:

- buildozer's documented option, `android.extra_manifest_application_arguments`, is
  **broken in 1.5.0**: it shell-escapes the value then passes argv as a list, so the
  attribute lands in the manifest quotes and all and aapt2 rejects it. That is why we
  patch templates instead.
- It must patch **both** the bootstrap source and the dist's own copy. p4a copies
  templates into the dist at creation and renders from that copy afterwards, so patching
  only the source silently changes nothing against an existing dist. The step fails the
  build if a dist template is missed — leave that guard in.

A build made outside `build_apk.sh` (the Linux-VM/CI path in `docs/BUILD.md`) does not get
this and produces an app that cannot update itself.

## Publishing an update

```bash
bash scripts/publish_update.sh pi@<host> [remote-dir]
```

It takes the newest APK in `dist/` **by mtime**, so rebuilding an older branch before
publishing silently ships the wrong one — check the filename it echoes. It defaults to
`/home/pi/navamesh-updates`; the test Pi uses `/home/tj/navamesh-updates`, so pass it.

**`dist/` is per-machine and can be far behind.** On the Fedora box it holds only
**1.9.10** while the dev Pi is already serving **1.9.18** — so running this script from
that machine would publish an eight-version regression, and the `version.json` it writes
would point the whole fleet at it. Check what the Pi is already serving
(`cat ~/navamesh-updates/version.json`) before publishing from anywhere.

State as of 2026-08-23: the dev Pi (`/home/tj/navamesh-updates`) serves **1.9.18**;
`spirit-farm-pi` (`/home/pi/navamesh-updates`) still serves **1.9.8** and needs the
newer APK copied over during the deployment rollout.

`scripts/pi_update_server/` holds the Pi side: a Range-capable static server. The stock
`python -m http.server` answers a Range request with 200 and the whole file, which meant an
interrupted 91 MB download restarted from byte 0 and DownloadManager's resume had nothing
to resume against.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q \
  --ignore=tests/test_e2e_conversation.py --ignore=tests/test_protocol_roundtrip.py
```

**268 passed.** The two ignored modules need a live RNS TCP testnet. Unlike the Navamesh
repo, this suite does not silently skip — a `.venv` is present and complete.

Android-only glue (jnius, PackageInstaller, LocationManager) is covered by **source
guards**: tests that assert on `inspect.getsource()` rather than executing it. That is not
laziness — it cannot run off-device — but it means the jnius bindings themselves are only
ever proven by installing on a phone.

## Why the OTA and GPS code look the way they do

**Downloads go through Android's `DownloadManager`, not a worker thread.** An in-process
download lost on every front the moment the screen slept: the CPU suspended it, Doze cut
the app's network, and nothing resumed, so each retry restarted 91 MB from zero. The
download id is persisted in `FarmSettings.pending_download` because it outlives the
process — a transfer that finishes while the app is closed must not be orphaned.

**GPS reads `LocationManager` directly through jnius, not plyer.** plyer's Android facade
forwards six scalars and **drops the timestamp**, so there was no way to tell a fresh fix
from the cached one Android hands every newly-registered listener — which is the fix from
wherever the farmer previously stood. Setting a node's position from that pins it to the
wrong place and looks entirely plausible doing it. `is_fresh_fix()` rejects anything stale
or predating the request.

**Thresholds in `location.py` are tuned for satellite-only.** The deployed phones have no
SIM and leave Google Location Accuracy off, so every fix comes from GNSS. 15 m because
sensors share a garden bench; 120 s because an unassisted cold start is 30-90 s and the
old 25 s ceiling cut it off every time.
