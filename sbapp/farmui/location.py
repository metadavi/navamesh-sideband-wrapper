"""
location.py — one-shot GPS fix for the "Change sensor location" command.

The field nodes ship with gps_mode = NOT_PRESENT and have no receiver of their own, so
a node's position can only ever come from outside it. The stock Meshtastic app supplies
one by copying the connected phone's fix over Bluetooth; this module is where the same
fix comes from when the command travels over LoRa instead.

Why not Sideband's own telemetry Location sensor (sbapp/sideband/sense.py): it lives in
the Android foreground service process, reachable from this UI process only through
getstate/setstate, and it only runs at all once the whole telemetry subsystem is switched
on via telemetry_enabled + telemetry_s_location. That is a lot of standing machinery to
enable for a reading the farmer wants once, while standing next to a node. sense.py is
also protected upstream code (see docs/DECISION.md), so this drives Android's
LocationManager itself through jnius.

Why not plyer, which upstream's own main.py uses for its Bluetooth-scan flow: plyer's
Android GPS facade forwards lat/lon/speed/bearing/altitude/accuracy and drops the
timestamp. Without it there is no way to tell a fix taken a second ago from one taken
where the farmer was standing ten minutes and twenty metres back -- and Android hands
exactly that cached fix to every newly-registered listener. Silently pinning a node to
the previous spot is the one failure this feature must not have, so we read
getElapsedRealtimeNanos() and reject anything that is not current.

Everything here is callable off Android: get_fix() reports "no GPS on this platform" on
desktop rather than raising, so the dialog falls back to manual entry and the flow stays
testable without a phone.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

# Hard ceiling on the wait, not a target: get_fix() returns the instant a good-enough
# fix lands (see GOOD_ENOUGH_ACCURACY_M), so this only elapses in full when the phone
# genuinely cannot produce one.
#
# 120 s, sized for a satellite-only cold start. The deployed phones carry no SIM, and
# Google Location Accuracy (the network provider) is deliberately off on them, so every
# fix comes from the GNSS receiver -- there is no Wi-Fi/cell trilateration to fall back
# on. Network location would not help in the field anyway: it geolocates by matching
# nearby BSSIDs against Google's database, and the only APs out there are the farm's own
# HT-HD01 units, which Google has never surveyed.
#
# A receiver with no cached almanac has to read ephemeris off the satellites at 50 bit/s,
# which is 30-90 s and occasionally worse under partial sky. Field-observed on a fresh
# phone: every provider reporting last location=null, and 60 s was not enough to break
# the deadlock. This only bites once -- the almanac then stays cached for hours, so later
# locks are warm starts of a few seconds, and the early exit ends them immediately.
FIX_TIMEOUT_SECONDS = 120.0

# Stop early once a fix is at least this good, rather than burning the full timeout.
#
# This is Android's Location.getAccuracy(): a horizontal radius at the 68th percentile,
# NOT a mean error. "15 m" means roughly a 2-in-3 chance the true position is inside 15 m
# of the reported point -- and so a 1-in-3 chance it is outside it. Doubling the radius
# gets you to about 95%.
#
# 15 m, chosen for closely-spaced nodes: several sit together on one garden bench, and a
# loose pin puts them on top of each other on the farm map. Outdoors with a real satellite
# lock -- which is where this is actually used, standing next to a node -- GPS reports
# 3-8 m and the early exit fires within a second or two, so the tighter bar costs nothing
# in the field.
#
# It does cost indoors: Android's network provider (Wi-Fi/cell trilateration) reports
# ~20 m, which no longer satisfies this, so an indoor attempt waits out FIX_TIMEOUT_SECONDS
# before returning that same ~20 m fix. That is the right trade -- the field case is fast
# and precise, and the desk case is merely slow, not wrong.
#
# Note this threshold cannot disambiguate which node is which: the target is chosen
# explicitly from the node picker, so position never identifies a node. Nodes a metre
# apart will still land on near-identical coordinates no matter how tight this gets.
GOOD_ENOUGH_ACCURACY_M = 15.0

# Above this, the dialog warns before sending. A fix this coarse can place a node in the
# wrong part of the field, and the farmer standing next to it is the only person who can
# tell that it is wrong.
POOR_ACCURACY_M = 50.0

# A fix may be at most this old, in seconds, to count as "now".
#
# Android hands a newly-registered listener the receiver's most recent fix
# immediately, which is a real hazard for this feature: walk twenty metres, ask
# again, and the position that comes straight back can be the one from where you
# were standing before. Setting a node's location from that pins it to the wrong
# place, and it fails silently -- the confirm dialog shows plausible coordinates,
# just the previous ones.
#
# We cannot get this from plyer: its Android facade forwards only
# lat/lon/speed/bearing/altitude/accuracy and drops the timestamp entirely, so
# there is no way to tell a one-second-old fix from a ten-minute-old one. That is
# why get_fix() talks to LocationManager through jnius directly.
#
# 10 s is comfortably longer than the 1 s update interval we ask for -- a live
# receiver re-emits continuously, so genuine fixes are always well inside it --
# and far shorter than the time it takes to walk between two nodes.
# How long to wait for the farmer to answer Android's permission modal.
PERMISSION_WAIT_SECONDS = 15.0

FIX_MAX_AGE_SECONDS = 10.0

# Tolerance for a fix computed a moment before the request landed. Without it a
# fix produced in the same instant we started could be rejected as "before".
FIX_START_GRACE_SECONDS = 2.0

# Providers are requested by name. "passive" costs nothing (it only observes what
# other apps request) and is worth having for the case where something else on the
# phone is already holding the GPS on.
_ANDROID_LOCATION_PROVIDERS = ("gps", "network", "passive")

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


def fix_age_seconds(fix_elapsed_nanos, now_elapsed_nanos) -> float:
    """Age of a fix in seconds from two elapsed-realtime stamps.

    Deliberately elapsed-realtime (monotonic since boot), not wall clock: a phone
    that syncs its clock mid-attempt would otherwise appear to receive fixes from
    the future or the distant past.
    """
    try:
        age = (int(now_elapsed_nanos) - int(fix_elapsed_nanos)) / 1e9
    except (TypeError, ValueError):
        return float("inf")
    return max(0.0, age)


def is_fresh_fix(fix_elapsed_nanos, now_elapsed_nanos, start_elapsed_nanos,
                 max_age: float = FIX_MAX_AGE_SECONDS,
                 grace: float = FIX_START_GRACE_SECONDS) -> bool:
    """True when a fix belongs to the request in progress.

    Two independent rejections, because they catch different things:
      * older than `max_age`      -- a stale reading, wherever it came from.
      * taken before we asked     -- the cached fix Android hands a new listener,
                                     which is the one that pins a node to the
                                     wrong place.
    """
    if fix_age_seconds(fix_elapsed_nanos, now_elapsed_nanos) > max_age:
        return False
    try:
        return int(fix_elapsed_nanos) >= int(start_elapsed_nanos) - int(grace * 1e9)
    except (TypeError, ValueError):
        return False


def _location_manager():
    """Android LocationManager, or raise. Android only."""
    from jnius import autoclass, cast
    Context = autoclass("android.content.Context")
    mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
    ctx = mActivity.getApplicationContext()
    return cast("android.location.LocationManager",
                ctx.getSystemService(Context.LOCATION_SERVICE))


def _make_location_listener(on_location_obj):
    """A LocationListener proxy that forwards raw android.location.Location objects.

    Raw, not unpacked, because the timestamp is the whole point: plyer's facade
    forwards six scalars and drops getElapsedRealtimeNanos(), leaving no way to
    reject a stale fix.
    """
    from jnius import PythonJavaClass, java_method

    class _Listener(PythonJavaClass):
        __javainterfaces__ = ["android/location/LocationListener"]
        # Use the app's class loader. The default ("system") cannot see jnius'
        # Java side from a worker thread, which is the ClassNotFoundException
        # documented in updater.ensure_intent_binding().
        __javacontext__ = "app"

        @java_method("(Landroid/location/Location;)V")
        def onLocationChanged(self, location):
            on_location_obj(location)

        @java_method("(Ljava/util/List;)V", name="onLocationChanged")
        def onLocationChangedList(self, locations):
            # API 31+ can deliver a batch; the last entry is the newest.
            try:
                n = locations.size()
                if n:
                    on_location_obj(locations.get(n - 1))
            except Exception:
                pass

        # Required by the interface on older APIs; nothing here needs them.
        @java_method("(Ljava/lang/String;)V")
        def onProviderEnabled(self, provider):
            pass

        @java_method("(Ljava/lang/String;)V")
        def onProviderDisabled(self, provider):
            pass

        @java_method("(Ljava/lang/String;ILandroid/os/Bundle;)V")
        def onStatusChanged(self, provider, status, extras):
            pass

    return _Listener()


def get_fix(timeout: float = FIX_TIMEOUT_SECONDS,
            permission_wait: float = PERMISSION_WAIT_SECONDS
            ) -> tuple[Optional[Fix], Optional[str]]:
    """
    Block until the phone reports a *fresh* position, then return (fix, None).

    Returns (None, reason) instead if there is no GPS to read, the permissions were
    refused, or nothing arrived in time. Never raises: every failure here has to become
    a sentence the farmer can act on, not a traceback.

    Talks to LocationManager directly rather than through plyer, so that every
    reading carries getElapsedRealtimeNanos() and a cached fix from the last place
    the farmer stood can be rejected instead of silently pinning a node there.

    Blocking, so call it from a worker thread. Callbacks arrive on the main looper,
    so the caller must still marshal UI work through Clock.schedule_once.
    """
    if not is_android():
        return None, "This device has no GPS. Enter the coordinates instead."

    if not has_permissions():
        request_permissions()
        # The Android modal is answered by a human, so give them a moment rather
        # than reading the grant back in the same breath. Without this the first
        # attempt on a fresh install always failed, however fast they tapped Allow.
        deadline = time.monotonic() + permission_wait
        while time.monotonic() < deadline and not has_permissions():
            time.sleep(0.25)
    if not has_permissions():
        return None, ("Location permission was not granted. Allow it in Android settings, "
                      "or enter the coordinates instead.")

    try:
        from jnius import autoclass
        SystemClock = autoclass("android.os.SystemClock")
        Looper = autoclass("android.os.Looper")
        manager = _location_manager()
    except Exception as exc:
        return None, f"Could not reach the GPS ({exc}). Enter the coordinates instead."

    best: list[Fix] = []
    done = threading.Event()
    lock = threading.Lock()
    stale_seen = [0]
    start_nanos = SystemClock.elapsedRealtimeNanos()

    def on_location_obj(location):
        try:
            fix_nanos = location.getElapsedRealtimeNanos()
            now_nanos = SystemClock.elapsedRealtimeNanos()
            if not is_fresh_fix(fix_nanos, now_nanos, start_nanos):
                with lock:
                    stale_seen[0] += 1
                return
            lat = float(location.getLatitude())
            lon = float(location.getLongitude())
            accuracy = (float(location.getAccuracy())
                        if location.hasAccuracy() else None)
        except Exception:
            return

        fix = Fix(lat, lon, accuracy)
        with lock:
            # Keep the tightest fix seen, not the most recent: accuracy improves in fits
            # and starts, and a late reading is often worse than one from 10 s earlier.
            if not best or _tighter(fix, best[0]):
                best[:] = [fix]
            good = (best[0].accuracy_m is not None
                    and best[0].accuracy_m <= GOOD_ENOUGH_ACCURACY_M)
        if good:
            done.set()

    listener = None
    try:
        listener = _make_location_listener(on_location_obj)
        # Only enabled providers: asking a disabled one throws, and on these phones
        # the network provider is deliberately off (no SIM, and Google Location
        # Accuracy left disabled), so "gps" is usually the only live one.
        requested = 0
        for name in _ANDROID_LOCATION_PROVIDERS:
            try:
                if not manager.isProviderEnabled(name):
                    continue
                # minTime 1000 ms, minDistance 0: the farmer is standing still and we
                # want every reading Android will give us. Delivery on the main looper
                # so this worker thread does not need one of its own.
                manager.requestLocationUpdates(
                    name, 1000, 0, listener, Looper.getMainLooper())
                requested += 1
            except Exception:
                continue
        if not requested:
            return None, ("Location is switched off on this phone. Turn it on, or enter "
                          "the coordinates instead.")
    except Exception as exc:
        return None, f"Could not start the GPS ({exc}). Enter the coordinates instead."

    try:
        done.wait(timeout)
    finally:
        try:
            manager.removeUpdates(listener)
        except Exception:
            pass

    with lock:
        fix = best[0] if best else None
        stale = stale_seen[0]

    if fix is None:
        if stale:
            # We did hear from the receiver, just nothing current. Saying "no fix"
            # would send the farmer looking for open sky they are already standing in.
            return None, ("Only an old position is available. Wait a few seconds and try "
                          "again, or enter the coordinates instead.")
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
