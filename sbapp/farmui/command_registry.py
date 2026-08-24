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
    # True → the value is a "<lat> <lon>" string the farmer captures from the phone's GPS
    # (or types in, if there is no fix), not a number chosen from presets.
    #
    # Deliberately NOT needs_value: that flag means "offer preset buttons", and a live
    # position is the one value in this app with nothing to preset. get_wire() therefore
    # substitutes a needs_location value verbatim and skips the int bounds check, which
    # would be meaningless for a coordinate pair.
    needs_location: bool = False
    # False → the node picker hides its "ALL FIELD NODES" button for this command.
    allow_broadcast: bool = True
    # True → the value step offers "Enter a time" beside the presets, for a cadence the
    # presets do not cover.
    #
    # A considered exception to the presets-only rule above, not a gap being filled. The
    # precedent is set_location's "Enter coordinates", which exists because a live position
    # has nothing sensible to preset. This is the other reason to break it: the presets are
    # the cadences we expected, and an experiment is exactly the thing that wants one we did
    # not. Unlike a coordinate pair, the value is an int with real bounds, so it is validated
    # here as strictly as a preset would have been -- get_wire()'s bounds check still applies,
    # which is why this is NOT modelled on needs_location's skip.
    allow_manual_value: bool = False


# Bounds mirror the firmware clamps (NavameshCommand.cpp) and the Pi's validation in
# processors/command_proto.py. Three copies is deliberate: the UI stops a bad value before
# it is sent, the Pi rejects it with a readable message if it arrives anyway, and the node
# clamps it as a last resort.
COMMANDS: list[Command] = [
    # Help first: it is the one command a farmer reaches for when they do not already
    # know what the others do, so it should not be the last thing they find.
    Command("help",      "help",      "❓", "Help",            False),
    Command("status",    "status",    "📋", "Farm status",     False),
    Command("soil",      "soil",      "💧", "Soil moisture",   False),
    Command("battery",   "battery",   "🔋", "Battery",         False),
    Command("position",  "position",  "📍", "Position",        False),
    Command("link",      "link",      "📡", "Sensor strength", False),
    Command("map_all",   "map",       "🗺",  "Map — all nodes", False),
    Command("map_one",   "map {id}",  "🗺",  "Map — one node",  True),
    Command("nodes",     "nodes",     "🛰",  "List nodes",      False),

    Command(
        "ble_window", "ble {id} {value}", "🔧", "Bluetooth on", True,
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
        # Farmers asked to time a specific node themselves rather than pick from this list.
        # The wire unit stays seconds -- the app converts, so neither the Pi nor the firmware
        # had to learn a new format for this.
        allow_manual_value=True,
    ),
    Command(
        "quiet_on", "quiet {id} on", "🔇", "Pause messaging", True,
        is_write=True, value_choices=("on",),
        # "after a day", not "within 3 days": the UI sends no duration, so the node
        # applies NAVAMESH_QUIET_DEFAULT_MINUTES = 1440. 4320 (three days) is only the
        # firmware's clamp ceiling. Caught on the bench when the ack came back
        # applied=1440 against text promising three days -- not false, but wrong in the
        # direction that matters: a farmer expecting three days of quiet gets the sensor
        # back after one, and one who wants it back sooner thinks they must wait three.
        confirm_hint=("The node stops sending but keeps listening, so you can resume it "
                      "at any time. It also resumes on its own after a day, and any "
                      "reboot resumes it immediately."),
    ),
    Command(
        "quiet_off", "quiet {id} off", "🔊", "Resume messaging", True,
        is_write=True, value_choices=("off",),
        confirm_hint="The node starts sending readings again.",
    ),
    Command(
        "set_location", "setloc {id} {value}", "📍", "Change sensor location", True,
        is_write=True, needs_location=True, allow_broadcast=False,
        confirm_hint=("The node has no GPS of its own, so it uses your phone's position. "
                      "Stand next to the node before you send this."),
    ),
]

