"""
test_location.py — the one-shot GPS fix behind "Set node location".

farmui/location.py deliberately imports no Kivy, so all of this runs on a desktop with no
phone and no display. The Android-only branches are covered by monkeypatching is_android,
which is the same seam the module itself uses to stay callable off-device.
"""
from __future__ import annotations

import pytest

from sbapp.farmui import location as loc


# ── Fix ──────────────────────────────────────────────────────────────────────────

def test_wire_value_keeps_seven_decimal_places():
    """1e-7 degrees is ~1 cm. Six would quietly drop the last digit of every fix."""
    fix = loc.Fix(36.0721234, -109.0450987, accuracy_m=5.0)
    assert fix.as_wire_value() == "36.0721234 -109.0450987"


def test_wire_value_pads_short_coordinates():
    assert loc.Fix(36.0, -109.0).as_wire_value() == "36.0000000 -109.0000000"


@pytest.mark.parametrize("accuracy,poor", [
    (5.0, False),
    (loc.POOR_ACCURACY_M, False),
    (loc.POOR_ACCURACY_M + 0.1, True),
    (None, True),
])
def test_poor_accuracy_classification(accuracy, poor):
    assert loc.Fix(36.0, -109.0, accuracy).is_poor is poor


def test_unknown_accuracy_counts_as_poor():
    """
    Explicit because the tempting default is the wrong one. Treating "the phone did not
    say" as "good" is how a node gets confidently pinned to the wrong place, with no
    warning shown to the one person standing there who could catch it.
    """
    assert loc.Fix(36.0, -109.0, accuracy_m=None).is_poor is True


# ── manual entry ─────────────────────────────────────────────────────────────────

def test_parse_manual_accepts_a_normal_pair():
    fix, error = loc.parse_manual("36.0721", "-109.0450")
    assert error is None
    assert fix.latitude == 36.0721
    assert fix.longitude == -109.0450
    # Nothing vouches for a typed number, so it carries no accuracy and reads as poor.
    assert fix.accuracy_m is None
    assert fix.is_poor is True


def test_parse_manual_tolerates_surrounding_whitespace():
    fix, error = loc.parse_manual("  36.0721 ", " -109.0450  ")
    assert error is None and fix.latitude == 36.0721


def test_parse_manual_accepts_whole_degrees():
    fix, error = loc.parse_manual("36", "-109")
    assert error is None
    assert (fix.latitude, fix.longitude) == (36.0, -109.0)


@pytest.mark.parametrize("lat,lon", [
    ("", "-109.045"),
    ("36.0721", ""),
    ("north", "-109.045"),
    ("36.0721", "west"),
    ("91", "-109.045"),
    ("-90.001", "-109.045"),
    ("36.0721", "180.5"),
    ("36.0721", "-180.5"),
    ("0", "0"),
])
def test_parse_manual_rejects_bad_input_with_a_reason(lat, lon):
    fix, error = loc.parse_manual(lat, lon)
    assert fix is None
    # Shown to a farmer in a dialog, not written to a log: a finished sentence, not a
    # bare "invalid input" or a repr.
    assert error and error.endswith(".") and " " in error


@pytest.mark.parametrize("lat,lon", [(90, 0.1), (-90, 0.1), (0.1, 180), (0.1, -180)])
def test_parse_manual_accepts_the_exact_bounds(lat, lon):
    fix, error = loc.parse_manual(str(lat), str(lon))
    assert error is None and fix is not None


# ── off-Android behaviour ────────────────────────────────────────────────────────

def test_get_fix_off_android_explains_itself_instead_of_raising(monkeypatch):
    """
    A desktop build has no GPS. This must return a sentence the dialog can show, not an
    exception and not a silent None — the farmer needs to be pointed at manual entry.
    """
    monkeypatch.setattr(loc, "is_android", lambda: False)
    fix, error = loc.get_fix(timeout=0.1)
    assert fix is None
    assert "no GPS" in error


def test_request_permissions_is_a_noop_off_android(monkeypatch):
    monkeypatch.setattr(loc, "is_android", lambda: False)
    loc.request_permissions()  # must not raise


def test_has_permissions_is_false_off_android(monkeypatch):
    monkeypatch.setattr(loc, "is_android", lambda: False)
    assert loc.has_permissions() is False


def test_get_fix_reports_refused_permission_distinctly(monkeypatch):
    """
    farmui never asked for these at runtime before this feature, so a fresh install with
    the permission refused is the likeliest first failure. It must not read as "no fix".
    """
    monkeypatch.setattr(loc, "is_android", lambda: True)
    monkeypatch.setattr(loc, "request_permissions", lambda: None)
    monkeypatch.setattr(loc, "has_permissions", lambda: False)
    fix, error = loc.get_fix(timeout=0.1)
    assert fix is None
    assert "permission" in error.lower()


def test_get_fix_async_delivers_the_failure_rather_than_hanging(monkeypatch):
    """A spinner that never clears is worse than a message; the callback always fires."""
    monkeypatch.setattr(loc, "is_android", lambda: False)
    got = []
    loc.get_fix_async(lambda fix, error: got.append((fix, error)), timeout=0.1).join(5)
    assert len(got) == 1
    assert got[0][0] is None and got[0][1]


# ── coordinate keystroke filter ──────────────────────────────────────────────────

def test_filter_allows_a_leading_minus():
    """
    The bug this exists to prevent. Kivy's input_filter="float" strips everything outside
    [0-9.], so a farmer could not type -109.0450 at all — and every longitude on this farm
    is negative, so the manual fallback would be unusable exactly where it is needed.
    """
    assert loc.coordinate_filter("", "-") == "-"


def test_filter_rejects_a_minus_that_is_not_leading():
    assert loc.coordinate_filter("109", "-") == ""
    assert loc.coordinate_filter("-109", "-") == ""


def test_filter_allows_digits_and_one_decimal_point():
    assert loc.coordinate_filter("", "36") == "36"
    assert loc.coordinate_filter("36", ".") == "."
    assert loc.coordinate_filter("36.07", ".") == ""


def test_filter_allows_only_one_point_within_a_single_paste():
    assert loc.coordinate_filter("", "36.07.21") == "36.0721"


def test_filter_drops_letters_and_spaces():
    assert loc.coordinate_filter("", "36 N abc") == "36"


def test_filter_passes_a_realistic_pasted_coordinate_through_intact():
    assert loc.coordinate_filter("", "-109.0450987") == "-109.0450987"


# ── fix selection ────────────────────────────────────────────────────────────────

def test_tighter_prefers_the_smaller_accuracy():
    assert loc._tighter(loc.Fix(0, 0, 5.0), loc.Fix(0, 0, 20.0)) is True
    assert loc._tighter(loc.Fix(0, 0, 20.0), loc.Fix(0, 0, 5.0)) is False


def test_tighter_prefers_a_known_accuracy_over_an_unknown_one():
    assert loc._tighter(loc.Fix(0, 0, 60.0), loc.Fix(0, 0, None)) is True
    assert loc._tighter(loc.Fix(0, 0, None), loc.Fix(0, 0, 60.0)) is False


def test_good_enough_threshold_is_inside_the_poor_warning():
    """
    Stopping early must never hand back a fix the confirm step would then warn about, or
    the app would be settling for a position it does not itself trust.
    """
    assert loc.GOOD_ENOUGH_ACCURACY_M < loc.POOR_ACCURACY_M
