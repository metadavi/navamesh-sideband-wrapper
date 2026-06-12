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
