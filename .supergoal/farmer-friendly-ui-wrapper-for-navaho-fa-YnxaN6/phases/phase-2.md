SUPERGOAL_PHASE_START
Phase: 2 of 8 — Protocol rig & stub gateway
Task: Build a loopback RNS testnet plus a stub Navamesh gateway replicating reticulum_bridge.py's exact LXMF command contract, and prove all 9 command round-trips with pytest.
Type: brownfield-integration, testing
Mandatory commands: .venv/bin/python -m pytest tests/ -q (x3), bash scripts/check_upstream_integrity.sh
Acceptance criteria: 6
Evidence required: pytest output x3, one full command/response transcript
Depends on phases: 1

## Why

A real LXMF round-trip harness on loopback proves the protocol seam before any UI exists and becomes the regression net every later phase runs against.

## Work

- `tests/rig/rns_testnet.py`: helper that creates two isolated RNS instances with distinct configdirs under a tmpdir, joined via loopback `TCPServerInterface`/`TCPClientInterface` on an ephemeral port. Each side gets its own identity and LXMF router. Provide clean startup/teardown (RNS is process-global — run each instance in a subprocess; this is the known-correct pattern for multi-instance RNS tests).
- `tests/rig/stub_gateway.py`: standalone LXMF gateway process mirroring the command contract of `~/Desktop/Navamesh-main/src/navamesh/reticulum_bridge.py` (READ it for the contract; do not import or modify it): commands status, soil, battery, position, link, map, map <id>, nodes, help, case-insensitive, content-or-title; replies formatted like the real `fmt_*` outputs; `map` replies attach a small generated JPEG via `LXMF.FIELD_IMAGE` (+ `FIELD_FILE_ATTACHMENTS` when available) exactly like the real bridge; unknown command → help text. Node data from a JSON fixture (3 nodes: one dry, one ok, one wet; one without GPS).
- Document the contract in `tests/rig/CONTRACT.md` as a table with reticulum_bridge.py line references.
- `tests/test_protocol_roundtrip.py`: client side uses ONLY pip `rns`+`lxmf`: announce, resolve gateway destination, send each of the 9 commands, assert reply (text shape per command; image field present for map; node list for nodes; help for help and for garbage input).
- Make timing robust: generous-but-bounded waits on announce propagation and delivery callbacks; no sleeps-and-pray; suite must pass 3x consecutively.

## Acceptance criteria (all must pass — verify each in transcript)

- All 9 commands round-trip with asserted replies (text contracts + image field for map)
- Client announce received by gateway rig and vice versa, public RNS/LXMF APIs only
- Rig layer imports only `rns`/`lxmf` pip packages (no Sideband imports) — show grep proof
- CONTRACT.md table cross-references reticulum_bridge.py line numbers
- 3 consecutive full-suite passes
- Integrity guard green

## Mandatory commands (run each, surface last ~10 lines + exit code)

- `.venv/bin/python -m pytest tests/ -q` (run three times, show each)
- `bash scripts/check_upstream_integrity.sh`

## Evidence required in transcript

- pytest output x3
- One full printed command/response transcript (e.g. `soil` request and the formatted reply text)
- grep proof of no-Sideband-imports in tests/rig

## Notes

This stub gateway is test infrastructure, not a replacement for the real bridge — keep its formatting faithful so later UI snapshot expectations match real-gateway output. Never modify Navamesh-main.
