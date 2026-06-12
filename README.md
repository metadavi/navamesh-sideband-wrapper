# Navamesh Farm App

A farmer-friendly Android UI built as a minimal Sideband fork for the Navamesh precision-agriculture network.

## What it does

- **Announce**: broadcast your farm identity over Reticulum
- **Stream**: see nearby gateways; tap to set the Navamesh gateway as your farm hub
- **Conversation**: tap big labeled buttons — Soil, Battery, Position, Link, Map, Nodes, Status — and get plain-English reply cards

All radio communication goes through Reticulum/LXMF exactly as stock Sideband does. The only thing this fork changes is the UI entry point.

## Upstream

Sideband 1.9.7 (markqvist/Sideband@89a0c70). Protected paths are byte-identical to upstream; the integrity guard (`scripts/check_upstream_integrity.sh`) enforces this on every build.

## Dev setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
bash scripts/check_upstream_integrity.sh   # must pass before any work
.venv/bin/python -m pytest tests/ -q
```

## Constraint statement

- `rns` and `lxmf` pip packages are unmodified pinned deps — never altered
- Sideband protected paths are byte-identical to upstream tag 1.9.7
- `~/Desktop/Navamesh-main` is read-only reference — never modified by this project

See `docs/ARCHITECTURE.md` and `docs/DECISION.md` for design rationale.
See `NOTICE` for license and attribution.
