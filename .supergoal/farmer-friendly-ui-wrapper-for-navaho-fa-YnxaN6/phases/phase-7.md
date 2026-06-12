SUPERGOAL_PHASE_START
Phase: 7 of 8 — Behavior-preservation proof
Task: Turn "Reticulum/Sideband behavior unchanged" from a claim into a documented, re-runnable proof: guarantee→evidence matrix, stock-equivalence test, and a real-hardware field test plan.
Type: testing, docs
Mandatory commands: .venv/bin/python -m pytest tests/ -q (x3), bash scripts/check_upstream_integrity.sh
Acceptance criteria: 4
Evidence required: equivalence assertion output, TESTING.md matrix rendered in transcript
Depends on phases: 2, 4, 5

## Why

The user's hardest constraint is exact preservation of current communication functionality — this phase makes that verifiable by anyone, any time, without trusting this run's self-reports.

## Work

- `tests/test_stock_equivalence.py`: send the same command twice against the rig — (a) via a minimal raw client using only pip rns+lxmf constructing the LXMessage the way stock Sideband does for a typed message, (b) via `farmui.dispatch`. Capture both at the rig and assert equality of: content bytes, title handling, absence of extra fields, destination addressing. Representative commands: `soil`, `map !<id>`, `help`.
- `docs/TESTING.md` — guarantee→evidence matrix. Rows at minimum:
  | Guarantee | Evidence |
  - RNS routing/transport/crypto unchanged → unmodified pip `rns` at pinned version (UPSTREAM.lock + pip check in integrity script)
  - LXMF message/propagation behavior unchanged → unmodified pip `lxmf` (same)
  - Sideband core (identities, announces, conversations, delivery methods) unchanged → protected-path tree hashes (integrity script) incl. `sbapp/sideband/`, `sbapp/services/`
  - Announce behavior observable-identical → rig announce tests (phase 2) + field plan step
  - Command wire format identical to typed Sideband → stock-equivalence test
  - Gateway compatibility (real `reticulum_bridge.py`) → field test plan
  - Stock Sideband still interoperates with the same gateway in parallel → field plan step
  Every row names a concrete script/test/step — no empty or "by design" rows.
- `docs/FIELD_TEST_PLAN.md`: numbered, user-executable with the real Pi: power on gateway, confirm farm app announce appears in a stock Sideband instance elsewhere on the mesh; pin gateway from stream; run all 9 commands and compare outputs against typing the same commands from stock Sideband; confirm stock Sideband keeps working in parallel; expected outputs included.
- Wire integrity script into a single `scripts/verify_all.sh` (guard + pins + full pytest) as the one-command proof.

## Acceptance criteria (all must pass — verify each in transcript)

- Equivalence test green: farmui-path LXMF content == stock-path content for soil, map <id>, help
- TESTING.md matrix rendered in transcript with zero empty/hand-wavy evidence cells
- `bash scripts/verify_all.sh` exits 0; full suite green x3
- FIELD_TEST_PLAN.md: every numbered step has an `Expected:` line (mechanical check shown: count of steps == count of Expected lines, both printed)

## Mandatory commands (run each, surface last ~10 lines + exit code)

- `.venv/bin/python -m pytest tests/ -q` (x3)
- `bash scripts/verify_all.sh`
- `bash scripts/check_upstream_integrity.sh`

## Evidence required in transcript

- Equivalence assertion output
- TESTING.md matrix
- verify_all.sh output

## Notes

If stock Sideband adds fields to typed messages (e.g. telemetry when enabled), the equivalence baseline is Sideband with default farm-relevant settings; document any conditional fields in TESTING.md rather than hiding them.
