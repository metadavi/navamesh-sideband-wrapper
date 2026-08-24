"""
test_manual_interval.py — "Enter a time" for the reporting interval.

The write commands offer value_presets only, deliberately: it keeps the "no typing
anywhere" rule the rest of this UI follows, and a preset list makes an out-of-range value
impossible to enter. This is a considered exception to that, not a gap being filled --
farmers asked to time a specific node themselves rather than pick from a list.

The precedent is set_location's "Enter coordinates". The difference that matters: a
coordinate pair has no meaningful numeric bounds, so get_wire() skips the check for it. An
interval is an int and the bounds DO apply, so this must be validated as strictly as a
preset would have been. These tests pin that difference.
"""
from __future__ import annotations

import os
import inspect

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""


# ── Conversion ──────────────────────────────────────────────────────────────────

def test_minutes_and_hours_convert_to_the_seconds_the_wire_carries():
    from sbapp.farmui.command_registry import seconds_from_units
    assert seconds_from_units(45, 60) == 2700
    assert seconds_from_units(3, 3600) == 10800
    assert seconds_from_units(1, 60) == 60


def test_only_minutes_and_hours_are_offered():
    """Seconds is the protocol's unit and nobody standing in a field thinks in it. Days
    would exceed the 24 h ceiling on the first tap, which is a worse way to meet a bound
    than not being offered it."""
    from sbapp.farmui.command_registry import VALUE_UNITS
    assert [label for label, _ in VALUE_UNITS] == ["Minutes", "Hours"]


# ── Validation, which is the whole point of not copying needs_location ──────────

def test_a_value_inside_the_bounds_is_accepted():
    from sbapp.farmui.command_registry import validate_manual_value
    seconds, error = validate_manual_value("set_interval", "45", 60)
    assert error is None
    assert seconds == 2700


def test_a_value_over_the_ceiling_is_refused_not_clamped():
    """Someone who typed 30 hours meant something this system cannot do. Quietly giving
    them 24 would look like it worked."""
    from sbapp.farmui.command_registry import validate_manual_value
    seconds, error = validate_manual_value("set_interval", "30", 3600)
    assert seconds is None
    assert error and "24" not in error.split(".")[0].replace("1 day", "")


def test_a_value_under_the_floor_is_refused():
    from sbapp.farmui.command_registry import validate_manual_value
    seconds, error = validate_manual_value("set_interval", "0", 60)
    assert seconds is None and error


def test_the_bounds_are_the_registry_bounds_not_a_second_copy():
    """Bounds stay triplicated across UI, Pi and firmware -- but within the UI there must
    be exactly one copy, or the manual path and the preset path can disagree."""
    from sbapp.farmui.command_registry import validate_manual_value, get_command
    cmd = get_command("set_interval")
    assert validate_manual_value("set_interval", cmd.value_min, 1)[0] == cmd.value_min
    assert validate_manual_value("set_interval", cmd.value_max, 1)[0] == cmd.value_max
    assert validate_manual_value("set_interval", cmd.value_max + 1, 1)[0] is None


def test_junk_is_refused_with_the_text_the_farmer_typed():
    from sbapp.farmui.command_registry import validate_manual_value
    seconds, error = validate_manual_value("set_interval", "abc", 60)
    assert seconds is None
    assert "abc" in error


def test_an_out_of_range_message_says_what_they_asked_for_in_their_own_units():
    """'Must be 60-86400 seconds' asks a farmer who typed 30 hours to convert twice."""
    from sbapp.farmui.command_registry import validate_manual_value
    _, error = validate_manual_value("set_interval", "30", 3600)
    assert "30 hours" in error


# ── Only the interval offers it ─────────────────────────────────────────────────

def test_manual_entry_is_opt_in_per_command():
    """A BLE window or a quiet duration has no equivalent demand, and every manual field
    is another place an out-of-range value can be typed."""
    from sbapp.farmui.command_registry import COMMANDS
    allowed = {c.key for c in COMMANDS if getattr(c, "allow_manual_value", False)}
    assert allowed == {"set_interval"}


