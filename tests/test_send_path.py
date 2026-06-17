"""
test_send_path.py — Send goes through CoreDispatcher with the correct
SidebandCore.send_message signature.

Bug fixed: app._send_and_show called `core.send_message(dest_hash, content)` —
wrong positional order and missing the required `propagation` arg. Both the
Commands path and the Debug 'Send Test Message' now route through
CoreDispatcher (content=, destination_hash=bytes, propagation=False).
"""
from __future__ import annotations

import os
import threading

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""

import pytest

GW_HEX = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"


class FakeCore:
    """Records the send_message call with the real upstream signature."""

    def __init__(self):
        self.calls = []
        self.allow_service_dispatch = False
        self.is_client = False

    def send_message(self, content, destination_hash, propagation,
                     skip_fields=False, no_display=False, attachment=None,
                     image=None, audio=None):
        self.calls.append({
            "content": content,
            "destination_hash": destination_hash,
            "propagation": propagation,
            "skip_fields": skip_fields,
        })
        return True


# ── CoreDispatcher.send_text (the shared, correct path) ──────────────────────

def test_send_text_correct_args_and_hex_conversion():
    from sbapp.farmui.dispatch import CoreDispatcher, SENDING
    core = FakeCore()
    reply = CoreDispatcher(core).send_text(GW_HEX, "hello world")
    assert reply.state == SENDING
    assert len(core.calls) == 1
    call = core.calls[0]
    assert call["content"] == "hello world"
    assert call["destination_hash"] == bytes.fromhex(GW_HEX)   # hex → bytes
    assert call["propagation"] is False                         # direct/opportunistic
    assert call["skip_fields"] is True


def test_send_command_correct_args():
    from sbapp.farmui.dispatch import CoreDispatcher
    core = FakeCore()
    CoreDispatcher(core).send_command("status", GW_HEX)
    call = core.calls[0]
    assert call["content"] == "status"
    assert call["destination_hash"] == bytes.fromhex(GW_HEX)
    assert call["propagation"] is False


# ── app._send_and_show (Commands path) routes through the dispatcher ─────────

def _make_app_with_core(core, monkeypatch):
    from sbapp.farmui.app import FarmApp
    from sbapp.farmui.dispatch import CoreDispatcher
    app = FarmApp.__new__(FarmApp)
    app.sideband = core
    app._dispatcher = CoreDispatcher(core)

    class FakeConv:
        def __init__(self):
            self.results = []
        def add_result(self, text):
            self.results.append(text)
    app._conv_screen = FakeConv()
    # Make Clock.schedule_once run callbacks immediately for deterministic tests.
    import sbapp.farmui.app as app_mod
    monkeypatch.setattr(app_mod.Clock, "schedule_once", lambda cb, t=0: cb(0))
    return app


def test_send_and_show_uses_dispatcher(monkeypatch):
    core = FakeCore()
    app = _make_app_with_core(core, monkeypatch)
    done = []
    app._send_and_show(GW_HEX, "soil", on_complete=lambda: done.append(True))
    assert len(core.calls) == 1
    assert core.calls[0]["content"] == "soil"
    assert core.calls[0]["destination_hash"] == bytes.fromhex(GW_HEX)
    assert core.calls[0]["propagation"] is False
    assert done == [True]
    assert app._conv_screen.results == []  # no failure surfaced


def test_app_does_not_call_send_message_directly():
    """Source guard: the wrong-order direct call must not return."""
    import inspect
    import sbapp.farmui.app as app_mod
    src = inspect.getsource(app_mod)
    assert "self.sideband.send_message(" not in src


# ── Debug 'Send Test Message' routes through the dispatcher ──────────────────

def test_send_test_message_routes_through_dispatcher(monkeypatch):
    core = FakeCore()
    app = _make_app_with_core(core, monkeypatch)
    ev = threading.Event()
    captured = {}

    def on_done(ok, detail):
        captured["ok"] = ok
        captured["detail"] = detail
        ev.set()

    from sbapp.farmui import dev_diagnostics
    dev_diagnostics.send_test_message(app, GW_HEX, "ping", on_done=on_done)
    assert ev.wait(3.0), "on_done was not called"
    assert captured["ok"] is True
    assert len(core.calls) == 1
    assert core.calls[0]["content"] == "ping"
    assert core.calls[0]["destination_hash"] == bytes.fromhex(GW_HEX)
    assert core.calls[0]["propagation"] is False


def test_send_test_message_rejects_bad_hex(monkeypatch):
    core = FakeCore()
    app = _make_app_with_core(core, monkeypatch)
    ev = threading.Event()
    captured = {}

    def on_done(ok, detail):
        captured["ok"] = ok
        ev.set()

    from sbapp.farmui import dev_diagnostics
    dev_diagnostics.send_test_message(app, "not-hex", "ping", on_done=on_done)
    assert ev.wait(3.0)
    assert captured["ok"] is False
    assert core.calls == []  # never reached the core
