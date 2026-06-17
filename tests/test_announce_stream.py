"""
test_announce_stream.py — client-safe announce reading for the Stream tab.

The wrapper UI is a Sideband *client* (no message_router), so core.list_announces()
silently drops peer (lxmf.delivery) announces. FarmApp.list_announces_safe() reads
the shared announce DB directly instead. This is what makes received announces
(e.g. from a stock-Sideband peer) actually show up in the wrapper's Stream.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import time

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""

import pytest


# Real Sideband announce schema (from core.py __db_init):
_SCHEMA = ("create table announce "
           "(id PRIMARY KEY, received INTEGER, source BLOB, data BLOB, "
           "dest_type BLOB, extra BLOB)")


def _make_db(rows):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute(_SCHEMA)
    con.executemany(
        "insert into announce (id, received, source, data, dest_type, extra) "
        "values (?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return path


class FakeCore:
    def __init__(self, db_path):
        self.db_path = db_path


def _app(core):
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app.sideband = core
    return app


def test_reads_peer_announce_with_name():
    peer = bytes.fromhex("46f9b38f42661bab7e027bfcec7f0bf9")
    now = int(time.time())
    path = _make_db([
        ("a1", now, peer, b"Phone B", b"lxmf.delivery", None),
    ])
    try:
        result = _app(FakeCore(path)).list_announces_safe()
        assert len(result) == 1
        assert result[0]["dest_hex"] == "46f9b38f42661bab7e027bfcec7f0bf9"
        assert result[0]["name"] == "Phone B"
        assert result[0]["type"] == "lxmf.delivery"
    finally:
        os.unlink(path)


def test_dedupes_by_source_keeps_newest():
    peer = bytes.fromhex("aabbccddeeff00112233445566778899")
    now = int(time.time())
    path = _make_db([
        ("old", now - 100, peer, b"OldName", b"lxmf.delivery", None),
        ("new", now, peer, b"NewName", b"lxmf.delivery", None),
    ])
    try:
        result = _app(FakeCore(path)).list_announces_safe()
        assert len(result) == 1                 # one entry per source
        assert result[0]["name"] == "NewName"   # newest (received desc) wins
    finally:
        os.unlink(path)


def test_empty_and_missing_db_are_safe():
    assert _app(FakeCore("/nonexistent/path.db")).list_announces_safe() == []
    path = _make_db([])
    try:
        assert _app(FakeCore(path)).list_announces_safe() == []
    finally:
        os.unlink(path)
    # no core at all
    from sbapp.farmui.app import FarmApp
    a = FarmApp.__new__(FarmApp)
    a.sideband = None
    assert a.list_announces_safe() == []


def test_send_announce_sets_wants_announce_flag():
    """The button must trigger an announce via wants.announce (the service
    consumes it), NOT call the client-crashing lxmf_announce()."""
    class FlagCore:
        def __init__(self):
            self.state = {}
            self.lxmf_announce_called = False
        def setstate(self, prop, val):
            self.state[prop] = val
        def lxmf_announce(self, *a, **k):
            self.lxmf_announce_called = True
            raise AssertionError("must not call lxmf_announce() on the client")

    core = FlagCore()
    _app(core).send_announce()
    assert core.state.get("wants.announce") is True
    assert core.lxmf_announce_called is False


def test_send_announce_no_core_is_safe():
    from sbapp.farmui.app import FarmApp
    a = FarmApp.__new__(FarmApp)
    a.sideband = None
    a.send_announce()  # must not raise


def test_time_ago_formatting():
    from sbapp.farmui.app import FarmApp
    now = time.time()
    assert FarmApp._time_ago(now).endswith("s ago")
    assert FarmApp._time_ago(now - 120) == "2m ago"
    assert FarmApp._time_ago(now - 7200) == "2h ago"
    assert FarmApp._time_ago(now - 172800) == "2d ago"
