# Behavior-Preservation Guarantee Matrix

This document maps every "unchanged" guarantee for the Navamesh Farm App to its
automated and/or manual evidence.  Each row has a non-empty evidence column; no
hand-wavy rows.

---

## Guarantees & Evidence

| # | Protected behavior | Guarantee | Automated evidence | Manual / structural evidence |
|---|---|---|---|---|
| 1 | **Reticulum (RNS) code unchanged** | `rns` pip package is pinned at 1.3.5 and never imported for modification | `scripts/check_upstream_integrity.sh` verifies `rns==1.3.5` pin in `requirements-dev.txt`; `pip show rns` confirms installed version | `rns` is a read-only pip dependency; no file under `.venv/lib/python*/site-packages/RNS/` is in the repo |
| 2 | **LXMF code unchanged** | `lxmf` pip package is pinned at 1.0.1 and never modified | `scripts/check_upstream_integrity.sh` verifies `lxmf==1.0.1` pin; `pip show lxmf` confirms | `lxmf` is a read-only pip dependency |
| 3 | **SidebandCore byte-identical** | `sbapp/sideband/` tree hash matches upstream-pin | `scripts/check_upstream_integrity.sh` — tree hash guard on `sbapp/sideband/`; exits 1 on any drift | Protected path listed in `UPSTREAM.lock`; git history shows zero commits to this path after initial vendor |
| 4 | **Android foreground service byte-identical** | `sbapp/services/sidebandservice.py` hash matches upstream-pin | `scripts/check_upstream_integrity.sh` — SHA-256 check on `sbapp/services/` | `UPSTREAM.lock` records tree hash; service is the standard Sideband service, not modified |
| 5 | **Vendored libraries unchanged** | `sbapp/kivymd/`, `sbapp/mapview/`, `sbapp/plyer/`, `sbapp/pmqtt/`, `sbapp/md/`, `sbapp/share/`, `libs/`, `recipes/` byte-identical | `scripts/check_upstream_integrity.sh` — tree hashes for all protected paths | `UPSTREAM.lock` records individual tree hashes; no commits to these paths |
| 6 | **LXMF message content = typed command** | `farmui` sends exactly the same bytes a user would type in stock Sideband | `tests/test_stock_equivalence.py` — `test_farmui_wire_equals_stock` sends via raw LXMessage and via farmui dispatcher; asserts gateway wirelog has ≥2 identical entries for each command | `farmui/dispatch.py:122` — `content=wire` where `wire = get_wire(cmd_key)` is the plain command string |
| 7 | **All 9 commands round-trip correctly** | Every command produces the expected gateway reply shape | `tests/test_protocol_roundtrip.py` — 9 commands × 3 consecutive runs | `tests/rig/CONTRACT.md` — cross-references each command to `reticulum_bridge.py` line numbers |
| 8 | **farmui-path replies identical to stock-path replies** | Same command via both paths receives the same gateway text | `tests/test_e2e_conversation.py` — all 9 commands via `LxmfDirectDispatcher` against the rig; reply content asserted | `tests/test_stock_equivalence.py` — stock reply and farmui reply both asserted against the same gateway |
| 9 | **LXMF OPPORTUNISTIC delivery method preserved** | farmui uses `LXMF.LXMessage.OPPORTUNISTIC` — identical to stock Sideband | `tests/test_e2e_conversation.py` green (OPPORTUNISTIC is the only method that works on the loopback rig without a Destination announce delay) | `farmui/dispatch.py:145` — `desired_method=LXMF.LXMessage.OPPORTUNISTIC` |
| 10 | **Announce behavior unchanged** | farmui calls `source.announce()` via the standard LXMF identity announce — no custom announce logic | `tests/test_protocol_roundtrip.py` — client announce is received by the gateway rig | `farmui/dispatch.py` never calls RNS directly for announces; Sideband's `SidebandCore` handles announces in production |
| 11 | **Identity / crypto unchanged** | RNS identity creation and key derivation unchanged | `tests/test_e2e_conversation.py` — identities created with `RNS.Identity()` (standard API); messages encrypted and delivered correctly | Cryptography entirely inside `rns` pip package (pinned 1.3.5, verified by integrity guard) |
| 12 | **UDP interface is config-only** | HT-HD01 UDPInterface is added by writing the RNS config template only; no interface code in protected paths | `tests/test_udp_interface.py` — full command round-trip over loopback UDPInterface using unmodified RNS | `git diff main_upstream_pin -- sbapp/sideband/` shows zero lines changed; UDP config written to user-editable `[interfaces]` block |
| 13 | **No new network surface** | farmui adds zero new TCP/UDP listeners; all network access is through RNS | Test suite runs without opening any port except the testnet loopback | `farmui/` has no `socket`, `http`, or `asyncio.create_server` calls — verified by `grep -r "socket\|http.server\|create_server" sbapp/farmui/` |
| 14 | **`sbapp/main.py` shim only** | `main.py` is ≤5 lines pointing to `farmui`; upstream version preserved at `main_upstream.py` | `scripts/check_upstream_integrity.sh` verifies `sbapp/main_upstream.py` SHA-256 | `git diff main_upstream_pin -- sbapp/main.py` shows exactly the shim replacement |

---

## Running the full evidence suite

```bash
# Integrity guard (rows 1-5, 12, 14)
bash scripts/check_upstream_integrity.sh

# Full test suite (rows 6-13)
.venv/bin/pytest tests/ -q

# Wire-content equivalence (row 6 in isolation)
.venv/bin/pytest tests/test_stock_equivalence.py -v

# Protocol round-trip (row 7)
.venv/bin/pytest tests/test_protocol_roundtrip.py -v

# e2e conversation (rows 8-9)
.venv/bin/pytest tests/test_e2e_conversation.py -v

# UDP interface (row 12)
.venv/bin/pytest tests/test_udp_interface.py -v
```

All commands above must exit 0.  The integrity guard must print `RESULT: PASS`.

---

## What is NOT in scope for automated testing

| Item | Reason | Evidence type |
|---|---|---|
| Actual Pi gateway reachability | Requires real HT-HD01 hardware + Pi | Field test plan (`docs/FIELD_TEST_PLAN.md`) |
| Android service lifecycle on real device | Requires sideloaded APK | `docs/DEVICE_SMOKE.md` checklist |
| HaLow radio RF link | Hardware-dependent | Field test plan |
| Over-the-air announce propagation beyond the testnet | Hardware-dependent | Field test plan |
