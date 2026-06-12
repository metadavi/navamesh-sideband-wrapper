# Thinking — Navamesh Farm App (farmer-friendly Sideband/Reticulum wrapper)

## Goals
- A beautiful, dead-simple Android app for farmers: three surfaces — **Announce**, **Announce Stream**, **Gateway Conversation** — where every gateway interaction is a big tappable button (status, soil, battery, position, link, map, map <id>, nodes, help). No typing, ever.
- Preserve the exact current communication behavior: standard LXMF messages to the existing `reticulum_bridge.py` gateway on the Pi; standard RNS announces; standard identities; nothing protocol-level changes.
- Reticulum and Sideband treated strictly as upstream dependencies / pinned vendored code.

## Architecture decision (the central call)

**Chosen: Sideband fork with a minimal replacement UI layer ("farm UI"), keeping the entire Sideband core + service layer byte-identical to a pinned upstream release, with RNS and LXMF as unmodified pip dependencies.**

Why this beats the alternatives:

| Option | Verdict | Reason |
|---|---|---|
| **Fork Sideband, replace only UI layer** | ✅ chosen | `sbapp/sideband/core.py` (5,502 lines) is a deliberately headless core: it owns RNS init, the LXMF router, announces, conversations, and the message DB, and already runs as the Android foreground service (`sbapp/services/sidebandservice.py`). The Kivy UI (`sbapp/main.py`, `sbapp/ui/`) sits cleanly on top via a small API: `lxmf_announce()`, `list_announces()`, `send_message()`, `list_messages()`, `list_conversations()`. Replacing the UI while keeping core byte-identical gives us: the solved Android build chain (buildozer + p4a + local recipes), the solved service/client split, and zero protocol risk. |
| New Android app from scratch on rns+lxmf | ❌ | Would re-solve p4a recipes, the Android foreground-service split, identity storage, notification plumbing — months of work Sideband already did, with far more chance of subtle behavioral divergence. |
| Companion/desktop/web app | ❌ | User confirmed the target is the farmer's Android phone over Wi-Fi to an HT-HD01. |
| Modify Sideband screens in place | ❌ | Touching existing UI files invites drift; we add new files and one thin entry shim instead. |

**Connectivity decision:** the phone reaches the Reticulum network via **UDPInterface over Wi-Fi to the Heltec HT-HD01 (HaLow)** → Pi's HT-HD01 → Pi RNS. Sideband's own generated RNS config template ends with an `[interfaces]` section explicitly inviting custom interfaces. RNS instantiates `UDPInterface` from config natively (`RNS/Interfaces/UDPInterface.py` upstream). **The HT-HD01 link is therefore pure configuration — zero code changes to RNS or Sideband core networking.**

**Compatibility guarantee:** the gateway side (`reticulum_bridge.py` in Navamesh-main, read-only) only sees standard LXMF messages whose content is a command word. Any standards-compliant LXMF client is compatible by construction — including stock Sideband running anywhere. Our fork's core IS stock Sideband core, so announce/path/delivery behavior is identical by construction, and we prove it with diff guards + protocol regression tests.

## Constraints
- DO NOT modify: `rns`, `lxmf` (pinned pip deps); `sbapp/sideband/**`; `sbapp/services/**`; vendored libs (`sbapp/kivymd`, `sbapp/mapview`, `sbapp/plyer`, `sbapp/pmqtt`, `libs/`, `recipes/`, `patches/`); existing `sbapp/ui/**` files.
- `sbapp/main.py` is UI-layer: replaced by a ~3-line shim dispatching to the new `farmui` package (p4a requires the entry file to be `main.py`). Upstream original preserved verbatim as `sbapp/main_upstream.py` for diffing.
- `~/Desktop/Navamesh-main` is read-only reference. New project lives in `~/Desktop/Navamesh_sideband_wrapper`.
- License: Sideband is **CC BY-NC-SA 4.0** → the fork must keep attribution, stay non-commercial, share-alike. Internal farm tool: compliant; NOTICE file required.

## Risks (top 3)
1. **Android APK build chain (buildozer/p4a) on macOS** — likelihood: high. Mitigation: dedicated phase; use Sideband's own Makefile targets inside a Linux Docker container; document a Linux-VM fallback; everything before that phase runs and is verified on desktop (Sideband runs on desktop via the same core).
2. **Service/client split on Android** — the farm UI must instantiate `SidebandCore(is_client=True…)` exactly as `main.py` does, or the shared-instance plumbing breaks. Mitigation: copy the instantiation/lifecycle pattern verbatim from upstream `main.py`; keep `sidebandservice.py` untouched; device smoke checklist in the packaging phase.
3. **Behavioral drift creeping in via "small" core edits** — mitigation: `scripts/check_upstream_integrity.sh` (tree-hash comparison of protected paths against the pinned upstream commit) is a mandatory command in every phase from phase 1 on; any failure is a hard stop.

## Dependencies / ordering
- Protocol test rig (phase 2) must exist before any UI work so every UI phase verifies against a real LXMF round-trip, not mocks.
- Gateway pinning UX depends on announce stream (both phase 3/4).
- UDP interface config (phase 5) is independent of UI but must precede Android packaging so the APK ships with the right connectivity story.

## Open questions (assumed, surfaced in plan review)
- Upstream pin = latest Sideband release tag at clone time (1.9.x) and the rns/lxmf versions its setup.py requires.
- Gateway discovery: farmer taps the gateway's announce in the stream → "Set as my farm gateway" (also manual hex entry in a settings corner). Default display name filter: "Navamesh Gateway".
- The HT-HD01's UDP port/IP are deployment config (an `.env`-style settings screen field + documented RNS config snippet), not hardcoded.
- `map` replies arrive as `LXMF.FIELD_IMAGE` JPEG ≤ ~12 KB (lora profile) — UI renders inline with pinch-zoom.

## Memory hits applied
None — memory directory empty (first run on this machine for this project).

## Tools/skills relied on
- WebFetch/WebSearch available if upstream docs needed mid-run; Context7 absent — planned against cloned source (better than docs anyway).
- Local shallow clones of Sideband + Reticulum in `<run-root>/research/` for study; the build vendors its own fresh pinned clone.

## Best practices applied
- Fork hygiene: pinned upstream commit recorded in `UPSTREAM.lock`; protected-path tree-hash guard; all new code in new files/packages.
- Testability: a stub gateway reproducing the exact `reticulum_bridge.py` command contract lets the full app be exercised on desktop over a loopback RNS testnet (TCP + UDP variants) with no hardware.
- Farmer UX: ≥48dp touch targets (we target ~96dp primary buttons), WCAG AA contrast, color + icon + word triple-coding for soil status (never color alone), plain-language copy, large-text mode.
