# Roadmap: Navamesh Farm App — farmer-friendly Sideband/Reticulum wrapper

**Task:** Build an Android farmer UI (Announce / Announce Stream / button-only Gateway Conversation) as a minimal-UI-layer Sideband fork that preserves exact Reticulum/Sideband communication behavior with the existing Navamesh Pi gateway.
**Type:** greenfield (new repo) + fork-integration, ui
**Created:** 2026-06-12
**Total phases:** 8

## Context summary

- **Stack:** Python 3.11/3.12 venv (rns/lxmf/kivy run on macOS for dev), Kivy/KivyMD UI inside a pinned Sideband fork, buildozer + python-for-android (Docker) for the Android APK.
- **Package manager:** pip (venv at `.venv/`); Android deps via Sideband's own `buildozer.spec`.
- **Build / test / lint commands:** `bash scripts/check_upstream_integrity.sh` · `.venv/bin/python -m pytest tests/ -q` · `.venv/bin/python -m compileall sbapp/farmui tests` · (phase 6 only) Dockerized `make apk`.
- **Risky areas:** buildozer/p4a Android build on macOS; Android service/client shared-instance plumbing; accidental edits to protected upstream paths.

## Hard constraints (from user — restated, enforced every phase)

- DO NOT rewrite or modify Reticulum (`rns`) or LXMF — unmodified, pinned pip dependencies.
- DO NOT alter Reticulum networking, routing, crypto, announces, identities, LXMF behavior, transport, or Sideband protocol behavior.
- Sideband core is vendored at a pinned upstream commit and kept **byte-identical** in protected paths (verified by `scripts/check_upstream_integrity.sh` every phase).
- `~/Desktop/Navamesh-main` is read-only reference; never modified; the new project never created inside it.

## Do-not-touch vs safe-to-touch map

**DO NOT TOUCH (protected paths — tree-hash-guarded against the pin):**
| Path | What it is |
|---|---|
| `rns`, `lxmf` pip packages | Reticulum + LXMF — upstream deps, pinned versions |
| `sbapp/sideband/**` | SidebandCore: RNS init, LXMF router, announces, conversations, message DB |
| `sbapp/services/**` | Android foreground service running the core headless |
| `sbapp/ui/**` (existing files) | Stock Sideband screens — left intact, not imported by farm UI |
| `sbapp/kivymd`, `sbapp/mapview`, `sbapp/plyer`, `sbapp/pmqtt`, `sbapp/md`, `sbapp/share`, `libs/`, `recipes/`, `patches/` | Vendored libs + p4a recipes/patches (build chain) |
| `sbapp/main_upstream.py` | Upstream `main.py` preserved verbatim for diffing |
| `~/Desktop/Navamesh-main/**` | Existing working pipeline — read-only |

**SAFE TO TOUCH / CREATE:**
| Path | What |
|---|---|
| `sbapp/main.py` | Becomes a ~3-line shim → `farmui` (p4a requires entry named `main.py`); the single modified upstream file, UI-layer only |
| `sbapp/farmui/**` (new) | All farm UI code: app shell, 3 screens, command registry, response presenter, theme |
| `sbapp/buildozer.spec` | Packaging metadata only: title, package.name/domain, icon, presplash, version |
| `setup.py` | Additive: `navamesh-farm` console entry point for desktop dev runs |
| `tests/**`, `scripts/**`, `docs/**`, `deploy/**`, `README.md`, `NOTICE` (all new) | Test rig, guards, docs, RNS config snippets |

## Assumptions

Non-blocking decisions recorded so the run can proceed; correct any that are wrong:

- Upstream pin = the latest Sideband release tag at vendoring time (1.9.x line) and the rns/lxmf versions its `setup.py` declares.
- Gateway selection UX: tap the gateway's announce in the stream → "Set as my farm gateway"; manual hex entry kept in a small settings screen. Default announce highlight matches display name "Navamesh Gateway".
- HT-HD01 IP/port for the phone-side UDPInterface are deployment settings (settings screen + documented RNS config snippet), defaulting to broadcast on the Wi-Fi subnet, port matching the Pi's `HTHD01_UDP` interface.
- v1 commands exactly mirror the gateway: `status, soil, battery, position, link, map, map <id>, nodes, help`. `map <id>` gets a node picker fed by cached `nodes` results.
- Design: big & legible farm-utility (≈96dp primary buttons, AA contrast, color+icon+word coding, plain language, large-text toggle).
- Android minimum matches upstream Sideband (minapi 24, api 33); APK is debug-signed for farm sideloading in v1.

