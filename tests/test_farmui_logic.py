"""
test_farmui_logic.py — Pure-logic tests for the farmui package.
No display / Kivy window required.
"""
from __future__ import annotations

import os
import sys

# Suppress Kivy window creation during import
os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""  # prevent SDL2 from trying real display


def test_command_registry_count():
    """Exactly 9 commands defined."""
    from sbapp.farmui.command_registry import COMMANDS
    assert len(COMMANDS) == 9


def test_command_wire_strings():
    """Every command has the correct wire string per CONTRACT.md."""
    from sbapp.farmui.command_registry import COMMANDS, get_wire

    expected = {
        "status":   "status",
        "soil":     "soil",
        "battery":  "battery",
        "position": "position",
        "link":     "link",
        "map_all":  "map",
        "map_one":  "map {id}",   # template; resolved by get_wire with node_id
        "nodes":    "nodes",
        "help":     "help",
    }
    by_key = {c.key: c for c in COMMANDS}
    for key, wire in expected.items():
        assert key in by_key, f"Missing command key: {key}"
        assert by_key[key].wire == wire, (
            f"Command {key!r}: expected wire={wire!r}, got {by_key[key].wire!r}"
        )


def test_get_wire_simple():
    from sbapp.farmui.command_registry import get_wire
    assert get_wire("status") == "status"
    assert get_wire("soil")   == "soil"
    assert get_wire("map_all") == "map"


def test_get_wire_node_picker():
    from sbapp.farmui.command_registry import get_wire
    result = get_wire("map_one", node_id="!drynode001")
    assert result == "map !drynode001"


def test_get_wire_node_missing_raises():
    from sbapp.farmui.command_registry import get_wire
    import pytest
    with pytest.raises(ValueError):
        get_wire("map_one")


def test_command_all_have_icon_and_label():
    from sbapp.farmui.command_registry import COMMANDS
    for cmd in COMMANDS:
        assert cmd.icon, f"Command {cmd.key!r} has no icon"
        assert cmd.label, f"Command {cmd.key!r} has no label"


def test_contrast_ratios_aa():
    """All token pairs must meet WCAG AA (≥4.5:1)."""
    from sbapp.farmui.theme import TOKEN_PAIRS, contrast_ratio
    failures = []
    for name, fg, bg in TOKEN_PAIRS:
        ratio = contrast_ratio(fg, bg)
        if ratio < 4.5:
            failures.append(f"{name}: {ratio:.2f}:1 (need ≥4.5:1)")
    assert not failures, "Contrast failures:\n" + "\n".join(failures)


def test_contrast_helper_known_value():
    """Black-on-white = 21:1 (exactly)."""
    from sbapp.farmui.theme import contrast_ratio
    ratio = contrast_ratio("#000000", "#FFFFFF")
    assert abs(ratio - 21.0) < 0.01, f"Expected ~21.0, got {ratio}"


def test_announce_list_adapter_highlight():
    """Announce stream: 'Navamesh Gateway' should be flagged as a gateway."""
    from sbapp.farmui.screens.stream import _is_gateway, GATEWAY_DISPLAY_NAME
    assert _is_gateway(GATEWAY_DISPLAY_NAME) is True
    assert _is_gateway("Some other device") is False
    assert _is_gateway("") is False


def test_announce_list_adapter_non_gateway():
    from sbapp.farmui.screens.stream import _is_gateway
    assert _is_gateway("My Sideband") is False
    assert _is_gateway("Navamesh Gateway extra") is False


def test_bigbutton_min_height():
    """BigButton height constant >= 96dp."""
    from kivy.metrics import dp
    from sbapp.farmui import theme
    assert theme.BUTTON_HEIGHT >= 96
