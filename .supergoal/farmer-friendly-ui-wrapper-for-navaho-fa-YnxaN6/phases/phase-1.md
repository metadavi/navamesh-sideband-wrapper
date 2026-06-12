SUPERGOAL_PHASE_START
Phase: 1 of 8 — Scaffold fork & pin upstream
Task: Initialize the Navamesh Farm App repo with Sideband vendored at a pinned upstream release, an integrity guard over all protected paths, and the architecture/decision docs.
Type: greenfield, fork-integration
Mandatory commands: bash scripts/check_upstream_integrity.sh, .venv/bin/python -c "import RNS, LXMF; print(RNS.__file__, LXMF.__file__)", git log --oneline | tail -5
Acceptance criteria: 6
Evidence required: integrity pass+fail demo, UPSTREAM.lock contents, pip pin printout
Depends on phases: none

## Why

Everything depends on a clean fork with the upstream pin and a drift guard in place before any code is written — this is what makes "Reticulum/Sideband unchanged" provable later.

## Work

- `git init` in `~/Desktop/Navamesh_sideband_wrapper` (cwd). NEVER write into `~/Desktop/Navamesh-main` (read-only reference).
- Clone Sideband, check out the **latest release tag** (1.9.x line), record URL+tag+sha. Vendor its working tree into the repo (drop upstream `.git`). A study clone already exists at `.supergoal/farmer-friendly-ui-wrapper-for-navaho-fa-YnxaN6/research/Sideband` — but vendor a fresh tag checkout, not the depth-1 main clone.
- First commit = pristine vendored upstream only (clean diff baseline). Tag it `upstream-pin`.
- Copy `sbapp/main.py` → `sbapp/main_upstream.py` verbatim (second commit).
- Write `UPSTREAM.lock`: upstream URL, tag, commit sha, rns/lxmf pinned versions (from upstream setup.py), and a tree hash per protected path.
- Protected paths: `sbapp/sideband/`, `sbapp/services/`, `sbapp/ui/`, `sbapp/kivymd/`, `sbapp/mapview/`, `sbapp/plyer/`, `sbapp/pmqtt/`, `sbapp/md/`, `sbapp/share/`, `libs/`, `recipes/`, `sbapp/patches/` (adjust to actual tree), `sbapp/main_upstream.py`.
- `scripts/check_upstream_integrity.sh`: recompute each protected path's hash (e.g. `git ls-tree`/`tar | shasum` deterministic method), compare to UPSTREAM.lock, exit non-zero with a named-path message on drift. Also assert installed `rns`/`lxmf` versions match the lock.
- Python env: `python3 -m venv .venv`; install pinned `rns`, `lxmf`, plus dev deps (`pytest`, `kivy` per upstream requirement, `kivymd` if upstream expects system one — note Sideband vendors kivymd; desktop run may need upstream-documented deps). `requirements-dev.txt` captures it.
- `docs/ARCHITECTURE.md`: diagram + prose of the existing pipeline (RAK sensors → LoRa → Pi → MQTT → InfluxDB/Postgres → Azure; `reticulum_bridge.py` LXMF gateway; HT-HD01 HaLow path) and where the farm app sits. Reference `~/Desktop/Navamesh-main/src/navamesh/reticulum_bridge.py` by path/line, do not copy code wholesale.
- `docs/DECISION.md`: the five candidate approaches (Sideband UI fork / wrapper app / companion app / Android frontend from scratch / web-kiosk), why fork-with-minimal-UI-layer wins, the safe/unsafe file map (mirror ROADMAP's table), and the license note (CC BY-NC-SA 4.0 → NOTICE).
- `NOTICE` + `README.md` (project intro, constraint statement, how to run the guard).

## Acceptance criteria (all must pass — verify each in transcript)

- git history shows pristine-upstream initial commit tagged `upstream-pin`, then scaffold commits
- UPSTREAM.lock records URL, tag, sha, dep pins, per-path tree hashes
- Integrity script exits 0 pristine; mutate one protected file → exits non-zero naming the path → revert → 0 again (all three shown)
- `pip show rns lxmf` versions match UPSTREAM.lock
- DECISION.md covers all five approaches + safe/unsafe map + license
- `~/Desktop/Navamesh-main` untouched (print a recursive newest-mtime check before/after phase)

## Mandatory commands (run each, surface last ~10 lines + exit code)

- `bash scripts/check_upstream_integrity.sh`
- `.venv/bin/python -c "import RNS, LXMF; print(RNS.__file__, LXMF.__file__)"`
- `git log --oneline | tail -5`

## Evidence required in transcript

- Integrity guard pass + induced-fail + pass-again outputs
- UPSTREAM.lock contents
- pip pin printout matching the lock

## Notes

Hard constraints (apply to EVERY phase): never modify `rns`/`lxmf` packages, protected Sideband paths, or anything under `~/Desktop/Navamesh-main`. All new code lives in new files. If a step seems to require touching a protected path, STOP and record it in STATE.md as a blocker instead of doing it.