## Risk top 3

1. **buildozer/p4a APK build on macOS** — likelihood: high. Mitigation: isolated phase 6; build inside Linux Docker using Sideband's own Makefile; Linux-VM fallback documented; all functionality verified on desktop first.
2. **Android service/client split breaks if instantiation drifts from upstream** — likelihood: medium. Mitigation: `farmui` copies `main.py`'s `SidebandCore(is_client=True…)` lifecycle verbatim; `sidebandservice.py` untouched; device smoke checklist.
3. **Silent edits to protected upstream paths** — likelihood: medium (easy to do accidentally). Mitigation: integrity guard is a mandatory command in every phase; CI-style hard stop on any diff.

## Phase map

| # | Phase | Depends on | Deliverable |
|---|-------|------------|-------------|
| 1 | Scaffold fork & pin upstream | — | Repo with pinned Sideband vendored, integrity guard green, ARCHITECTURE.md + DECISION.md + NOTICE |
| 2 | Protocol rig & stub gateway | 1 | Loopback RNS testnet + stub Navamesh gateway; pytest proves LXMF command round-trips |
| 3 | Farm UI shell (desktop) | 1 | `farmui` package: app shell + 3 navigable screens, big-button design, desktop launch + screenshots |
| 4 | Conversation command flow | 2, 3 | Buttons → LXMF → gateway → readable cards (incl. map image), node picker, gateway pinning |
| 5 | HT-HD01 UDP connectivity | 1, 2 | Config-only UDPInterface wiring, connectivity status UI, deploy snippets; UDP loopback test green |
| 6 | Android packaging | 3, 4, 5 | Debug APK built via Dockerized buildozer; device/emulator smoke checklist |
| 7 | Behavior-preservation proof | 2, 4, 5 | TESTING.md mapping every "unchanged" guarantee → automated/manual evidence; full suite green |
| 8 | Polish & Harden | 1–7 | Every aspect verified: states, a11y, copy, perf, docs (farmer guide + deployment), final audit |

---

## Phase 1 — Scaffold fork & pin upstream

**Why:** Everything depends on a clean fork with the upstream pin and the integrity guard in place before any code is written.

**Deliverables:**
- Git repo initialized in `~/Desktop/Navamesh_sideband_wrapper` with vendored Sideband at pinned tag; `UPSTREAM.lock` (repo URL + tag + commit sha + protected-path tree hashes)
- `sbapp/main_upstream.py` (verbatim copy of upstream `main.py`)
- `scripts/check_upstream_integrity.sh` — recomputes tree hashes of all protected paths, fails non-zero on any drift
- `docs/ARCHITECTURE.md` (current pipeline + where the wrapper sits) and `docs/DECISION.md` (fork-vs-wrapper-vs-companion analysis and the chosen seam)
- `NOTICE` (CC BY-NC-SA 4.0 attribution), `README.md`, `.venv` with pinned `rns`/`lxmf` (+ dev deps), `requirements-dev.txt`

**Acceptance criteria:**
- [ ] `git log` shows an initial commit of pristine vendored upstream, separate from any later commits (clean diff baseline)
- [ ] `UPSTREAM.lock` records URL, tag, commit sha, and per-protected-path tree hashes
- [ ] `scripts/check_upstream_integrity.sh` exits 0 on the pristine tree and exits non-zero when a protected file is test-mutated (demonstrated, then reverted)
- [ ] `pip show rns lxmf` versions match `UPSTREAM.lock` pins
- [ ] `docs/DECISION.md` covers all five candidate approaches with the safe/unsafe file map
- [ ] `~/Desktop/Navamesh-main` untouched (`find` mtime check printed)

**Mandatory commands:**
- `bash scripts/check_upstream_integrity.sh`
- `.venv/bin/python -c "import RNS, LXMF; print(RNS.__file__, LXMF.__file__)"`
- `git -C ~/Desktop/Navamesh_sideband_wrapper log --oneline | tail -5`

