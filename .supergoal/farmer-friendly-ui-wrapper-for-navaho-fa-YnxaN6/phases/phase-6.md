SUPERGOAL_PHASE_START
Phase: 6 of 8 — Android packaging
Task: Produce the installable Navamesh Farm debug APK using Sideband's own buildozer/p4a chain (Dockerized), with packaging-metadata-only spec edits and an on-device smoke checklist.
Type: build, packaging
Mandatory commands: bash scripts/build_apk.sh, git diff upstream-pin -- sbapp/buildozer.spec, bash scripts/check_upstream_integrity.sh, .venv/bin/python -m pytest tests/ -q
Acceptance criteria: 5
Evidence required: APK ls -lh + unzip listing, spec diff, device smoke results
Depends on phases: 3, 4, 5

## Why

Farmers install an APK; Sideband's build chain is the proven path and only packaging metadata may change.

## Work

- Edit `sbapp/buildozer.spec` ONLY: `title = Navamesh Farm`, `package.name = navameshfarm`, `package.domain` (e.g. `farm.navaho`), `icon.filename`, `presplash.filename`, `version`. Requirements, permissions, services (`sidebandservice:services/sidebandservice.py:foreground`), api levels: UNTOUCHED.
- App icon + presplash assets under `sbapp/assets/farm/` (new files): simple high-contrast sprout/radio mark.
- Verify the Android branch of `farmui/app.py` (client mode + service start intent) matches `main_upstream.py`'s pattern: starting the foreground service, `SidebandCore(is_client=True, …)`, lifecycle (pause/resume) hooks. The service file itself stays untouched and still imports the unmodified core.
- `scripts/build_apk.sh`: run buildozer in a Linux container (e.g. official buildozer image or ubuntu + pinned buildozer/p4a per upstream Makefile), caching SDK/NDK in a named volume; copy APK to `dist/`. Document Linux-VM fallback in `docs/BUILD.md`. Expect the first build to take a long time (SDK/NDK download) — that's normal, let it run.
- `docs/DEVICE_SMOKE.md`: numbered on-device checklist — install, service notification appears, three screens navigate, announce sends, gateway announce appears in stream (against rig-on-laptop over Wi-Fi UDP or the real Pi), pin gateway, soil command round-trips, map renders. Leave a results column; fill in what can be verified on emulator; flag device-only rows for the user.

## Acceptance criteria (all must pass — verify each in transcript)

- `dist/navamesh-farm-*-debug.apk` exists; `unzip -l` shows app classes + service entries; build log tail shown
- buildozer.spec diff vs upstream-pin touches only the 5 metadata keys + icon/presplash paths
- EITHER (a) app launches on an emulator/device: service notification + three screens, screenshots recorded in DEVICE_SMOKE.md, OR (b) no emulator/device obtainable in this environment after a real attempt (attempt + failure output shown in transcript): APK structural verification passes (unzip shows farmui code, service entry, assets) AND every launch-dependent row in DEVICE_SMOKE.md is marked "user field test" — the transcript must state explicitly which branch applied
- Integrity guard green (covers untouched sidebandservice.py and core)
- Desktop pytest still green

## Mandatory commands (run each, surface last ~10 lines + exit code)

- `bash scripts/build_apk.sh`
- `git diff upstream-pin -- sbapp/buildozer.spec`
- `bash scripts/check_upstream_integrity.sh`
- `.venv/bin/python -m pytest tests/ -q`

## Evidence required in transcript

- APK `ls -lh` + unzip listing excerpt
- Full spec diff
- DEVICE_SMOKE.md with filled results column

## Notes

This is the highest-risk phase (p4a on a mac host via Docker; arm64 host quirks). If the containerized build fails after honest attempts, follow the 3-strike protocol; an acceptable phase outcome on strike 3 is NOT silence — the FAILURE_HANDOFF must include the exact failing step and the documented Linux-VM/CI alternative in docs/BUILD.md. Do not weaken the spec edits constraint to make the build pass.
