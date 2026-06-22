"""
test_connectivity_chip.py — Regression tests for the connectivity status chip.

Bug: FarmApp._poll read `getstate("misc.connectivity")`, a key the backend
never sets, so the chip was permanently stuck on
"Radio not responding — check the white box" even when Reticulum/Sideband
was working. Fixed by FarmApp._radio_is_up(), which reads a real signal:
  - Android: freshness of `service.heartbeat` (the only RPC-readable liveness
    signal, refreshed each loop by sidebandservice.py).
  - Desktop/dev: live RNS interface `.online` state / shared-instance status.

These tests construct FarmApp without Kivy's App machinery (__new__) so no
window/event loop is needed, and stub the core + platform/RNS surface.
"""
from __future__ import annotations

import os
import sys
import time

# Suppress Kivy window creation during import (same as test_farmui_logic.py)
os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""

import pytest


class FakeCore:
    """Minimal stand-in for SidebandCore exposing only getstate()."""

    def __init__(self, state=None):
        self._state = state or {}
        # Optional desktop-branch attributes; default to absent/None.
        self.interface_local = None
        self.reticulum = None

    def getstate(self, prop, allow_cache=False):
        # Mirrors SidebandCore.getstate: unknown keys return None.
        return self._state.get(prop)


def _make_app(core):
    """Build a FarmApp instance without invoking Kivy's App.__init__."""
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app.sideband = core
    return app


# ── The original bug: the dead key is never set ──────────────────────────────

def test_dead_key_is_never_set():
    """The old key returns None from a faithful getstate stub → bool() is False.

    This reproduces the exact condition that made the chip always read
    "Radio not responding": `bool(getstate("misc.connectivity"))` is False
    because nothing populates that key.
    """
    core = FakeCore({"service.heartbeat": time.time()})
    assert core.getstate("misc.connectivity") is None
    assert bool(core.getstate("misc.connectivity")) is False


def test_poll_no_longer_reads_dead_key():
    """Guard against reintroducing the dead key in the poll path."""
    import inspect
    from sbapp.farmui import app as app_mod
    src = inspect.getsource(app_mod)
    assert "misc.connectivity" not in src, (
        "Dead key 'misc.connectivity' must not be read; use _radio_is_up()."
    )
    assert "_radio_is_up" in src


# ── Android branch: heartbeat freshness ──────────────────────────────────────

@pytest.fixture
def force_android(monkeypatch):
    import RNS
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: True)


def test_android_fresh_heartbeat_is_up(force_android):
    core = FakeCore({"service.heartbeat": time.time()})
    app = _make_app(core)
    assert app._radio_is_up() is True


def test_android_stale_heartbeat_is_down(force_android):
    """A heartbeat older than HEARTBEAT_MAX_AGE means the backend is unresponsive."""
    from sbapp.farmui.app import FarmApp
    stale = time.time() - (FarmApp.HEARTBEAT_MAX_AGE + 5.0)
    app = _make_app(FakeCore({"service.heartbeat": stale}))
    assert app._radio_is_up() is False


def test_android_missing_heartbeat_is_down(force_android):
    app = _make_app(FakeCore({}))  # no heartbeat key at all
    assert app._radio_is_up() is False


# ── Desktop/dev branch: live interface status ────────────────────────────────

class FakeInterface:
    def __init__(self, online):
        self.online = online


@pytest.fixture
def force_desktop(monkeypatch):
    import RNS
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: False)
    return monkeypatch


def test_desktop_online_interface_is_up(force_desktop):
    import RNS
    force_desktop.setattr(RNS.Transport, "interfaces", [FakeInterface(online=True)])
    app = _make_app(FakeCore())
    assert app._radio_is_up() is True


def test_desktop_only_local_interface_is_down(force_desktop):
    """The local AutoInterface is excluded — it doesn't represent the radio link."""
    import RNS
    core = FakeCore()
    local = FakeInterface(online=True)
    core.interface_local = local
    force_desktop.setattr(RNS.Transport, "interfaces", [local])
    app = _make_app(core)
    assert app._radio_is_up() is False


def test_desktop_offline_interface_is_down(force_desktop):
    import RNS
    force_desktop.setattr(RNS.Transport, "interfaces", [FakeInterface(online=False)])
    app = _make_app(FakeCore())
    assert app._radio_is_up() is False


def test_desktop_shared_instance_is_up(force_desktop):
    import RNS
    force_desktop.setattr(RNS.Transport, "interfaces", [])
    core = FakeCore()
    core.reticulum = type("R", (), {"is_connected_to_shared_instance": True})()
    app = _make_app(core)
    assert app._radio_is_up() is True


# ── Safety: never raises, never mutates backend ──────────────────────────────

def test_radio_is_up_never_raises(monkeypatch):
    """A core whose getstate explodes must yield False, not propagate."""
    import RNS
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: True)

    class BoomCore:
        def getstate(self, *a, **k):
            raise RuntimeError("rpc down")

    app = _make_app(BoomCore())
    assert app._radio_is_up() is False


