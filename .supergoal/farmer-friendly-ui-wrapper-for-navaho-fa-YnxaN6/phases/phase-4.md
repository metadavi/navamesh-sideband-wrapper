SUPERGOAL_PHASE_START
Phase: 4 of 8 — Conversation command flow end-to-end
Task: Wire the command buttons to real LXMF send/receive through SidebandCore against the phase-2 rig — reply cards, map image rendering, node picker, gateway pinning, delivery states.
Type: ui, integration
Mandatory commands: .venv/bin/python -m pytest tests/ -q (x3), bash scripts/check_upstream_integrity.sh
Acceptance criteria: 6
Evidence required: wire-content assertion output, screenshots (reply cards + map + failure), pytest x3
Depends on phases: 2, 3

## Why

This is the product: button tap → LXMF message → gateway → readable reply card, proven against the rig with zero protocol deviation.

## Work

- Command dispatch module `sbapp/farmui/dispatch.py`: button handler → `SidebandCore.send_message(content=<wire string>, destination_hash=<pinned gateway>, propagation/method = core defaults)`. No custom fields, no custom titles beyond what stock Sideband would produce — the message must be indistinguishable from a typed Sideband message.
- Reply consumption: poll/notify via core's existing message APIs (`list_messages` for the gateway conversation, or the state/notification hooks main_upstream.py uses); render each reply as a `ResultCard` — monospace body for the gateway's aligned text, headline derived from the command, time-ago stamp.
- `map` replies: detect `LXMF.FIELD_IMAGE` in the message fields via core's message representation; decode JPEG; show inline, tap to zoom (simple fullscreen viewer). Decode failure → friendly card, never a crash.
- Node picker bottom sheet for "Map — one node": populated from the most recent `nodes` reply (parse the known list format), cached in farmui-local settings; empty cache → card prompting "Tap 🛰 List nodes first" (and auto-offer to send it).
- Gateway pinning: stream row action stores gateway hash in farmui settings (JSON in app dir, NOT in core/RNS config); conversation header shows pinned gateway name/hash; un-pinned state shows a friendly "Pick your farm gateway" empty state linking to the stream tab.
- Delivery states per outgoing command: sending/delivered/failed chips driven by core's message state fields; failed → plain-language card with a big "Try again" button.
- `tests/test_e2e_conversation.py` (headless, against rig from phase 2): drives `dispatch.py` functions directly (same code path as buttons) for all 9 commands; asserts reply parsing incl. image bytes for map; asserts the rig-logged raw incoming content string equals exactly the wire string (e.g. `"soil"`, `"map !abc123"`); failure-path test: stop rig gateway, assert failed state surfaces.

## Acceptance criteria (all must pass — verify each in transcript)

- Desktop demo vs rig: every button produces its reply card; map shows image; screenshots captured (cards, map open, failure card)
- e2e pytest green x3 covering all 9 commands headlessly
- Wire-content assertion: rig-side raw LXMF content equals the exact command strings stock Sideband would send when typed
- No typing anywhere; node picker handles empty/missing nodes cache gracefully (test + screenshot)
- Failed-delivery path shows plain-language retry card (test asserts state; screenshot)
- Integrity guard green

## Mandatory commands (run each, surface last ~10 lines + exit code)

- `.venv/bin/python -m pytest tests/ -q` (x3)
- `bash scripts/check_upstream_integrity.sh`

## Evidence required in transcript

- Wire-content assertion output
- Screenshot file list (reply cards, map image, node picker, failure state)
- pytest x3

## Notes

Resist adding gateway-side features — the gateway contract is frozen at the 9 commands. Any "it would be nice if the bridge also…" idea goes to docs/FUTURE.md, untouched code.
