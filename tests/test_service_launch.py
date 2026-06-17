"""
test_service_launch.py — Wrapper launches the Android foreground service.

Covers the regression where farmui never started the backend service (so
Reticulum ran nowhere, no heartbeat, announces/messages silently no-op).

All tests run headless and construct FarmApp via __new__ (no Kivy window).
"""
from __future__ import annotations

import os
import sys
import types

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""

import pytest


def _make_app(monkeypatch):
    from sbapp.farmui.app import FarmApp
    # user_data_dir is a read-only Kivy App property; override on the class.
    monkeypatch.setattr(FarmApp, "user_data_dir", "/tmp/navamesh-test", raising=False)
    app = FarmApp.__new__(FarmApp)
    app.sideband = None
    app._dispatcher = None
    app._service_launch_error = None
    app._service_started_at = None
    return app


# ── Service class name is derived, not hardcoded ─────────────────────────────

def test_service_class_name_uses_build_package():
    from sbapp.farmui.app import FarmApp
    assert (
        FarmApp._service_class_name("farm.navamesh.navameshfarm")
        == "farm.navamesh.navameshfarm.ServiceSidebandservice"
    )


def test_no_upstream_package_hardcoded_in_farmui():
    """The wrapper must not hardcode upstream's io.unsigned.sideband package."""
    import sbapp.farmui as pkg
    root = os.path.dirname(pkg.__file__)
    offenders = []
    for dirpath, _dirs, files in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(dirpath, f)
                with open(p, encoding="utf-8") as fh:
                    if "io.unsigned" in fh.read():
                        offenders.append(p)
    assert not offenders, f"Upstream package hardcoded in: {offenders}"


# ── Launch behaviour (fake jnius) ────────────────────────────────────────────

class _FakeService:
    started_with = None

    @classmethod
    def start(cls, activity, argument):
        cls.started_with = (activity, argument)


def _install_fake_jnius(monkeypatch, *, service_or_raise):
    """Inject a fake jnius.autoclass that returns an activity + service."""
    activity = types.SimpleNamespace(
        mActivity=types.SimpleNamespace(
            getPackageName=lambda: "farm.navamesh.navameshfarm"
        )
    )

    def autoclass(name):
        if name == "org.kivy.android.PythonActivity":
            return activity
        if name == "farm.navamesh.navameshfarm.ServiceSidebandservice":
            if isinstance(service_or_raise, Exception):
                raise service_or_raise
            return service_or_raise
        raise AssertionError(f"unexpected autoclass({name!r})")

    fake = types.ModuleType("jnius")
    fake.autoclass = autoclass
    monkeypatch.setitem(sys.modules, "jnius", fake)
    return activity


@pytest.fixture
def android(monkeypatch):
    import RNS
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: True)


def test_start_service_launches_with_derived_class_and_appdir(android, monkeypatch):
    _FakeService.started_with = None
    _install_fake_jnius(monkeypatch, service_or_raise=_FakeService)
    app = _make_app(monkeypatch)
    app._start_service()
    # Launched the correct, package-derived class with our app dir as argument.
    assert _FakeService.started_with is not None
    _activity, argument = _FakeService.started_with
    assert argument == "/tmp/navamesh-test"
    assert app._service_launch_error is None
    assert app._service_started_at is not None


def test_start_service_records_error_instead_of_crashing(android, monkeypatch):
    _install_fake_jnius(monkeypatch, service_or_raise=RuntimeError("no such class"))
    app = _make_app(monkeypatch)
    app._start_service()  # must not raise
    assert app._service_launch_error is not None
    assert "no such class" in app._service_launch_error


def test_start_service_noop_off_android(monkeypatch):
    import RNS
    monkeypatch.setattr(RNS.vendor.platformutils, "is_android", lambda: False)
    app = _make_app(monkeypatch)
    app._start_service()
    assert app._service_launch_error is None
    assert app._service_started_at is None


# ── Launch failure surfaces as 'no_service', not a HaLow blame ───────────────

def test_launch_failure_maps_to_no_service_state(android, monkeypatch):
    # Android scenario: no heartbeat available, and the service launch failed.
    # (Pin the platform so this doesn't depend on RNS.Transport global state
    # that other RNS-testnet tests may leave populated in the same process.)
    from sbapp.farmui.app import FarmApp
    from sbapp.farmui.widgets import StatusChip
    from sbapp.farmui import dev_diagnostics

    class FakeCore:
        def getstate(self, prop, allow_cache=False):
            return None  # no heartbeat

    app = _make_app(monkeypatch)
    app.sideband = FakeCore()
    app._service_launch_error = "boom"
    assert app._connectivity_state() == StatusChip.NO_SERVICE
    assert "launch failed: boom" in dev_diagnostics.service_status_text(app)
