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
