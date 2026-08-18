#!/usr/bin/env python3
"""
stub_gateway.py — Navamesh stub LXMF gateway for tests.

Replicates the command contract of reticulum_bridge.py (read-only reference
at ~/Desktop/Navamesh-main/src/navamesh/reticulum_bridge.py) using fixture
node data instead of Postgres.

Command contract (reticulum_bridge.py lines 8-17):
  status   -> fmt_status()          lines 281-303
  soil     -> fmt_soil()            lines 305-315
  battery  -> fmt_battery()         lines 317-327
  position -> fmt_position()        lines 329-338
  link     -> fmt_link()            lines 340-348
  map      -> JPEG via FIELD_IMAGE  lines 558-602
  map <id> -> JPEG for one node     lines 562-565
  nodes    -> node ID list          lines 548-550
  help     -> HELP_TEXT             line  551
  unknown  -> "Unknown command" + help  line 604

Run as: python stub_gateway.py --configdir DIR --storagedir DIR --port PORT --hashfile FILE
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import threading
import time
from typing import Optional

import RNS
import LXMF

sys.path.insert(0, os.path.dirname(__file__))
from fixture_nodes import FIXTURE_NODES, NodeSnapshot


# ── Formatters (mirroring reticulum_bridge.py) ─────────────────────────────

def _fmt_node(node_id: str) -> str:
    return f"Node {node_id[-4:]}" if node_id.startswith("!") else node_id

def _fmt_ts(ts: Optional[int]) -> str:
    if ts is None:
        return "never"
    try:
        import datetime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

def _fmt_uptime(seconds: Optional[int]) -> str:
    if seconds is None:
        return "N/A"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h: return f"{h}h {m}m"
    if m: return f"{m}m {s}s"
    return f"{s}s"

def _header(title: str) -> str:
    return f"{'─'*30}\n{title}\n{'─'*30}\n"

def fmt_status(nodes: dict) -> str:
    if not nodes:
        return "No node data in database yet. Are field nodes transmitting?"
    lines = [_header("🌱 Navamesh Status")]
    for node_id, snap in sorted(nodes.items()):
        lines.append(f"[ {_fmt_node(node_id)} ]  {node_id}")
        lines.append(f"  Last seen:  {_fmt_ts(snap.ts)}")
        if snap.soil_percent is not None:
            lines.append(f"  Soil:       {snap.soil_percent:.1f}%")
        elif snap.soil_raw is not None:
            lines.append(f"  Soil ADC:   {snap.soil_raw}")
        if snap.battery_usb:
            lines.append(f"  Battery:    USB (charging)")
        elif snap.battery_level is not None:
            lines.append(f"  Battery:    {snap.battery_level:.0f}%")
        if snap.voltage is not None:
            lines.append(f"  Voltage:    {snap.voltage:.2f}V")
        if snap.rx_rssi is not None:
            lines.append(f"  RSSI/SNR:   {snap.rx_rssi} dBm / {snap.rx_snr} dB")
        if snap.lat is not None:
            lines.append(f"  Position:   {snap.lat:.6f}, {snap.lon:.6f}")
        lines.append("")
    return "\n".join(lines)

def fmt_soil(nodes: dict) -> str:
    if not nodes: return "No soil data in database yet."
    lines = [_header("🌱 Soil Moisture")]
    for node_id, snap in sorted(nodes.items()):
        if snap.soil_percent is not None:
            lines.append(f"{_fmt_node(node_id)}: {snap.soil_percent:.1f}%  ({_fmt_ts(snap.ts)})")
        elif snap.soil_raw is not None:
            lines.append(f"{_fmt_node(node_id)}: ADC={snap.soil_raw}  ({_fmt_ts(snap.ts)})")
        else:
            lines.append(f"{_fmt_node(node_id)}: no soil data yet")
    return "\n".join(lines)

def fmt_battery(nodes: dict) -> str:
    if not nodes: return "No battery data in database yet."
    lines = [_header("🔋 Battery")]
    for node_id, snap in sorted(nodes.items()):
        bat = "USB (charging)" if snap.battery_usb else (
            f"{snap.battery_level:.0f}%" if snap.battery_level is not None else "no data"
        )
        volt = f"  {snap.voltage:.2f}V" if snap.voltage is not None else ""
        up   = f"  up {_fmt_uptime(snap.uptime_seconds)}" if snap.uptime_seconds else ""
        lines.append(f"{_fmt_node(node_id)}: {bat}{volt}{up}  ({_fmt_ts(snap.ts)})")
    return "\n".join(lines)

def fmt_position(nodes: dict) -> str:
    if not nodes: return "No position data in database yet."
    lines = [_header("📍 Position")]
    for node_id, snap in sorted(nodes.items()):
        if snap.lat is not None:
            alt = f"  alt={snap.alt}m" if snap.alt is not None else ""
            lines.append(f"{_fmt_node(node_id)}: {snap.lat:.6f}, {snap.lon:.6f}{alt}  ({_fmt_ts(snap.ts)})")
        else:
            lines.append(f"{_fmt_node(node_id)}: no GPS fix yet")
    return "\n".join(lines)

def fmt_link(nodes: dict) -> str:
    if not nodes: return "No link data in database yet."
    lines = [_header("📡 Link Quality")]
    for node_id, snap in sorted(nodes.items()):
        if snap.rx_rssi is not None:
            lines.append(f"{_fmt_node(node_id)}: RSSI={snap.rx_rssi} dBm  SNR={snap.rx_snr} dB  ({_fmt_ts(snap.ts)})")
        else:
            lines.append(f"{_fmt_node(node_id)}: no link data yet")
    return "\n".join(lines)

HELP_TEXT = """🌱 Navamesh Gateway — Commands

  status       — full summary of all nodes
  soil         — soil moisture readings
  battery      — battery levels & uptime
  position     — GPS coordinates
  link         — RSSI/SNR link quality
  map          — rendered map image (all nodes)
  map <id>     — rendered map image (one node)
  nodes        — list all known node IDs
  help         — this message