**Evidence required:** integrity script pass+fail demo output; UPSTREAM.lock contents; pip pin printout.

**Dependencies:** none

---

## Phase 2 — Protocol rig & stub gateway

**Why:** A real LXMF round-trip harness on loopback proves the protocol seam before any UI exists, and becomes the regression net every later phase runs against.

**Deliverables:**
- `tests/rig/stub_gateway.py` — standalone LXMF gateway replicating `reticulum_bridge.py`'s exact command contract (status/soil/battery/position/link/map/map <id>/nodes/help; map returns a small JPEG via `LXMF.FIELD_IMAGE`), backed by fixture node data (no Postgres)
- `tests/rig/rns_testnet.py` — spins two isolated RNS instances (distinct configdirs) joined over loopback TCPInterface
- `tests/test_protocol_roundtrip.py` — client identity announces, resolves the gateway, sends each command, asserts reply shape/content for all 9 commands

**Acceptance criteria:**
- [ ] All 9 commands round-trip with asserted replies (text contracts + image field for `map`)
- [ ] Announce from client is received by gateway rig (and vice versa) using only public RNS/LXMF APIs
- [ ] Rig uses ONLY unmodified `rns`/`lxmf` pip packages — no Sideband imports needed at this layer
- [ ] Stub gateway's command surface documented as a table cross-referenced to `reticulum_bridge.py` line numbers (read-only reference)
- [ ] Suite green and repeatable: 3 consecutive runs pass (no port/timing flakes)
- [ ] Integrity guard still green

**Mandatory commands:**
- `.venv/bin/python -m pytest tests/ -q` (×3 runs shown)
- `bash scripts/check_upstream_integrity.sh`

**Evidence required:** pytest output ×3; one full command/response transcript printed (e.g. `soil`).

**Dependencies:** 1

---

## Phase 3 — Farm UI shell (desktop)

**Why:** The three-screen skeleton with the farm-utility design system must be navigable and demo-able on desktop before wiring real messaging.

**Deliverables:**
- `sbapp/farmui/` package: `app.py` (FarmApp shell, instantiates `SidebandCore` exactly as upstream `main.py` does), `theme.py` (design tokens: type scale, color roles incl. soil red/green/blue triple-coding), `screens/announce.py`, `screens/stream.py`, `screens/conversation.py`, `widgets.py` (BigButton ≥96dp, ResultCard, StatusChip)
- `sbapp/main.py` shim (≤5 lines → `farmui.app.run()`); upstream preserved at `sbapp/main_upstream.py`
- `setup.py` additive entry point `navamesh-farm`
- Bottom-tab navigation between the three screens; Announce screen shows own LXMF address + big "Send Announce" button; Stream screen lists heard announces (gateway highlighted + "Set as my farm gateway"); Conversation screen shows the 9 command buttons grid + message list area
- `tests/test_farmui_logic.py` — pure-logic tests (command registry完整ness, theme contrast ratios ≥ AA computed, announce-list adapter)

**Acceptance criteria:**
- [ ] `navamesh-farm` (or `.venv/bin/python sbapp/main.py`) launches on desktop; all three screens reachable; screenshot of each captured to `docs/screenshots/`
- [ ] `SidebandCore` instantiation matches upstream `main.py` pattern (side-by-side diff shown in transcript)
- [ ] No file under protected paths modified (integrity guard green); `farmui` imports core only via its public methods
- [ ] All 9 commands present as buttons with icon + plain-language label (e.g. "💧 Soil moisture")
- [ ] Computed contrast ratio for every text/background token pair ≥ 4.5:1 (test asserts)
- [ ] `pytest` green; `compileall` clean

**Mandatory commands:**
- `.venv/bin/python -m pytest tests/ -q`
- `.venv/bin/python -m compileall sbapp/farmui tests`
- `bash scripts/check_upstream_integrity.sh`

**Evidence required:** three screenshots; SidebandCore instantiation diff; pytest output.

**Dependencies:** 1

---

## Phase 4 — Conversation command flow end-to-end

**Why:** This is the product: button tap → LXMF message → gateway → readable reply card, proven against the phase-2 rig with zero protocol deviation.

