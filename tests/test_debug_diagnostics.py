"""
test_debug_diagnostics.py — Chip 3-state logic + Debug-tab data accessors.

The status chip must never blame the HaLow "white box" for a backend-service
condition. These tests exercise the connectivity-state machine and the
read-only diagnostics accessors the Debug tab renders.
"""
from __future__ import annotations

import os

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""

import pytest


class FakeCore:
    def __init__(self, state=None, lxmf_hex=None, service_log=None):
        self._state = state or {}
        if lxmf_hex is not None:
            import types
            self.lxmf_destination = types.SimpleNamespace(hexhash=lxmf_hex)
        self._service_log = service_log

    def getstate(self, prop, allow_cache=False):
        return self._state.get(prop)

    def get_service_log(self):
        return self._service_log


def _app(core=None, *, launch_error=None, started_at=None):
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app.sideband = core
    app._dispatcher = None
    app._service_launch_error = launch_error
    app._service_started_at = started_at
    return app


# ── Chip rewording ───────────────────────────────────────────────────────────

def test_chip_negative_text_does_not_blame_white_box():
    from sbapp.farmui.widgets import StatusChip
    text = StatusChip.status_text(StatusChip.NO_SERVICE)
    assert "white box" not in text.lower()
    # Gives a recovery hint instead of blaming the radio hardware.
    assert "restart" in text.lower()


def test_chip_three_states_distinct():
    from sbapp.farmui.widgets import StatusChip
    texts = {
        s: StatusChip.status_text(s)
        for s in (StatusChip.CONNECTED, StatusChip.CONNECTING, StatusChip.NO_SERVICE)
    }
    assert len(set(texts.values())) == 3


# ── Connectivity state machine ───────────────────────────────────────────────

def test_state_connected_on_fresh_heartbeat(monkeypatch):
    import RNS, time
    from sbapp.farmui.widgets import StatusChip
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: True)
    app = _app(FakeCore({"service.heartbeat": time.time()}))
    assert app._connectivity_state() == StatusChip.CONNECTED


def test_state_connecting_within_grace(monkeypatch):
    import RNS, time
    from sbapp.farmui.app import FarmApp
    from sbapp.farmui.widgets import StatusChip
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: True)
    app = _app(FakeCore({}), started_at=time.time())  # launched, no heartbeat yet
    assert app._connectivity_state() == StatusChip.CONNECTING


def test_state_no_service_after_grace(monkeypatch):
    import RNS, time
    from sbapp.farmui.app import FarmApp
    from sbapp.farmui.widgets import StatusChip
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: True)
    old = time.time() - (FarmApp.CONNECT_GRACE + 5)
    app = _app(FakeCore({}), started_at=old)
    assert app._connectivity_state() == StatusChip.NO_SERVICE


def test_state_no_service_on_launch_error(monkeypatch):
    import RNS
    from sbapp.farmui.widgets import StatusChip
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: True)
    app = _app(FakeCore({}), launch_error="boom")
    assert app._connectivity_state() == StatusChip.NO_SERVICE


# ── Diagnostics accessors ────────────────────────────────────────────────────

def test_local_address_and_fallback():
    app = _app(FakeCore(lxmf_hex="deadbeef"))
    assert app.local_address() == "deadbeef"
    assert _app(None).local_address() == "unavailable"


def test_heartbeat_age(monkeypatch):
    import time
    from sbapp.farmui import dev_diagnostics
    app = _app(FakeCore({"service.heartbeat": time.time() - 3}))
    age = dev_diagnostics.heartbeat_age(app)
    assert age is not None and 2.0 <= age <= 6.0
    assert dev_diagnostics.heartbeat_age(_app(FakeCore({}))) is None


def test_service_log_accessor():
    from sbapp.farmui import dev_diagnostics
    app = _app(FakeCore(service_log="line1\nline2"))
    assert dev_diagnostics.service_log_text(app) == "line1\nline2"
    assert dev_diagnostics.service_log_text(_app(FakeCore(service_log=None))) == "(no log yet)"


def test_interfaces_text_android_uses_connectivity_status(monkeypatch):
    import RNS
    from sbapp.farmui import dev_diagnostics
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: True)
    app = _app(FakeCore({"service.connectivity_status": "Local\n1 peer"}))
    assert "peer" in dev_diagnostics.interfaces_text(app)
