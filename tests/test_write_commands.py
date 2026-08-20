"""
test_write_commands.py — Control-command wire encoding and the confirm-before-send rule.

Control commands reconfigure deployed field hardware over LoRa. The source-guard tests
here exist because the dangerous regression is not a wrong string — it is a control
command that reaches dispatch without the farmer confirming it.
"""
from __future__ import annotations

import ast
import os

import pytest

# Suppress Kivy window creation during import (same as test_farmui_logic.py)
os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""


# ── wire strings (must match reticulum_bridge.handle_command exactly) ────────────

def test_write_command_wire_templates():
    from sbapp.farmui.command_registry import COMMANDS

    expected = {
        "ble_window":   "ble {id} {value}",
        "set_interval": "interval {id} {value}",
        "quiet_on":     "quiet {id} on",
        "quiet_off":    "quiet {id} off",
        "set_location": "setloc {id} {value}",
    }
    by_key = {c.key: c for c in COMMANDS}
    for key, wire in expected.items():
        assert by_key[key].wire == wire


def test_get_wire_substitutes_both_id_and_value():
    from sbapp.farmui.command_registry import get_wire
    assert get_wire("ble_window", node_id="!abc12345", value=30) == "ble !abc12345 30"
    assert get_wire("set_interval", node_id="^all", value=1800) == "interval ^all 1800"


def test_get_wire_does_not_collapse_node_commands_into_map():
    """
    Regression guard. get_wire() once hardcoded f"map {node_id}" for every needs_node
    command, which would silently turn a control command into a map request — sending
    something entirely different from what the farmer tapped.
    """
    from sbapp.farmui.command_registry import get_wire
    # Value must be in range per command: 30 min is valid for ble, but 30 s is below the
    # 60 s interval floor.
    cases = [
        ("ble_window", 30),
        ("set_interval", 1800),
        ("quiet_on", None),
        ("quiet_off", None),
    ]
    for key, value in cases:
        wire = get_wire(key, node_id="!abc12345", value=value)
        assert not wire.startswith("map "), f"{key} was encoded as a map command"


def test_get_wire_quiet_needs_no_value():
    from sbapp.farmui.command_registry import get_wire
    assert get_wire("quiet_on", node_id="!abc12345") == "quiet !abc12345 on"
    assert get_wire("quiet_off", node_id="!abc12345") == "quiet !abc12345 off"


def test_get_wire_requires_a_node_for_write_commands():
    from sbapp.farmui.command_registry import get_wire
    with pytest.raises(ValueError):
        get_wire("ble_window", value=30)


def test_get_wire_requires_a_value_where_the_template_needs_one():
    from sbapp.farmui.command_registry import get_wire
    with pytest.raises(ValueError):
        get_wire("ble_window", node_id="!abc12345")


@pytest.mark.parametrize("key,value", [
    ("ble_window", 0), ("ble_window", 241),
    ("set_interval", 59), ("set_interval", 86401),
])
def test_get_wire_enforces_bounds(key, value):
    from sbapp.farmui.command_registry import get_wire
    with pytest.raises(ValueError):
        get_wire(key, node_id="!abc12345", value=value)


def test_read_commands_are_unaffected():
    from sbapp.farmui.command_registry import get_wire
    assert get_wire("status") == "status"
    assert get_wire("map_all") == "map"
    assert get_wire("map_one", node_id="!drynode001") == "map !drynode001"


# ── presets ─────────────────────────────────────────────────────────────────────

def test_value_presets_are_all_within_bounds():
    """Presets are the only way to enter a value, so an out-of-range one is unreachable."""
    from sbapp.farmui.command_registry import COMMANDS
    for cmd in COMMANDS:
        for label, value in cmd.value_presets:
            assert cmd.value_min <= value <= cmd.value_max, (
                f"{cmd.key} preset {label!r}={value} is outside "
                f"{cmd.value_min}-{cmd.value_max}"
            )