Control commands (change the field nodes):
  ble <id|^all> <min>      — open a Bluetooth window, then auto-close
  interval <id|^all> <sec> — set telemetry interval (live, no reboot)
  quiet <id|^all> on|off   — stop / resume transmitting"""

# The stub treats every sender as authorized and never touches a radio. The real
# gateway's allow-list and bounds checks are covered by the Pi repo's
# tests/test_handle_write_command.py; duplicating them here would only test the stub.
STUB_CMD_ID = 12345


def _make_stub_jpeg() -> bytes:
    """Generate a tiny solid-green JPEG (no staticmap needed) for map tests."""
    try:
        from PIL import Image
        img = Image.new("RGB", (64, 64), color=(34, 204, 68))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=50)
        return buf.getvalue()
    except ImportError:
        # Minimal valid 1x1 red JPEG (hardcoded bytes)
        return bytes.fromhex(
            "ffd8ffe000104a46494600010100000100010000"
            "ffdb004300080606070605080707070909080a0c"
            "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20"
            "242e2720222c231c1c2837292c3031343434"
            "1f27393938323832323236ffffffc000110800"
            "01000103012200021101031101ffc400"
            "1f0000010501010101010000000000000000"
            "0102030405060708090a0bffda000c0301"
            "0002110311003f00fae0ffd9"
        )


def handle_command(cmd: str, nodes: dict):
    parts   = cmd.strip().lower().split(None, 1)
    command = parts[0] if parts else ""
    target  = parts[1].strip() if len(parts) > 1 else None

    if command == "nodes":
        if not nodes: return "No nodes in database yet.", None
        return "Known field nodes:\n" + "\n".join(f"  {n}" for n in sorted(nodes)), None
    if command == "help":     return HELP_TEXT, None
    if command == "status":   return fmt_status(nodes), None
    if command == "soil":     return fmt_soil(nodes), None
    if command == "battery":  return fmt_battery(nodes), None
    if command == "position": return fmt_position(nodes), None
    if command == "link":     return fmt_link(nodes), None

    if command in ("ble", "interval", "quiet"):
        bits = (target or "").split()
        node = bits[0] if bits else None
        arg  = bits[1] if len(bits) > 1 else None
        if not node or arg is None:
            return f"⚠️  '{command}' needs a target and a value.", None
        if node not in ("^all", "all") and node not in nodes:
            return f"Node '{node}' not found. Send 'nodes' to list all known nodes.", None
        who = "ALL field nodes" if node in ("^all", "all") else node
        if command == "quiet":
            if arg not in ("on", "off"):
                return "quiet needs 'on' or 'off'. Example: quiet ^all on", None
            what = f"quiet mode {arg.upper()}"
        elif command == "ble":
            what = f"Bluetooth window for {arg} min"
        else:
            what = f"telemetry interval {arg} s"
        return (f"📤 Queued: {what} → {who}\n"
                f"Command {STUB_CMD_ID}. Waiting for the node to acknowledge…"), None

    if command == "map":
        if target:
            if target not in nodes:
                return f"Node '{target}' not found. Send 'nodes' to list all known nodes.", None
            map_nodes = {target: nodes[target]}
        else:
            map_nodes = nodes
        geo_count = sum(1 for s in map_nodes.values() if s.lat is not None)
        no_gps    = len(map_nodes) - geo_count
        img_bytes = _make_stub_jpeg()
        lines = [f"🗺️ Map: {geo_count} node(s) plotted"]
        if no_gps:
            lines.append(f"⚠️ {no_gps} node(s) missing GPS")
        return "\n".join(lines), ("jpg", img_bytes, "image/jpeg")

    return f"Unknown command: '{command}'\n\n{HELP_TEXT}", None


class StubGateway:
    DISPLAY_NAME = "Navamesh Gateway"

    def __init__(self, storagedir: str, wirelog: str | None = None):
        self._storagedir = storagedir
        self._wirelog = wirelog
        self._router = None
        self._source = None
        self._lock = threading.Lock()
        self._nodes = dict(FIXTURE_NODES)

    def start(self) -> str:
        os.makedirs(self._storagedir, exist_ok=True)
        id_path = os.path.join(self._storagedir, "identity")
        if os.path.exists(id_path):
            identity = RNS.Identity.from_file(id_path)
        else:
            identity = RNS.Identity()
            identity.to_file(id_path)

        self._router = LXMF.LXMRouter(storagepath=self._storagedir, autopeer=False)
        self._source = self._router.register_delivery_identity(
            identity, display_name=self.DISPLAY_NAME
        )
        self._router.register_delivery_callback(self._on_message)
        return RNS.hexrep(self._source.hash, delimit=False)

    def announce(self):
        if self._source:
            self._source.announce()

    def _on_message(self, message):
        try:
            content = message.content.decode("utf-8").strip() if message.content else ""
            title   = message.title.decode("utf-8").strip()   if message.title   else ""
            cmd     = content or title
            if self._wirelog:
                with open(self._wirelog, "a") as wf:
                    wf.write(cmd + "\n")
            text_reply, image_result = handle_command(cmd, self._nodes)
            with self._lock:
                self._send_reply(message, text_reply, image_result)
        except Exception as exc:
            sys.stderr.write(f"[stub_gateway] handler error: {exc}\n")

    def _send_reply(self, original, text, image_result):
        identity = RNS.Identity.recall(original.source_hash)
        if identity is None:
            RNS.Transport.request_path(original.source_hash)
            deadline = time.time() + 10
            while time.time() < deadline:
                identity = RNS.Identity.recall(original.source_hash)
                if identity:
                    break
                time.sleep(0.1)
        if identity is None:
            sys.stderr.write("[stub_gateway] Could not resolve client identity\n")
            return
        dest = RNS.Destination(
            identity,
            RNS.Destination.OUT, RNS.Destination.SINGLE,
            "lxmf", "delivery",
        )
        fields = None
        if image_result:
            img_type, img_bytes, mime = image_result
            fields = {LXMF.FIELD_IMAGE: [img_type, img_bytes]}
            try:
                fields[LXMF.FIELD_FILE_ATTACHMENTS] = [[f"navamesh_map.{img_type}", img_bytes, mime]]
            except AttributeError:
                pass
        msg = LXMF.LXMessage(
            destination=dest,
            source=self._source,
            content=text,
            title="Navamesh",
            desired_method=LXMF.LXMessage.OPPORTUNISTIC,
            fields=fields,
        )
        self._router.handle_outbound(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configdir",  required=True)
    ap.add_argument("--storagedir", required=True)
    ap.add_argument("--port",       type=int, required=True)
    ap.add_argument("--hashfile",   required=True)
    ap.add_argument("--wirelog",    default=None,
                    help="File to append each received wire content string (one per line)")
    args = ap.parse_args()

    rns = RNS.Reticulum(configdir=args.configdir, loglevel=RNS.LOG_WARNING)

    gw = StubGateway(args.storagedir, wirelog=args.wirelog)
    gw_hash = gw.start()
    gw.announce()

    with open(args.hashfile, "w") as f:
        f.write(gw_hash + "\n")
    sys.stdout.write(f"GATEWAY_READY hash={gw_hash}\n")
    sys.stdout.flush()

    # Re-announce frequently at startup so connecting clients hear it quickly,
    # then settle to a slow interval.
    startup_end = time.time() + 45
    while True:
        interval = 3 if time.time() < startup_end else 30
        time.sleep(interval)
        gw.announce()


if __name__ == "__main__":
    main()