# What "Enter a time" offers. Minutes and hours only: seconds is the protocol's unit and
# nobody standing in a field thinks in it, and days would exceed the 24 h ceiling on the
# first tap, which is a worse way to learn the bound than not being offered it.
VALUE_UNITS = (("Minutes", 60), ("Hours", 3600))


def seconds_from_units(magnitude, unit_seconds: int) -> int:
    """Convert a farmer-entered number and unit into the seconds the wire carries.

    Rounded to a whole second because the protobuf field is a uint32. Kept as a function
    rather than inlined in the dialog so the conversion is testable off-device -- the UI
    itself cannot run outside Android.
    """
    return int(round(float(magnitude) * int(unit_seconds)))


def validate_manual_value(key: str, magnitude, unit_seconds: int):
    """Return (seconds, error). Exactly one is None.

    The bounds check is the same one get_wire() applies, run early so the farmer is told
    while the number is still on screen rather than after they confirm. Rejecting rather
    than clamping: someone who typed 30 hours meant something this cannot do, and quietly
    giving them 24 would look like it worked.
    """
    cmd = get_command(key)
    text = str(magnitude).strip()
    if not text:
        return None, "Enter a number first."
    try:
        value = float(text)
    except ValueError:
        return None, f"{text!r} is not a number."
    if value <= 0:
        return None, "Enter a number greater than zero."

    seconds = seconds_from_units(value, unit_seconds)
    if not cmd.value_min <= seconds <= cmd.value_max:
        return None, (
            f"Must be between {_friendly_seconds(cmd.value_min)} and "
            f"{_friendly_seconds(cmd.value_max)}. That is {_friendly_seconds(seconds)}."
        )
    return seconds, None


def _friendly_seconds(seconds: int) -> str:
    """Seconds as a person would say them. Mirrors the gateway's _friendly_seconds so an
    out-of-range message here reads like the confirmations that follow it."""
    s = int(seconds)
    if s % 86400 == 0 and s >= 86400:
        n = s // 86400
        return f"{n} day" if n == 1 else f"{n} days"
    if s % 3600 == 0 and s >= 3600:
        n = s // 3600
        return f"{n} hour" if n == 1 else f"{n} hours"
    if s % 60 == 0 and s >= 60:
        n = s // 60
        return f"{n} minute" if n == 1 else f"{n} minutes"
    return f"{s} seconds"


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
        if cmd.needs_location:
            # Already formatted as "<lat> <lon>" by the confirm dialog, and validated there
            # against +/-90 / +/-180. int() would truncate it and the min/max bounds are a
            # numeric range that says nothing about a coordinate pair.
            wire = wire.replace("{value}", _validated_latlon(key, value))
        else:
            if not cmd.value_min <= int(value) <= cmd.value_max:
                raise ValueError(
                    f"{cmd.value_label or 'value'} for {key!r} must be "
                    f"{cmd.value_min}-{cmd.value_max}, got {value}"
                )
            wire = wire.replace("{value}", str(int(value)))

    return wire


def _validated_latlon(key: str, value) -> str:
    """
    Re-check a "<lat> <lon>" string on its way to the wire.

    The dialog validates before it gets here; this is the last gate, and it is worth having
    because a malformed coordinate does not fail loudly downstream -- it becomes a plausible
    number somewhere else on Earth.
    """
    bits = str(value).split()
    if len(bits) != 2:
        raise ValueError(f"Command {key!r} needs a latitude and a longitude, got {value!r}")
    try:
        lat, lon = float(bits[0]), float(bits[1])
    except ValueError:
        raise ValueError(f"{value!r} is not a latitude and longitude in decimal degrees")
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Latitude must be -90 to 90, got {lat}")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitude must be -180 to 180, got {lon}")
    if lat == 0.0 and lon == 0.0:
        raise ValueError("Refusing to send 0, 0 — that means no position was captured")
    return f"{lat:.7f} {lon:.7f}"