def test_the_wire_string_is_unchanged_so_the_pi_and_firmware_did_not_have_to_learn_units():
    from sbapp.farmui.command_registry import get_wire
    assert get_wire("set_interval", "!0b9aed49", 2700) == "interval !0b9aed49 2700"


def test_get_wire_still_bounds_check_a_manually_entered_value():
    """The dialog validates first, but get_wire is the last gate in this process and must
    not be weakened for the manual path the way needs_location weakened it."""
    import pytest
    from sbapp.farmui.command_registry import get_wire
    with pytest.raises(ValueError):
        get_wire("set_interval", "!0b9aed49", 999999)


# ── Dialog wiring (source guards -- Kivy cannot run off-device) ─────────────────

def test_the_manual_step_validates_before_advancing():
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.ConfirmCommandDialog._accept_manual_value)
    assert "validate_manual_value" in src
    # Must not send: picking a value advances to the confirm step, exactly like a preset.
    assert "_pick_value" in src
    assert "_on_confirm" not in src


def test_the_manual_button_appears_only_for_commands_that_allow_it():
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.ConfirmCommandDialog._build_value_step)
    assert "allow_manual_value" in src


def test_the_confirmation_reads_in_the_farmers_units():
    """This is the last screen before a deployed node is reconfigured. 'every 45 minutes',
    not '2700 seconds'."""
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.ConfirmCommandDialog._summary)
    assert "_friendly_seconds" in src


# ── The reply area (source guards — Kivy layout cannot run off-device) ──────────

def test_the_whole_page_scrolls_not_just_the_reply_area():
    """The gateway strip and a 14-tile grid used to be fixed above a small ScrollView,
    so a 27-line `help` reply arrived in a viewport showing about eight lines and read
    as truncated. The grid now scrolls away with everything else."""
    import inspect
    from sbapp.farmui.screens import conversation
    src = inspect.getsource(conversation.ConversationScreen.__init__)
    # The command grid and the gateway header go into the scrolling column, not
    # straight onto the screen.
    assert "content.add_widget(grid)" in src
    assert "content.add_widget(header)" in src
    assert "self._page.add_widget(content)" in src
    # Only the back bar stays pinned.
    assert "self.add_widget(BackBar" in src


def test_the_scrolling_column_is_driven_by_its_content_height():
    """A size_hint_y=None column that does not track minimum_height collapses, taking
    every reply with it."""
    import inspect
    from sbapp.farmui.screens import conversation
    src = inspect.getsource(conversation.ConversationScreen.__init__)
    assert 'content.bind(minimum_height=content.setter("height"))' in src


def test_the_empty_state_is_given_an_explicit_height():
    """EmptyState stretches by default, and a stretching child contributes nothing to a
    minimum_height column -- it would vanish rather than hold its place."""
    import inspect
    from sbapp.farmui.screens import conversation
    src = inspect.getsource(conversation.ConversationScreen.__init__)
    assert "self._empty = EmptyState(" in src
    empty_call = src[src.index("self._empty = EmptyState("):]
    assert "size_hint_y=None" in empty_call[:300]


def test_a_new_reply_scrolls_itself_into_view():
    """With the grid scrolling, a reply lands below the fold -- without this the farmer
    taps a command and the screen appears not to change."""
    import inspect
    from sbapp.farmui.screens import conversation
    assert "self._reveal_replies()" in inspect.getsource(
        conversation.ConversationScreen.add_result)
    reveal = inspect.getsource(conversation.ConversationScreen._reveal_replies)
    # Deferred: a ResultCard's height comes from its texture and is 0 when added.
    assert "Clock.schedule_once" in reveal
    assert "scroll_to" in reveal
    # And it must never be able to take down the reply it is scrolling to.
    assert "except Exception" in reveal
