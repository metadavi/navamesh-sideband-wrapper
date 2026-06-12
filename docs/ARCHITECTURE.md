# Architecture: Navamesh Farm App

## Existing pipeline

```
RAK Soil Sensor (LoRa) ──► RAK Gateway
                                 │
                            Pi (Raspberry Pi)
                            ├── MQTT broker (paho-mqtt)
                            ├── mqtt_to_db.py  ──► InfluxDB / Postgres
                            ├── reticulum_bridge.py  ──► LXMF gateway (RNS)
                            └── HT-HD01 (HaLow radio) ──► Wi-Fi bridge
                                                              │
                                                         Farmer's phone
                                                         (Sideband / Farm App)
```

Key source files (read-only reference at `~/Desktop/Navamesh-main`):
- `src/navamesh/reticulum_bridge.py` — LXMF command/response gateway; listens for commands, queries Postgres, replies with text or JPEG map image via `LXMF.FIELD_IMAGE`.
- `src/navamesh/mqtt_client.py` — ingest from MQTT broker into Postgres
- `src/navamesh/generate_map.py` — renders PNG/JPEG map tiles for the `map` command
- `src/navamesh/processors/` — telemetry processors (soil, position, link)
- `rns_config.example` — reference RNS config with UDPInterface for HaLow (HT-HD01), TCPServerInterface on port 4243, and UDP broadcast on 4242

Commands served by `reticulum_bridge.py` (lines 1-50):
  `status`, `soil`, `battery`, `position`, `link`, `map`, `map <id>`, `nodes`, `help`

## Where the Farm App sits

```
Navamesh Farm App (this repo)
└── sbapp/farmui/          ← NEW: all farmer UI code
    ├── app.py             ← FarmApp: thin shell over SidebandCore
    ├── theme.py           ← design tokens (big buttons, contrast)
    └── screens/           ← Announce / Stream / Conversation
sbapp/main.py              ← 3-line shim → farmui (modified; upstream copy at main_upstream.py)
sbapp/sideband/            ← PROTECTED: SidebandCore unchanged
sbapp/services/            ← PROTECTED: Android service unchanged
```

The Farm App is a **minimal UI layer** over the standard Sideband/Reticulum stack.  
No protocol logic is added or changed. All messaging goes through `SidebandCore.send_message()` and `SidebandCore.get_messages()` — the same calls the stock Sideband UI makes.

## HT-HD01 HaLow path

The phone reaches the Pi through:
1. Phone Wi-Fi → HT-HD01 (HaLow radio, IP bridge mode) → Pi's `eth0`
2. RNS `UDPInterface` on both ends (see `deploy/rns_udp_hthd01.conf.example`)
3. No new network code — configuration only, written by the farmui settings screen into the RNS config's `[interfaces]` section.
