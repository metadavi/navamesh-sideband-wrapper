"""
test_auto_announce.py — automatic announce scheduling in the wrapper UI.

The Connect tab (manual announce button) is gone: the app now announces once
shortly after backend bring-up and then every 4 minutes. Both fires MUST go
through FarmApp.send_announce() — the `wants.announce` flag the Sideband
service consumes — never lxmf_announce() (which crashes on the Android client).
"""
from __future__ import annotations

import os

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""


class FakeClock:
    """Recorder standing in for kivy.clock.Clock (module-level name in app.py)."""
    def __init__(self):
        self.once = []
        self.intervals = []

    def schedule_once(self, cb, timeout=0):
        self.once.append((cb, timeout))
        return object()

    def schedule_interval(self, cb, timeout):
        self.intervals.append((cb, timeout))
        return object()


class FlagCore:
    """Core stub that records the wants.announce flag and forbids lxmf_announce."""
    def __init__(self):
        self.state = {}
        self.lxmf_announce_called = False

    def setstate(self, prop, val):
        self.state[prop] = val

    def lxmf_announce(self, *a, **k):
        self.lxmf_announce_called = True
        raise AssertionError("must not call lxmf_announce() on the client")


def _app(core=None):
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app.sideband = core
    return app


def test_auto_announce_schedules_startup_and_240s_interval(monkeypatch):
    import sbapp.farmui.app as app_mod
    fake = FakeClock()
    monkeypatch.setattr(app_mod, "Clock", fake)
    app = _app()
    app._start_auto_announces()
    assert fake.intervals == [(app._auto_announce_tick, 240.0)]
    assert app._auto_announce_interval == 240.0
    (cb, delay), = fake.once
    assert cb == app._auto_announce_tick
    # The first announce must land before the service-start grace expires.
    assert 0 < delay < app_mod.FarmApp.CONNECT_GRACE
    assert delay == app._auto_announce_first_delay


def test_auto_announce_never_double_schedules(monkeypatch):
    import sbapp.farmui.app as app_mod
    fake = FakeClock()
    monkeypatch.setattr(app_mod, "Clock", fake)
    app = _app()
    app._start_auto_announces()
    app._start_auto_announces()
    assert len(fake.intervals) == 1
    assert len(fake.once) == 1


def test_auto_announce_tick_uses_wants_announce_flag_only():
    core = FlagCore()
    app = _app(core)
    app._auto_announce_tick(0)
    assert core.state.get("wants.announce") is True
    assert core.lxmf_announce_called is False


def test_auto_announce_tick_without_core_is_safe():
    _app(None)._auto_announce_tick(0)  # must not raise


def test_start_backend_kicks_off_auto_announces(monkeypatch):
    import sbapp.farmui.app as app_mod
    fake = FakeClock()
    monkeypatch.setattr(app_mod, "Clock", fake)
    app = _app()
    # Instance attributes shadow the bound methods — backend bring-up stubbed.
    app._init_sideband = lambda: None
    app._ensure_hthd01_config = lambda: False
    app._start_service = lambda: None
    app._start_backend(0)
    assert len(fake.intervals) == 1
    assert len(fake.once) == 1
