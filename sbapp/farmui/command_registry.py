"""
command_registry.py — The 9 gateway commands with display metadata.

Wire strings must match reticulum_bridge.py exactly (case-insensitive on the
gateway side, so we send lowercase). See tests/rig/CONTRACT.md.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Command:
    key: str          # unique key for this command
    wire: str         # exact string sent over LXMF
    icon: str         # emoji icon
    label: str        # plain-language farmer label
    needs_node: bool  # True → requires a node picker (map <id>)


COMMANDS: list[Command] = [
    Command("status",    "status",    "📋", "Farm status",     False),
    Command("soil",      "soil",      "💧", "Soil moisture",   False),
    Command("battery",   "battery",   "🔋", "Battery",         False),
    Command("position",  "position",  "📍", "Locations",       False),
    Command("link",      "link",      "📡", "Signal (RSSI)",   False),
    Command("map_all",   "map",       "🗺",  "Map — all nodes", False),
    Command("map_one",   "map {id}",  "🗺",  "Map — one node",  True),
    Command("nodes",     "nodes",     "🛰",  "List nodes",      False),
    Command("help",      "help",      "❓", "Help",            False),
]

COMMAND_WIRE_STRINGS = [c.wire for c in COMMANDS]


def get_wire(key: str, node_id: Optional[str] = None) -> str:
    """Return the wire string for the given command key, substituting node_id if needed."""
    cmd = next((c for c in COMMANDS if c.key == key), None)
    if cmd is None:
        raise KeyError(f"Unknown command key: {key!r}")
    if cmd.needs_node:
        if not node_id:
            raise ValueError(f"Command {key!r} requires a node_id")
        return f"map {node_id}"
    return cmd.wire
