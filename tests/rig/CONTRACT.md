# Stub Gateway Command Contract

Cross-reference to `~/Desktop/Navamesh-main/src/navamesh/reticulum_bridge.py`

| Command | Input (content or title) | Response shape | Image field | bridge.py lines |
|---------|--------------------------|----------------|-------------|-----------------|
| `status` | `"status"` (case-insensitive) | Header "🌱 Navamesh Status" + per-node block (Last seen, Soil %, Battery, RSSI/SNR, Position) | None | 281–303 |
| `soil` | `"soil"` | Header "🌱 Soil Moisture" + per-node `Node XXXX: NN.N%  (timestamp)` | None | 305–315 |
| `battery` | `"battery"` | Header "🔋 Battery" + per-node level/voltage/uptime | None | 317–327 |
| `position` | `"position"` | Header "📍 Position" + per-node lat/lon | None | 329–338 |
| `link` | `"link"` | Header "📡 Link Quality" + per-node RSSI/SNR | None | 340–348 |
| `map` | `"map"` | "🗺️ Map: N node(s) plotted" | JPEG via `FIELD_IMAGE` (`["jpg", bytes]`) | 558–602 |
| `map <id>` | `"map !drynode001"` etc. | Same as map but for single node | JPEG via `FIELD_IMAGE` | 562–565 |
| `nodes` | `"nodes"` | "Known field nodes:\n  !node1\n  !node2..." | None | 548–550 |
| `help` | `"help"` | `HELP_TEXT` constant (lists all commands) | None | 351–360, 551 |
| unknown | any unrecognized string | `"Unknown command: '...'\n\n{HELP_TEXT}"` | None | 604 |

## Control commands (write)

These change deployed field hardware, unlike everything above. The wrapper requires a
value-then-confirm dialog before dispatching one.

The gateway currently accepts control commands from **any** sender that can reach it:
`AUTHORIZED_FARMER_HASHES` is empty for testing and first deployment. Setting it restricts
access with no code change (see the Pi repo's `TODO.md`). The `unauthorized` row below
therefore only applies once that variable is populated.

| Command | Input | Response shape | Notes |
|---------|-------|----------------|-------|
| `ble` | `ble <!id\|^all> <minutes>` | `"📤 Queued: Bluetooth window for N min → …"` then a later ack | 1–240 minutes |
| `interval` | `interval <!id\|^all> <seconds>` | `"📤 Queued: telemetry interval N s → …"` then a later ack | 300–86400 seconds |
| `quiet` | `quiet <!id\|^all> on\|off` | `"📤 Queued: quiet mode ON/OFF → …"` then a later ack | auto-resumes within 3 days |
| `setloc` | `setloc <!id> <lat> <lon>` | `"📤 Queued: fixed position LAT, LON → …"` then a later ack | decimal degrees, 7 dp; **no `^all`** |
| unauthorized | any of the above | `"Unauthorized: this gateway does not accept control commands from you."` | nothing is transmitted |
| bad value | e.g. `ble !x 999` | `"⚠️  …must be …"` | rejected before transmit |
| unknown node | e.g. `ble !nope 15` | `"Node '!nope' not found. …"` | rejected before transmit |
| broadcast setloc | `setloc ^all 36.07 -109.04` | `"⚠️  'setloc' must name one node…"` | rejected before transmit |

`setloc` is the only control command the wrapper builds from a value that is neither a
preset nor on/off: the field nodes have no GPS, so the position comes from the phone's own
fix (or, with no fix, from coordinates typed into the confirm dialog). Its ack is also the
only one that reports a pair — the node echoes back the coordinates it actually stored, so
the outcome line reads `"✅ <node> applied setloc = 36.072123, -109.045099"`.

### Asynchronous outcome

Unlike the read verbs, that reply is **not** the final answer — it only confirms the
command was queued. The node's acknowledgement travels back over LoRa (PortNum 259) and
arrives as a **second, later LXMF message**:

- `"✅ <node> applied <verb> = <value>"` — confirmed, reporting what the node actually
  applied after its own clamping.
- `"⏱ <node> did not acknowledge <verb> within Ns…"` — no ack in time. Sensor nodes do not
  rebroadcast for each other, so a node outside direct gateway range is only reachable
  via `^all`.
- `"❌ <node> rejected <verb>…"` / `"⚠️ <verb> → <node> failed: …"`

The wrapper needs no new code for these: `app._poll_gateway_replies` already renders any
new inbound message from the pinned gateway, and `add_result` appends rather than replaces.

An **unsolicited** ack also exists: when a node's quiet mode self-expires it reports
`command_id = 0`, and the bridge logs that the node resumed on its own.

## Message routing

- Command is read from `message.content` (UTF-8); falls back to `message.title` (same as bridge line 645–646).
- Reply is sent via `LXMessage.OPPORTUNISTIC` in the stub (bridge uses `DIRECT` with `OPPORTUNISTIC` fallback, lines 719–728, 706–717).
- Gateway address: registered via `LXMRouter.register_delivery_identity()` (bridge line 633).

## Fixture nodes

| Node ID | Soil % | Battery | GPS | Label |
|---------|--------|---------|-----|-------|
| `!drynode001` | 20.0 (dry) | 45% / 3.65V | Yes | dry |
| `!oknode0002` | 55.0 (ok) | 78% / 3.85V | Yes | ok |
| `!wetnode003` | 75.0 (wet) | USB | Yes | wet |
| `!nogpsnode4` | 40.0 | 60% / 3.75V | None | no GPS |
