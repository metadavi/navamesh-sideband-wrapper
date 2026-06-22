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


def test_is_gateway_device_substring():
    """Device detection: any name containing 'gateway' (case-insensitive) is a
    gateway; everything else is a peer. The dest_hex arg is accepted (reserved
    for a future identity-based rule) without changing the result today."""
    from sbapp.farmui.devices import is_gateway_device, GATEWAY_DISPLAY_NAME
    assert is_gateway_device(GATEWAY_DISPLAY_NAME) is True
    assert is_gateway_device("East Gateway") is True
    assert is_gateway_device("GATEWAY") is True
    # Substring rule (intentionally looser than the old exact match):
    assert is_gateway_device("Navamesh Gateway extra") is True
    assert is_gateway_device("Navamesh Gateway", dest_hex="abc123") is True
    # Peers / non-gateways:
    assert is_gateway_device("My Sideband") is False
    assert is_gateway_device("Phone B") is False
    assert is_gateway_device("") is False
    assert is_gateway_device(None) is False


def test_stream_reexports_gateway_helper():
    """The Talk screen re-exports the canonical helper for back-compat."""
    from sbapp.farmui.screens.stream import is_gateway_device as via_stream
    from sbapp.farmui.devices import is_gateway_device as canonical
    assert via_stream is canonical


def test_large_text_setting_removed():
    """The Large Text preference is gone from settings (UI + scaling removed)."""
    from sbapp.farmui.settings import FarmSettings, _DEFAULT
    assert "large_text" not in _DEFAULT
    assert not hasattr(FarmSettings, "large_text")


def test_no_large_text_references_in_farmui():
    """No stray large-text scaling/handlers remain anywhere in farmui."""
    import os
    import sbapp.farmui as farmui_pkg
    root = os.path.dirname(farmui_pkg.__file__)
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8") as f:
                if "large_text" in f.read():
                    hits.append(os.path.relpath(path, root))
    assert not hits, f"large_text still referenced in: {hits}"


def test_build_lifts_content_for_soft_keyboard():
    """build() must set Window.softinput_mode so the composer rises above the
    Android keyboard (and drops back when dismissed). Source guard — build()
    needs a Kivy Window, unavailable headless."""
    import inspect
    from sbapp.farmui import app as app_mod
    src = inspect.getsource(app_mod.FarmApp.build)
    assert "softinput_mode" in src
    assert "below_target" in src


def test_bigbutton_min_height():
    """BigButton height constant >= 96dp."""
    from kivy.metrics import dp
    from sbapp.farmui import theme
    assert theme.BUTTON_HEIGHT >= 96


def test_command_tile_min_height():
    """Compact command tiles stay tappable: >= the 48dp touch-target minimum."""
    from sbapp.farmui import theme
    assert theme.COMMAND_TILE_HEIGHT >= theme.TOUCH_TARGET
    # ...and genuinely smaller than the primary CTA, so the grid is compacted.
    assert theme.COMMAND_TILE_HEIGHT < theme.BUTTON_HEIGHT


def test_reply_font_smaller_than_body():
    """Mono replies use a smaller size so terminal-width tables don't wrap."""
    from sbapp.farmui import theme
    assert theme.FONT_REPLY < theme.FONT_BODY


def test_status_chip_dot_uses_renderable_glyph():
    """The status dot must use a glyph the bundled font actually has.

    ● (U+25CF) is absent from the bundled text fonts (rendered as a □ box); the
    bullet • (U+2022) is present, so a [color]-markup bullet gives a crisp
    colored dot. Guard against regressing to the bare ●.
    """
    from sbapp.farmui.widgets import StatusChip
    assert StatusChip.DOT_GLYPH == "•"
    import inspect
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.StatusChip.set_state)
    assert "●" not in src, "bare ● (U+25CF) has no glyph and renders as a box"
    assert "[color=" in src, "the dot must carry the state hue via color markup"