def test_every_value_command_offers_presets():
    from sbapp.farmui.command_registry import COMMANDS
    for cmd in COMMANDS:
        if cmd.needs_value:
            assert cmd.value_presets, f"{cmd.key} needs a value but offers no presets"


# ── set node location ───────────────────────────────────────────────────────────

def test_set_location_is_not_a_preset_command():
    """
    needs_value means "offer preset buttons", and a live GPS position is the one value
    in this app with nothing to preset. needs_location must therefore stand apart, or
    test_every_value_command_offers_presets would be demanding presets that cannot exist.
    """
    from sbapp.farmui.command_registry import get_command
    cmd = get_command("set_location")
    assert cmd.needs_location is True
    assert cmd.needs_value is False
    assert cmd.value_presets == ()


def test_set_location_never_offers_broadcast():
    """One coordinate applied to every node would erase the node map in a single tap."""
    from sbapp.farmui.command_registry import COMMANDS, get_command
    assert get_command("set_location").allow_broadcast is False
    # Every other command keeps the old behaviour.
    for cmd in COMMANDS:
        if cmd.key != "set_location":
            assert cmd.allow_broadcast is True


def test_get_wire_formats_a_coordinate_pair():
    from sbapp.farmui.command_registry import get_wire
    wire = get_wire("set_location", node_id="!abc12345", value="36.0721 -109.045")
    assert wire == "setloc !abc12345 36.0721000 -109.0450000"


def test_get_wire_keeps_seven_decimal_places():
    """1e-7 degrees is ~1 cm; formatting at 6 dp would silently drop the last digit."""
    from sbapp.farmui.command_registry import get_wire
    wire = get_wire("set_location", node_id="!abc12345", value="36.0721234 -109.0450987")
    assert wire.endswith("36.0721234 -109.0450987")


def test_get_wire_does_not_truncate_a_coordinate_to_an_integer():
    """
    Regression guard. The generic value path runs int(value), which would turn a position
    into the middle of a different field — and the command would still look successful.
    """
    from sbapp.farmui.command_registry import get_wire
    wire = get_wire("set_location", node_id="!abc12345", value="36.0721 -109.045")
    assert "36.0721" in wire and "36 " not in wire


@pytest.mark.parametrize("bad", [
    "36.0721",              # longitude missing
    "36.0721 -109.045 12",  # a third number
    "north west",
    "91.0 -109.045",        # latitude past the pole
    "-90.001 -109.045",
    "36.0721 180.5",        # longitude past the antimeridian
    "36.0721 -180.5",
    "0 0",                  # no position was captured
    "",
])
def test_get_wire_rejects_bad_coordinates(bad):
    from sbapp.farmui.command_registry import get_wire
    with pytest.raises(ValueError):
        get_wire("set_location", node_id="!abc12345", value=bad)


def test_get_wire_requires_a_node_for_set_location():
    from sbapp.farmui.command_registry import get_wire
    with pytest.raises(ValueError):
        get_wire("set_location", value="36.0721 -109.045")


def test_write_commands_carry_a_confirm_hint():
    """The confirmation dialog explains the consequence; none may be blank."""
    from sbapp.farmui.command_registry import COMMANDS
    for cmd in COMMANDS:
        if cmd.is_write:
            assert cmd.confirm_hint.strip(), f"{cmd.key} has no confirm_hint"


# ── source guards: confirmation must precede dispatch ───────────────────────────
#
# These read the source files as text rather than importing the modules, because the UI
# modules pull in Kivy and these are the guards that most need to run everywhere,
# including CI without a display or a buildable Kivy.

_FARMUI = os.path.join(os.path.dirname(__file__), os.pardir, "sbapp", "farmui")


def _source(*parts) -> str:
    with open(os.path.join(_FARMUI, *parts), encoding="utf-8") as fh:
        return fh.read()


