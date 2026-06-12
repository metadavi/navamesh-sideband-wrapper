SUPERGOAL_PHASE_START
Phase: 5 of 8 — HT-HD01 UDP connectivity
Task: Wire the phone↔HT-HD01 path as a configuration-only RNS UDPInterface — settings UI writing the RNS config template's [interfaces] section, deploy snippets, connectivity status chip — proven by a UDP-variant rig test.
Type: integration, config
Mandatory commands: .venv/bin/python -m pytest tests/ -q (x3), bash scripts/check_upstream_integrity.sh
Acceptance criteria: 5
Evidence required: UDP round-trip pytest output, generated config contents, StatusChip up/down screenshots
Depends on phases: 1, 2

## Why

The farmer's phone reaches the Pi through Wi-Fi → HT-HD01 (HaLow), and per the hard constraints this must be pure configuration — RNS instantiates UDPInterface natively from its config file; Sideband's generated RNS config template explicitly reserves an [interfaces] section for custom interfaces.

## Work

- `deploy/rns_udp_hthd01.conf.example`: documented `[interfaces]` snippet — `type = UDPInterface`, listen/forward IP+port for the HT-HD01 (placeholders + comments explaining HaLow topology: phone Wi-Fi → HT-HD01 ↔ HaLow ↔ Pi's HT-HD01 → Pi RNS, mirroring the Pi-side `HTHD01_UDP` interface naming).
- farmui Settings screen (small, tucked behind a gear icon — farmers shouldn't need it after setup): HT-HD01 IP + port fields with validation; writing saves ONLY into the RNS config template's `[interfaces]` section through Sideband's existing user-editable template mechanism (find how core stores/regenerates the template — config file content manipulation only; if the template lives as a string in farmui-owned config dir, edit the file on disk; NEVER patch core code).
- Config writer must be surgical: parse existing config, replace/insert only the named `[[Navamesh HT-HD01]]`-style interface block, leave every other line byte-identical (test asserts).
- `StatusChip` wiring on all three screens: interface up/down (from RNS public state via core where exposed; otherwise last-announce-heard age as the proxy) + plain language ("Radio connected" / "Radio not responding — check the white box").
- `tests/test_udp_interface.py`: rig variant — two RNS instances joined via loopback `UDPInterface` (distinct ports on 127.0.0.1) instead of TCP; rerun the full 9-command round-trip; plus config-writer surgical-edit test; plus a boot test: RNS instance starts cleanly with the generated config (exit/log evidence).

## Acceptance criteria (all must pass — verify each in transcript)

- UDP-variant rig test green x3 (unmodified RNS UDPInterface config shape works)
- Settings write produces a valid RNS config (RNS boots with it — transcript proof) and a byte-level diff shows only the [interfaces] block changed
- StatusChip reflects up/down when the UDP peer stops (simulated; screenshots)
- git diff shows changes only under farmui/, deploy/, tests/, docs/
- Integrity guard green

## Mandatory commands (run each, surface last ~10 lines + exit code)

- `.venv/bin/python -m pytest tests/ -q` (x3)
- `bash scripts/check_upstream_integrity.sh`

## Evidence required in transcript

- UDP round-trip pytest output
- Generated config file contents + surgical-diff proof
- StatusChip screenshots (up and down)

## Notes

If Sideband's Android flow regenerates the RNS config template from `rns_config` in core.py at startup, verify whether user edits to the template persist (the template comment says custom [interfaces] entries are supported — confirm the persistence path by reading core, and document exactly how in deploy/). If persistence requires the farmer to use Sideband's "RNS config template" editor path, replicate that exact mechanism from farmui settings — still file-content-only.
