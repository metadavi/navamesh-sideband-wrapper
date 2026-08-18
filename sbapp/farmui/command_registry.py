"""
command_registry.py — The gateway commands with display metadata.

Wire strings must match reticulum_bridge.py exactly (case-insensitive on the
gateway side, so we send lowercase). See tests/rig/CONTRACT.md.

Two families live here:

  * READ commands (status, soil, ...) — safe, single tap, answered from the Pi's database.
  * WRITE commands (ble, interval, quiet) — these change deployed field hardware over
    LoRa. They carry `is_write=True`, which the UI uses to require a confirmation step.
    The gateway currently accepts them from any sender that can reach it (see the Pi
    repo's TODO.md); the confirmation dialog is therefore the ONLY thing between a tap
    and a reconfigured node, so do not bypass it.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Command:
    key: str          # unique key for this command
    wire: str         # exact string sent over LXMF; may contain {id} and {value}
    icon: str         # emoji icon
    label: str        # plain-language farmer label
    needs_node: bool  # True → requires a node picker
    # --- write-command metadata (unused by the read commands) ---
    is_write: bool = False       # True → mutates field hardware; UI must confirm first
    needs_value: bool = False    # True → requires a numeric argument
    value_label: str = ""        # e.g. "Minutes"
    value_default: int = 0
    value_min: int = 0
    value_max: int = 0
    # For on/off style commands, the literal appended instead of a number.
    value_choices: tuple = ()
    # Shown in the confirmation dialog, phrased for someone standing in a field.
    confirm_hint: str = ""
    # (label, value) presets offered as buttons. Presets rather than a text field keeps
    # the "no typing anywhere" rule that the rest of this UI follows, and makes an
    # out-of-range value impossible to enter in the first place.
    value_presets: tuple = ()


# Bounds mirror the firmware clamps (NavameshCommand.cpp) and the Pi's validation in
# processors/command_proto.py. Three copies is deliberate: the UI stops a bad value before
# it is sent, the Pi rejects it with a readable message if it arrives anyway, and the node
# clamps it as a last resort.
COMMANDS: list[Command] = [
    Command("status",    "status",    "📋", "Farm status",     False),
    Command("soil",      "soil",      "💧", "Soil moisture",   False),
    Command("battery",   "battery",   "🔋", "Battery",         False),
    Command("position",  "position",  "📍", "Position",        False),
    Command("link",      "link",      "📡", "Link strength",   False),
    Command("map_all",   "map",       "🗺",  "Map — all nodes", False),
    Command("map_one",   "map {id}",  "🗺",  "Map — one node",  True),
    Command("nodes",     "nodes",     "🛰",  "List nodes",      False),
    Command("help",      "help",      "❓", "Help",            False),

    Command(
        "ble_window", "ble {id} {value}", "🔧", "Open Bluetooth window", True,
        is_write=True, needs_value=True, value_label="Minutes",
        value_default=30, value_min=1, value_max=240,
        confirm_hint=("The node turns Bluetooth on for this long, then switches it off "
                      "again by itself. Connect while the window is open."),
        value_presets=(("5 min", 5), ("15 min", 15), ("30 min", 30),
                       ("1 hour", 60), ("2 hours", 120)),
    ),
    Command(
        "set_interval", "interval {id} {value}", "⏱", "Set reporting interval", True,
        is_write=True, needs_value=True, value_label="Seconds",
        value_default=1800, value_min=60, value_max=86400,
        confirm_hint=("How often the node reports. Shorter gives finer data but uses more "
                      "battery. Takes effect immediately, no reboot."),
        # 5 min is the firmware floor. 8 h is the deployed default, kept as a preset so
        # an experiment can be wound back to normal without remembering the number.
        value_presets=(("5 min", 300), ("15 min", 900), ("30 min", 1800),
                       ("1 hour", 3600), ("8 hours", 28800), ("24 hours", 86400)),
    ),
    Command(
        "quiet_on", "quiet {id} on", "🔇", "Pause transmitting", True,
        is_write=True, value_choices=("on",),
        confirm_hint=("The node stops sending but keeps listening, so you can resume it "
                      "at any time. It also resumes on its own within 3 days, and any "
                      "reboot resumes it immediately."),
    ),
    Command(
        "quiet_off", "quiet {id} off", "🔊", "Resume transmitting", True,
        is_write=True, value_choices=("off",),
        confirm_hint="The node starts sending readings again.",
    ),
]

COMMAND_WIRE_STRINGS = [c.wire for c in COMMANDS]

# Sentinel the UI passes as node_id to address every field node at once. Matches the
# gateway's BROADCAST_TARGET.
BROADCAST_ID = "^all"


def get_command(key: str) -> Command:
    cmd = next((c for c in COMMANDS if c.key == key), None)
    if cmd is None:
        raise KeyError(f"Unknown command key: {key!r}")
    return cmd


def get_wire(key: str, node_id: Optional[str] = None, value: Optional[int] = None) -> str:
    """
    Return the wire string for a command, substituting {id} and {value}.

    Note this fills the placeholders in `cmd.wire` rather than rebuilding the string.
    An earlier version hardcoded `f"map {node_id}"` for every needs_node command, which
    silently turned any other node-targeted command into a `map` request.
    """
    cmd = get_command(key)
    wire = cmd.wire

    if "{id}" in wire:
        if not node_id:
            raise ValueError(f"Command {key!r} requires a node_id")
        wire = wire.replace("{id}", node_id)

    if "{value}" in wire:
        if value is None:
            raise ValueError(f"Command {key!r} requires a value")
        if not cmd.value_min <= int(value) <= cmd.value_max:
            raise ValueError(
                f"{cmd.value_label or 'value'} for {key!r} must be "
                f"{cmd.value_min}-{cmd.value_max}, got {value}"
            )
        wire = wire.replace("{value}", str(int(value)))

    return wire
