# Decision: Architecture for the Navamesh Farm UI

## Five candidate approaches

| # | Approach | Summary | Safe? | Why rejected / chosen |
|---|----------|---------|-------|------------------------|
| 1 | **Sideband UI fork (minimal UI layer)** ✓ CHOSEN | Vendor Sideband at a pinned tag; add `sbapp/farmui/` package; replace only `main.py` with a 3-line shim. Protected paths byte-identical. | ✓ | Only approach that keeps Reticulum/LXMF behavior 100% unchanged while shipping a custom UX. License (CC BY-NC-SA 4.0) permits this with attribution. |
| 2 | Wrapper app (separate process) | Separate Python app that talks to a running Sideband instance via IPC or its shared SQLite DB. | Risky | Sideband has no stable IPC API; DB schema not public; fragile to Sideband updates. |
| 3 | Companion app | Separate Kivy app that uses rns+lxmf directly, bypassing Sideband entirely. | Risky | Duplicates identity management and transport init; subtle divergence from Sideband behavior is likely (announce timing, crypto params, DIRECT vs OPPORTUNISTIC defaults). |
| 4 | Android frontend from scratch | Write a new Android app in Kotlin/Java, implement LXMF from scratch. | ✗ | Enormous scope; re-implementing the crypto/routing layer correctly is error-prone; no benefit over the fork. |
| 5 | Web kiosk | Flask/FastAPI server on the Pi exposes a web UI; farmer uses a browser. | ✗ | Adds a server surface on the Pi; no offline capability; loses Reticulum's mesh properties. |

## The seam: what the fork touches and what it doesn't

### DO NOT TOUCH (protected, tree-hash-guarded)

| Path | What |
|------|------|
| `sbapp/sideband/` | SidebandCore: RNS init, LXMF router, announces, conversations, message DB |
| `sbapp/services/` | Android foreground service |
| `sbapp/ui/` | Stock Sideband screens |
| `sbapp/kivymd/`, `sbapp/mapview/`, `sbapp/plyer/`, `sbapp/pmqtt/`, `sbapp/md/`, `sbapp/share/` | Vendored UI libs |
| `libs/`, `recipes/`, `sbapp/patches/` | p4a build chain |
| `sbapp/main_upstream.py` | Verbatim copy of upstream `main.py` for diffing |
| `rns`, `lxmf` pip packages | Upstream deps, pinned, unmodified |

### SAFE TO CREATE

| Path | What |
|------|------|
| `sbapp/main.py` | 3-line shim → `farmui.app.run()` (the one allowed modified file) |
| `sbapp/farmui/` | All farm UI: app shell, screens, command registry, theme |
| `sbapp/buildozer.spec` | Packaging metadata only (title/package/icon/version) |
| `setup.py` | Additive entry point `navamesh-farm` |
| `tests/`, `scripts/`, `docs/`, `deploy/` | Test rig, guards, docs, deploy snippets |

## License note

Sideband is licensed CC BY-NC-SA 4.0. This fork is non-commercial (farm utility).  
Attribution is provided in `NOTICE`. The fork does not sublicense or relicense.
