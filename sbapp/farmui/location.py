"""
location.py — one-shot GPS fix for the "Set node location" command.

The field nodes ship with gps_mode = NOT_PRESENT and have no receiver of their own, so
a node's position can only ever come from outside it. The stock Meshtastic app supplies
one by copying the connected phone's fix over Bluetooth; this module is where the same
fix comes from when the command travels over LoRa instead.

Why not Sideband's own telemetry Location sensor (sbapp/sideband/sense.py): it lives in
the Android foreground service process, reachable from this UI process only through
getstate/setstate, and it only runs at all once the whole telemetry subsystem is switched
on via telemetry_enabled + telemetry_s_location. That is a lot of standing machinery to
enable for a reading the farmer wants once, while standing next to a node. sense.py is
also protected upstream code (see docs/DECISION.md), so this calls plyer directly the way
upstream's own main.py does for its Bluetooth-scan flow.

Everything here is callable off Android: get_fix() reports "no GPS on this platform" on
desktop rather than raising, so the dialog falls back to manual entry and the flow stays
testable without a phone.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional

# How long to wait for a fix before giving up and offering manual entry. A cold start
# under open sky is usually 10-30 s; longer than this and the farmer is better served by
# being told to step into the open than by a spinner that never resolves.
FIX_TIMEOUT_SECONDS = 25.0

# Stop early once a fix is at least this good, rather than burning the full timeout. 10 m
# is well inside what matters here: nodes sit metres apart at most, and the position is
# used to put a pin on a farm map, not to survey a boundary.
GOOD_ENOUGH_ACCURACY_M = 10.0

# Above this, the dialog warns before sending. A fix this coarse can place a node in the
# wrong part of the field, and the farmer standing next to it is the only person who can
# tell that it is wrong.
POOR_ACCURACY_M = 50.0

_ANDROID_PERMISSIONS = [
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_FINE_LOCATION",
]


@dataclass
class Fix:
    """A position from the phone. `accuracy_m` is None when the platform omits it."""
    latitude: float
    longitude: float
    accuracy_m: Optional[float] = None

    @property
    def is_poor(self) -> bool:
        # Unknown accuracy counts as poor: silently treating "no idea" as "good" is how a
        # node ends up confidently pinned to the wrong place.
        return self.accuracy_m is None or self.accuracy_m > POOR_ACCURACY_M

    def as_wire_value(self) -> str:
        """The "<lat> <lon>" string command_registry.get_wire() substitutes."""
        return f"{self.latitude:.7f} {self.longitude:.7f}"


def is_android() -> bool:
    try:
        import RNS
        return bool(RNS.vendor.platformutils.is_android())
    except Exception:
        return False


def has_permissions() -> bool:
    if not is_android():
        return False
    try:
        from android.permissions import check_permission
        return all(check_permission(p) for p in _ANDROID_PERMISSIONS)
    except Exception:
        return False


def request_permissions() -> None:
    """
    Ask for the location permissions if we do not already hold them.

    buildozer.spec has declared ACCESS_FINE_LOCATION and ACCESS_COARSE_LOCATION since
    before this feature existed, but a manifest declaration is not a grant: both are
    dangerous permissions, and on the app's target API they must also be requested at
    runtime. Nothing in farmui asked for them until now, so on a fresh install the fix
    would simply never arrive.

    Fire-and-forget by design. Android shows its own modal, and the farmer answers it
    before the fix attempt gets anywhere; if they decline, get_fix() times out and the
    dialog offers manual entry.
    """
    if not is_android() or has_permissions():
        return
    try:
        from android.permissions import request_permissions as _request
        _request(_ANDROID_PERMISSIONS)
    except Exception:
        pass


def get_fix(timeout: float = FIX_TIMEOUT_SECONDS) -> tuple[Optional[Fix], Optional[str]]:
    """
    Block until the phone reports a position, then return (fix, None).

    Returns (None, reason) instead if there is no GPS to read, the permissions were
    refused, or nothing arrived in time. Never raises: every failure here has to become
    a sentence the farmer can act on, not a traceback.

    Blocking, so call it from a worker thread. plyer delivers its callback on whatever
    thread Android chooses, so the caller must also marshal any UI work back through
    Clock.schedule_once.
    """
    if not is_android():
        return None, "This device has no GPS. Enter the coordinates instead."

    request_permissions()
    if not has_permissions():
        return None, ("Location permission was not granted. Allow it in Android settings, "
                      "or enter the coordinates instead.")

    try:
        from plyer import gps
    except Exception as exc:
        return None, f"Could not reach the GPS ({exc}). Enter the coordinates instead."

    best: list[Fix] = []
    done = threading.Event()
    lock = threading.Lock()

    def on_location(**kwargs):
        lat, lon = kwargs.get("lat"), kwargs.get("lon")
        if lat is None or lon is None:
            return
        accuracy = kwargs.get("accuracy")
        try:
            fix = Fix(float(lat), float(lon),
                      float(accuracy) if accuracy is not None else None)
        except (TypeError, ValueError):
            return

        with lock:
            # Keep the tightest fix seen, not the most recent: accuracy improves in fits
            # and starts, and a late reading is often worse than one from 10 s earlier.
            if not best or _tighter(fix, best[0]):
                best[:] = [fix]
            good = best[0].accuracy_m is not None and best[0].accuracy_m <= GOOD_ENOUGH_ACCURACY_M
        if good:
            done.set()

    try:
        gps.configure(on_location=on_location)
        # minTime in ms, minDistance in m. Both minimal: the farmer is standing still and
        # we want every reading Android will give us for the few seconds this runs.
        gps.start(minTime=1000, minDistance=0)
    except Exception as exc:
        return None, f"Could not start the GPS ({exc}). Enter the coordinates instead."

    try:
        done.wait(timeout)
    finally:
        try:
            gps.stop()
        except Exception:
            pass

    with lock:
        fix = best[0] if best else None

    if fix is None:
        return None, ("No GPS fix yet. Step into the open and try again, or enter the "
                      "coordinates instead.")
    return fix, None


def _tighter(candidate: Fix, incumbent: Fix) -> bool:
    """True if `candidate` is the better fix. A known accuracy always beats an unknown."""
    if candidate.accuracy_m is None:
        return False
    if incumbent.accuracy_m is None:
        return True
    return candidate.accuracy_m < incumbent.accuracy_m


def get_fix_async(on_result: Callable[[Optional[Fix], Optional[str]], None],
                  timeout: float = FIX_TIMEOUT_SECONDS) -> threading.Thread:
    """
    Run get_fix() on a worker thread and hand (fix, error) to `on_result`.

    `on_result` runs on that worker thread, so a Kivy caller must wrap its UI work in
    Clock.schedule_once — same rule the update checker in app.py follows.
    """
    def worker():
        try:
            fix, error = get_fix(timeout)
        except Exception as exc:
            # get_fix is written not to raise, but a spinner that never clears is a worse
            # failure than a message, so this stays as a backstop.
            fix, error = None, f"Could not read the GPS ({exc})."
        on_result(fix, error)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


def coordinate_filter(current: str, substring: str) -> str:
    """
    Keep only the characters that can still extend `current` into a decimal degree value.

    Digits always; a single '.'; and '-' only as the very first character. This exists
    because Kivy's built-in input_filter="float" strips everything outside [0-9.] — minus
    sign included — which would make every longitude in the Navajo region impossible to
    type into the manual-entry fallback.
    """
    kept: list[str] = []
    for ch in substring:
        if ch.isdigit():
            kept.append(ch)
        elif ch == "." and "." not in current and "." not in kept:
            kept.append(ch)
        elif ch == "-" and not current and not kept:
            kept.append(ch)
    return "".join(kept)


def parse_manual(lat_text: str, lon_text: str) -> tuple[Optional[Fix], Optional[str]]:
    """
    Validate typed coordinates into a Fix, or return (None, reason).

    accuracy_m stays None, which is_poor treats as poor -- correct here, since nothing
    vouches for a typed number. The dialog still shows the value for confirmation, which
    is the actual check on a typo.
    """
    try:
        lat = float(str(lat_text).strip())
        lon = float(str(lon_text).strip())
    except (TypeError, ValueError):
        return None, "Enter both numbers in decimal degrees, e.g. 36.0721 and -109.0450."
    if not -90.0 <= lat <= 90.0:
        return None, f"Latitude must be between -90 and 90, got {lat}."
    if not -180.0 <= lon <= 180.0:
        return None, f"Longitude must be between -180 and 180, got {lon}."
    if lat == 0.0 and lon == 0.0:
        return None, "0, 0 is in the Atlantic Ocean. Check the numbers."
    return Fix(lat, lon), None