**Deliverables:**
- Command dispatch in `farmui`: button → `SidebandCore.send_message()` to the pinned gateway; replies consumed via core's message APIs and rendered as ResultCards (monospace body for tabular text, inline zoomable image for `map`)
- Node picker sheet for `map <id>` populated from the latest `nodes` reply (cached locally in farmui only)
- Gateway pinning flow: tap announce → confirm → stored in farmui settings (not in core config)
- Sending/pending/delivered/failed states surfaced per message (driven by core's existing state, not new protocol logic)
- `tests/test_e2e_conversation.py` — headless: drives the same dispatch functions the buttons call against the rig; asserts all 9 flows including image render path

**Acceptance criteria:**
- [ ] Desktop demo against the rig: every button produces its reply card; `map` shows the image; screenshots captured
- [ ] e2e pytest covers all 9 commands headlessly and is green ×3 runs
- [ ] Message bytes on the wire are plain LXMF content identical in shape to typing the command in stock Sideband (rig logs the raw content string; asserted equal to e.g. `"soil"`)
- [ ] No typing required anywhere in the flow; node picker handles empty/missing `nodes` cache gracefully
- [ ] Failed-delivery path shows a plain-language retry card (simulated by stopping the rig gateway)
- [ ] Integrity guard green

**Mandatory commands:**
- `.venv/bin/python -m pytest tests/ -q` (×3)
- `bash scripts/check_upstream_integrity.sh`

**Evidence required:** wire-content assertion output; screenshots (reply cards + map image + failure state); pytest ×3.

**Dependencies:** 2, 3

---

## Phase 5 — HT-HD01 UDP connectivity

**Why:** The farmer's phone reaches the Pi through Wi-Fi → HT-HD01 (HaLow) via an RNS UDPInterface, and this must be configuration-only to honor the no-core-changes constraint.

**Deliverables:**
- `deploy/rns_udp_hthd01.conf.example` — documented `[interfaces]` snippet (UDPInterface, device IP/port/group) for both phone-side template and Pi-side reference
- farmui settings screen: HT-HD01 IP/port fields that write ONLY into the RNS config template's `[interfaces]` section through Sideband's existing user-editable-template mechanism (config file content, not code)
- Connectivity StatusChip on all screens: interface up/down + last-announce-heard age, read from core/RNS public state
- `tests/test_udp_interface.py` — rig variant joining the two RNS instances over loopback UDPInterface instead of TCP; full command round-trip re-asserted

**Acceptance criteria:**
- [ ] UDP-variant rig test green ×3 (proves UDPInterface config shape works with unmodified RNS)
- [ ] Settings write produces a valid RNS config (RNS boots cleanly with it; shown in transcript) and never touches any other config section
- [ ] StatusChip reflects up/down transitions when the UDP peer stops (simulated)
- [ ] No new interface code in protected paths — `git diff` shows changes only in `farmui`, `deploy/`, `tests/`
- [ ] Integrity guard green

**Mandatory commands:**
- `.venv/bin/python -m pytest tests/ -q` (×3)
- `bash scripts/check_upstream_integrity.sh`

**Evidence required:** UDP round-trip pytest output; generated config file contents; StatusChip up/down screenshots.

**Dependencies:** 1, 2

---

## Phase 6 — Android packaging

**Why:** Ship the actual APK farmers install, using Sideband's proven build chain with only packaging-metadata edits.

**Deliverables:**
- `buildozer.spec` edits limited to: title "Navamesh Farm", package.name/domain, icon, presplash, version (requirements/permissions/services lines untouched — diff shown)
- `scripts/build_apk.sh` — Dockerized buildozer build (Linux container) wrapping Sideband's Makefile; docs for Linux-VM fallback
- Debug APK at `dist/navamesh-farm-<ver>-debug.apk`
- `docs/DEVICE_SMOKE.md` — on-device checklist: service starts, three screens, announce out, gateway announce heard, soil command round-trip via real or rig gateway over Wi-Fi UDP

**Acceptance criteria:**
- [ ] APK file exists and `unzip -l` shows expected app + service entries; build log tail shown
- [ ] `buildozer.spec` diff vs upstream touches ONLY the 5 metadata keys listed above
- [ ] EITHER launches on emulator/device with screenshots in DEVICE_SMOKE.md, OR a real attempt failed (output shown) and APK structural verification passes with launch-dependent rows marked "user field test" — transcript states which branch applied
- [ ] `sidebandservice.py` byte-identical (integrity guard covers it; restated here)
- [ ] Integrity guard green; full pytest still green on desktop

**Mandatory commands:**
- `bash scripts/build_apk.sh` (long-running; tail of log + exit code)
- `git diff main_upstream_pin -- sbapp/buildozer.spec | head -40` (or equivalent pinned-baseline diff)
- `bash scripts/check_upstream_integrity.sh`
- `.venv/bin/python -m pytest tests/ -q`

**Evidence required:** APK ls -lh + unzip listing; spec diff; device smoke results.

**Dependencies:** 3, 4, 5

---

## Phase 7 — Behavior-preservation proof

**Why:** The user's hard constraint is "exact current communication functionality preserved" — this phase turns that from a claim into a documented, re-runnable proof.

**Deliverables:**
- `docs/TESTING.md` — a guarantee→evidence matrix: each protected behavior (identities, announces, LXMF message format, DIRECT/OPPORTUNISTIC delivery, routing/transport untouched, crypto untouched) mapped to (a) the integrity-guard path proving the code is byte-identical, and/or (b) the rig test proving observable behavior, and/or (c) a manual field-test step against the real Pi gateway
- `tests/test_stock_equivalence.py` — sends the same command once via a minimal "stock-style" raw LXMF client (plain rns+lxmf, the way Sideband would) and once via farmui's dispatch path; asserts byte-equal message content fields
- `docs/FIELD_TEST_PLAN.md` — step-by-step real-hardware validation with the actual Pi `reticulum_bridge.py` (announce seen in Sideband on another device, all 9 commands from the farm app, stock Sideband still works in parallel)

**Acceptance criteria:**
- [ ] Equivalence test green: farmui-path LXMF content == stock-path LXMF content for representative commands
- [ ] TESTING.md matrix has NO row whose evidence column is empty or hand-wavy ("trust me" rows fail review)
- [ ] Full suite green ×3; integrity guard green
- [ ] FIELD_TEST_PLAN.md: every numbered step has an `Expected:` line (step count == Expected count, both printed)

**Mandatory commands:**
- `.venv/bin/python -m pytest tests/ -q` (×3)
- `bash scripts/check_upstream_integrity.sh`

**Evidence required:** equivalence assertion output; TESTING.md matrix rendered in transcript.

**Dependencies:** 2, 4, 5

---

## Phase 8 — Polish & Harden

**Why:** Catch what shipping-focused phases missed; this is how "beautiful, simple, farmer-friendly" gets enforced rather than asserted.

**Sub-passes (each must produce evidence):**
- [ ] **UX & copy** — every visible string plain-language, no jargon ("RSSI" gets a helper line "signal strength"), no debug placeholders
- [ ] **States** — empty (no announces yet / no gateway pinned / no replies), loading/sending, error (gateway unreachable, radio down), first-run onboarding card
- [ ] **Edges** — gateway never announces; huge `nodes` list; reply while app backgrounded; clock-skew timestamps; image decode failure
- [ ] **A11y** — large-text toggle scales all screens; contrast re-verified; touch targets ≥48dp measured; color-blind safe (icon+word coding asserted)
- [ ] **Security** — no secrets in repo; settings input validation (IP/port); no new network surface beyond RNS config
- [ ] **Perf** — UI thread never blocked by core calls (dispatch off-thread); announce list virtualized beyond 100 entries
- [ ] **Docs** — `docs/FARMER_GUIDE.md` (with screenshots, ≤2 pages, plain language) + `docs/DEPLOYMENT.md` (Pi-side notes, HT-HD01 config, APK install)
- [ ] **Diff review** — full diff vs pinned baseline reviewed; no stray debug logs/TODOs; integrity guard final pass
- [ ] **Regression sweep** — full suite ×3 + desktop demo of all three screens re-screenshotted

**Mandatory commands:**
- `.venv/bin/python -m pytest tests/ -q` (×3)
- `.venv/bin/python -m compileall sbapp/farmui tests`
- `bash scripts/check_upstream_integrity.sh`
- `git diff --stat <pinned-baseline>..HEAD`

**Evidence required:** one paragraph per sub-pass; final diff --stat; final screenshots (normal + large-text).

**Dependencies:** 1–7