def _function_body(src: str, name: str) -> str:
    """Extract one top-level-or-method def body by indentation."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"function {name!r} not found")


def test_write_commands_route_to_confirmation_not_straight_to_send():
    """
    In ConversationScreen._on_command, a write command must go to _confirm_write, while
    read commands still go straight to _run_command.
    """
    body = _function_body(_source("screens", "conversation.py"), "_on_command")
    assert "is_write" in body
    assert "_confirm_write" in body


def test_confirm_dialog_dispatches_only_from_send():
    """
    ConfirmCommandDialog must invoke on_confirm from exactly one place: _send(). If
    _pick_value also fired it, choosing a value would transmit immediately and the
    confirmation step would be decorative.
    """
    src = _source("widgets.py")

    pick = _function_body(src, "_pick_value")
    assert "_on_confirm" not in pick, "choosing a value must not send"

    send = _function_body(src, "_send")
    assert "_on_confirm" in send

    # Scoped to the dialog class so an unrelated on_confirm elsewhere cannot mask this.
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "ConfirmCommandDialog")
    cls_src = ast.get_source_segment(src, cls) or ""
    assert cls_src.count("self._on_confirm(") == 1, (
        "on_confirm must be called from exactly one place (_send)"
    )


def test_node_picker_offers_broadcast_only_for_write_commands():
    body = _function_body(_source("app.py"), "open_node_picker")
    assert "include_broadcast" in body
    assert "is_write" in body


def test_node_picker_honours_allow_broadcast():
    """
    The ALL button must be gated on the command's own allow_broadcast too, not just on
    is_write — otherwise "Set node location" would offer a target it must never accept.
    """
    body = _function_body(_source("app.py"), "open_node_picker")
    assert "allow_broadcast" in body
    assert "is_write and allow_broadcast" in body


def test_location_capture_never_dispatches():
    """
    Capturing a position — from GPS or typed in — must advance to the confirm step and
    nothing more. Both paths funnel through _use_fix, so this pins that _use_fix leads to
    confirmation rather than to send.
    """
    src = _source("widgets.py")
    use_fix = _function_body(src, "_use_fix")
    assert "_build_confirm_step" in use_fix
    assert "_on_confirm" not in use_fix, "capturing a position must not send"

    for name in ("_on_fix", "_accept_manual", "_start_fix", "_build_manual_step"):
        assert "_on_confirm" not in _function_body(src, name), (
            f"{name} must not dispatch; only _send may"
        )


def test_a_dismissed_dialog_drops_a_late_gps_fix():
    """
    The search runs for up to 25 s and the farmer can close the dialog meanwhile. A late
    callback must not rebuild a dismissed dialog into an invisible one holding a captured
    position, so _on_fix bails on the dismissed flag before touching anything.
    """
    src = _source("widgets.py")
    # Scoped to the class: widgets.py defines many __init__s and _function_body finds
    # the first one in the file.
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "ConfirmCommandDialog")
    cls_src = ast.get_source_segment(src, cls) or ""
    assert "_mark_dismissed" in _function_body(cls_src, "__init__")

    body = _function_body(src, "_on_fix")
    assert "_dismissed" in body
    assert body.index("_dismissed") < body.index("_use_fix"), (
        "the dismissed check must come before the fix is accepted"
    )


def test_gps_callback_is_marshalled_onto_the_kivy_thread():
    """
    plyer delivers its location callback on whatever thread Android picks. Touching a
    widget from there is a crash that only reproduces on a phone, so the hop back through
    Clock.schedule_once is the whole safety of this path.
    """
    body = _function_body(_source("widgets.py"), "_start_fix")
    assert "Clock.schedule_once" in body
    assert "get_fix_async" in body


def test_dispatch_command_threads_value_through_to_get_wire():
    body = _function_body(_source("app.py"), "dispatch_command")
    assert "get_wire(cmd_key, node_id, value)" in body