def test_radio_is_up_with_no_core():
    app = _make_app(None)
    assert app._radio_is_up() is False


# ── Four-state mesh status (announce-traffic signal) ─────────────────────────
#
# "Connected" no longer means just "service alive" (the old false positive).
# It now requires an announce *heard over the radio* within RADIO_LIVE_WINDOW,
# read from the shared announce DB. The four states:
#   CONNECTED  ("Mesh active")        — alive + recent announce
#   MESH_QUIET ("Mesh quiet")         — alive + announce heard before, now stale
#   CONNECTING ("Listening for mesh…")— alive + no announce heard yet
#   NO_SERVICE ("Service offline")    — service not running

def _state_app(latest_epoch, force_android, *, started_ago=None, launch_error=None,
               core_state=None):
    """A FarmApp set up enough to exercise _connectivity_state() in headless tests."""
    from sbapp.farmui.app import FarmApp
    app = _make_app(FakeCore(core_state or {"service.heartbeat": time.time()}))
    app._service_launch_error = launch_error
    app._service_started_at = (time.time() - started_ago) if started_ago is not None else None
    app._heard_any_announce = False
    # Control the "most recent heard announce" timestamp directly (the real impl
    # reads max(received) from the announce DB; tested separately below).
    app._latest_announce_epoch = lambda: latest_epoch
    return app


def test_state_mesh_active_on_recent_announce(force_android):
    from sbapp.farmui.widgets import StatusChip
    app = _state_app(time.time(), force_android)
    assert app._connectivity_state() == StatusChip.CONNECTED
    assert StatusChip.status_text(StatusChip.CONNECTED).startswith("Mesh active")


def test_state_mesh_quiet_when_announce_stale(force_android):
    from sbapp.farmui.app import FarmApp
    from sbapp.farmui.widgets import StatusChip
    stale = time.time() - (FarmApp.RADIO_LIVE_WINDOW + 30.0)
    app = _state_app(stale, force_android)
    assert app._connectivity_state() == StatusChip.MESH_QUIET


def test_state_listening_when_no_announce_yet(force_android):
    from sbapp.farmui.widgets import StatusChip
    app = _state_app(None, force_android)
    assert app._connectivity_state() == StatusChip.CONNECTING


def test_state_service_offline_when_heartbeat_stale(force_android):
    """Fresh-service-but-no-link can't read green; a dead service reads offline."""
    from sbapp.farmui.app import FarmApp
    from sbapp.farmui.widgets import StatusChip
    stale_hb = time.time() - (FarmApp.HEARTBEAT_MAX_AGE + 5.0)
    app = _state_app(time.time(), force_android,
                     started_ago=FarmApp.CONNECT_GRACE + 10.0,
                     core_state={"service.heartbeat": stale_hb})
    assert app._connectivity_state() == StatusChip.NO_SERVICE


def test_fresh_heartbeat_alone_is_not_connected(force_android):
    """The old false positive: service alive but no traffic must NOT read green."""
    from sbapp.farmui.widgets import StatusChip
    app = _state_app(None, force_android)  # heartbeat fresh, zero announces
    assert app._radio_is_up() is True
    assert app._connectivity_state() != StatusChip.CONNECTED


def test_chip_never_claims_radio_connected():
    """Wording guard: no state may render the banned phrase 'Radio Connected'."""
    from sbapp.farmui.widgets import StatusChip
    for state in (StatusChip.CONNECTED, StatusChip.CONNECTING,
                  StatusChip.MESH_QUIET, StatusChip.NO_SERVICE):
        assert "radio connected" not in StatusChip.status_text(state).lower()


def test_latest_announce_epoch_reads_db_readonly(tmp_path):
    """_latest_announce_epoch() returns max(received) from the announce table."""
    import sqlite3
    db = tmp_path / "sideband.db"
    con = sqlite3.connect(str(db))
    con.execute("create table announce (id integer primary key, received real)")
    con.executemany("insert into announce (received) values (?)",
                    [(100.0,), (250.5,), (175.0,)])
    con.commit()
    con.close()

    class DBCore:
        db_path = str(db)
    app = _make_app(DBCore())
    assert app._latest_announce_epoch() == 250.5


def test_latest_announce_epoch_none_when_no_db():
    """No db_path → None (treated as 'no traffic heard'), never raises."""
    app = _make_app(type("C", (), {"db_path": None})())
    assert app._latest_announce_epoch() is None


def test_latest_announce_epoch_none_when_empty(tmp_path):
    import sqlite3
    db = tmp_path / "empty.db"
    con = sqlite3.connect(str(db))
    con.execute("create table announce (id integer primary key, received real)")
    con.commit()
    con.close()

    class DBCore:
        db_path = str(db)
    app = _make_app(DBCore())
    assert app._latest_announce_epoch() is None
