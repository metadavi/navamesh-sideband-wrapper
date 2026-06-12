SUPERGOAL_PHASE_START
Phase: 3 of 8 — Farm UI shell (desktop)
Task: Build the farmui package — app shell on SidebandCore plus three navigable big-button screens (Announce, Announce Stream, Conversation) — running on desktop with the farm-utility design system.
Type: ui, greenfield
Mandatory commands: .venv/bin/python -m pytest tests/ -q, .venv/bin/python -m compileall sbapp/farmui tests, bash scripts/check_upstream_integrity.sh
Acceptance criteria: 6
Evidence required: three screenshots, SidebandCore instantiation diff, pytest output
Depends on phases: 1

## Why

The three-screen skeleton with the farm-utility design system must be navigable and demo-able on desktop before wiring real messaging.

## Work

- New package `sbapp/farmui/`:
  - `app.py` — FarmApp (Kivy/KivyMD app class) instantiating `SidebandCore` EXACTLY as upstream `sbapp/main_upstream.py` does for desktop (`is_client=False`, config paths, getstate/setstate polling pattern) and as a client of the service on Android (mirror both branches; Android branch exercised in phase 6). Core accessed only via public methods: `lxmf_announce()`, `list_announces()`, `send_message()`, `list_messages()`, `list_conversations()`, `getstate/setstate`.
  - `theme.py` — design tokens: type scale (min body 18sp, headings 24–32sp), color roles: soil-dry red `#C62828`, soil-ok green `#2E7D32`, soil-wet blue `#1565C0`, surface/ink pairs; every pair's WCAG contrast computed in a helper.
  - `widgets.py` — `BigButton` (≥96dp height, icon + label), `ResultCard`, `StatusChip`, `EmptyState`.
  - `screens/announce.py` — own LXMF address (pretty hex, large), QR optional, big "📢 Send Announce" button, last-announce-sent time.
  - `screens/stream.py` — announce list (display name, short hash, time-ago), gateway-name matches highlighted, per-row "Set as my farm gateway".
  - `screens/conversation.py` — pinned-gateway header + 3x3 grid of the 9 command BigButtons with plain-language labels ("📋 Farm status", "💧 Soil moisture", "🔋 Battery", "📍 Locations", "📡 Signal", "🗺 Map — all", "🗺 Map — one node", "🛰 List nodes", "❓ Help") + scrollable message area (populated for real in phase 4).
- `sbapp/main.py` → ≤5-line shim calling `farmui.app.run()` (the ONLY modified upstream file; upstream preserved as `main_upstream.py`). Commit message states this explicitly.
- `setup.py`: additive `navamesh-farm=sbapp:farmui.app.run`-style console entry (do not remove the upstream `sideband` entry).
- Bottom tab navigation; works with window sizes phone-shaped (e.g. 1080x2400 @ scaled) for screenshots.
- `tests/test_farmui_logic.py` — pure logic, no display required: command registry has exactly the 9 commands with correct wire strings (`"status"`, `"soil"`, `"battery"`, `"position"`, `"link"`, `"map"`, `"map {id}"`, `"nodes"`, `"help"`); contrast helper asserts ≥4.5:1 for all token pairs; announce-list adapter maps core tuples → row models incl. gateway-highlight rule.
- Capture screenshots of all three screens to `docs/screenshots/` (kivy window screenshot or OS capture).

## Acceptance criteria (all must pass — verify each in transcript)

- Desktop launch works; all three screens reachable; 3 screenshots saved and listed
- SidebandCore instantiation side-by-side diff vs `main_upstream.py` shown — same arguments/lifecycle
- Integrity guard green; farmui imports core only via public methods (grep proof: no `sideband.core` internals/underscore attrs)
- All 9 commands present as BigButtons with icon + plain-language label
- Contrast test asserts ≥4.5:1 for every text/background pair and is green
- pytest + compileall clean

## Mandatory commands (run each, surface last ~10 lines + exit code)

- `.venv/bin/python -m pytest tests/ -q`
- `.venv/bin/python -m compileall sbapp/farmui tests`
- `bash scripts/check_upstream_integrity.sh`

## Evidence required in transcript

- ls of docs/screenshots/ + the three files
- Instantiation diff
- pytest output

## Notes

If desktop Kivy can't open a window in this environment, fall back to `KIVY_WINDOW=sdl2` checks or render-to-image via `Widget.export_to_png` in a headless-friendly mode — screenshots are required evidence either way. Design bar: this should look like a purpose-built farm tool, not a dev demo — generous spacing, no dense tables, sunlight-legible contrast.
