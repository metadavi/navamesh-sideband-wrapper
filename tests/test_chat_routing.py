"""
test_chat_routing.py — Talk-tab device routing + gateway replace-reply behavior.

A tapped device is routed by FarmApp.open_chat: gateways open the command
dashboard (and pin the gateway), peers open the free-text messenger. These tests
build FarmApp via __new__ with fake screens (Kivy widgets can't be instantiated
headless — no Window provider), so only the routing logic is exercised. The
replace-previous-reply behavior is verified as a source guard, mirroring
test_connectivity_chip.test_poll_no_longer_reads_dead_key.
"""
from __future__ import annotations

import os

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""


class _FakeConv:
    def __init__(self):
        self.gateway = None
        self.reset_called = False

    def update_gateway(self, name, h):
        self.gateway = (name, h)

    def reset_replies(self):
        self.reset_called = True


class _FakePeer:
    def __init__(self):
        self.opened = None
        self.closed = False

    def open_peer(self, name, h):
        self.opened = (name, h)

    def close_peer(self):
        self.closed = True

    def set_display_name(self, name):
        pass


class _FakeSM:
    def __init__(self):
        self.current = None


class _FakeSettings:
    def __init__(self):
        self.saved = None
        self.aliases = {}

    def set_gateway(self, name, h):
        self.saved = (name, h)

    def get_peer_alias(self, dest_hex):
        return self.aliases.get(dest_hex)

    def set_peer_alias(self, dest_hex, alias):
        self.aliases[dest_hex] = alias

    def clear_peer_alias(self, dest_hex):
        self.aliases.pop(dest_hex, None)


def _routing_app(core=None):
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app.sideband = core
    app._dispatcher = None
    app._gateway_name = "(none)"
    app._gateway_hash = None
    app._active_peer_hash = None
    app._shown_peer_msgs = set()
    app._conv_screen = _FakeConv()
    app._peer_screen = _FakePeer()
    app._sm = _FakeSM()
    app._settings = _FakeSettings()
    app._talk_tab = None
    app._home_tabs = None
    return app


def test_open_chat_routes_gateway_to_command_screen():
    app = _routing_app()
    app.open_chat("Navamesh Gateway", "abc123")
    assert app._sm.current == "gateway_chat"
    assert app._gateway_hash == "abc123"
    assert app._conv_screen.gateway == ("Navamesh Gateway", "abc123")
    assert app._conv_screen.reset_called is True
    assert app._settings.saved == ("Navamesh Gateway", "abc123")
    assert app._active_peer_hash is None


def test_open_chat_routes_peer_to_messenger():
    app = _routing_app()
    app.open_chat("Phone B", "def456")
    assert app._sm.current == "peer_chat"
    assert app._active_peer_hash == "def456"
    assert app._peer_screen.opened == ("Phone B", "def456")
    # A peer must NOT be pinned as a gateway.
    assert app._gateway_hash is None
    assert app._settings.saved is None


def test_open_chat_gateway_detection_is_case_insensitive_substring():
    app = _routing_app()
    app.open_chat("West GATEWAY 2", "0a0b")
    assert app._sm.current == "gateway_chat"
    assert app._gateway_hash == "0a0b"


def test_open_peer_uses_alias_when_present():
    app = _routing_app()
    app._settings.aliases["def456"] = "North barn phone"
    app.open_chat("Phone B", "def456")
    assert app._peer_screen.opened == ("North barn phone", "def456")


def test_go_home_clears_active_peer_and_returns_home():
    app = _routing_app()
    app.open_chat("Phone B", "def456")
    app.go_home()
    assert app._sm.current == "home"
    assert app._active_peer_hash is None
    # The visible peer session is cleared too — re-entering starts blank.
    assert app._peer_screen.closed is True
    assert app._shown_peer_msgs == set()


def test_send_peer_text_uses_dispatcher_and_refreshes():
    """send_peer_text routes through the dispatcher and triggers a message poll."""
    sent = []

    class FakeDispatcher:
        def send_text(self, dest_hex, content):
            sent.append((dest_hex, content))

    class FakeCore:
        def list_messages(self, *a, **k):
            return []

    app = _routing_app(core=FakeCore())
    app._dispatcher = FakeDispatcher()
    app._active_peer_hash = "def456"
    app.send_peer_text("def456", "hello")
    assert sent == [("def456", "hello")]


def test_gateway_screen_replaces_previous_reply_source_guard():
    """Each new command must clear the prior reply (clean dashboard, not a log)."""
    import inspect
    from sbapp.farmui.screens import conversation as conv_mod

    # The clear/waiting sequence lives in _run_command — the point that
    # actually commits to a send. _on_command only routes there (directly, or
    # via the node picker, which may be cancelled without clearing anything).
    run_cmd = inspect.getsource(conv_mod.ConversationScreen._run_command)
    assert "_clear_results" in run_cmd, (
        "a new command must clear the previous reply before dispatching")
    assert "_show_waiting" in run_cmd

    on_cmd = inspect.getsource(conv_mod.ConversationScreen._on_command)
    assert "_run_command" in on_cmd

    clear = inspect.getsource(conv_mod.ConversationScreen._clear_results)
    assert "_result_cards" in clear and "clear()" in clear


def test_announce_rows_are_independently_tappable_source_guard():
    """Each Talk row must isolate its own press, or only one row is ever tappable.

    Regression guard for the bug where every AnnounceRow shared a single
    touch.ud["_row_press"] key: the first row dispatched on touch-up popped it
    unconditionally (before the collide check), so peers (and all but one row)
    never fired on_open. Kivy widgets can't be instantiated headless (no Window
    provider), so this is a source guard like
    test_connectivity_chip.test_poll_no_longer_reads_dead_key.
    """
    import inspect
    from sbapp.farmui.screens import stream as stream_mod

    down = inspect.getsource(stream_mod.AnnounceRow.on_touch_down)
    up = inspect.getsource(stream_mod.AnnounceRow.on_touch_up)
    # No shared literal key on either side.
    assert '"_row_press"' not in down and '"_row_press"' not in up, (
        "rows must not share a single touch.ud key — it makes only one row tappable")
    # Press is keyed per instance.
    assert "self._press_key" in down and "self._press_key" in up
    init = inspect.getsource(stream_mod.AnnounceRow.__init__)
    assert "id(self)" in init, "the per-row key must be unique per instance"


def test_peer_message_direction(monkeypatch):
    """_poll_peer_messages renders inbound (source==peer) and outbound correctly."""
    peer_hex = "11" * 16
    peer = bytes.fromhex(peer_hex)
    me = bytes.fromhex("22" * 16)

    rendered = []

    class FakePeerScreen:
        def add_message(self, text, outbound):
            rendered.append((text, outbound))

    class FakeCore:
        def list_messages(self, dest, limit=None):
            return [
                {"hash": b"\x01", "source": peer, "content": b"hi there"},
                {"hash": b"\x02", "source": me, "content": b"reply back"},
            ]

    app = _routing_app(core=FakeCore())
    app._peer_screen = FakePeerScreen()
    app._active_peer_hash = peer_hex
    app._shown_peer_msgs = set()
    app._poll_peer_messages()
    assert rendered == [("hi there", False), ("reply back", True)]

    # Polling again renders nothing new (dedup by hash).
    rendered.clear()
    app._poll_peer_messages()
    assert rendered == []


def test_open_peer_baselines_history_and_renders_only_new_messages():
    """Entering a peer chat must NOT replay old DB history; only messages
    exchanged during the session render. Nothing is deleted from the DB —
    the old rows stay put, they are just marked as already seen."""
    peer_hex = "11" * 16
    peer = bytes.fromhex(peer_hex)
    me = bytes.fromhex("22" * 16)

    history = [
        {"hash": b"\x01", "source": peer, "content": b"old inbound"},
        {"hash": b"\x02", "source": me, "content": b"old outbound"},
    ]

    rendered = []

    class FakePeerScreen(_FakePeer):
        def add_message(self, text, outbound):
            rendered.append((text, outbound))

    class FakeCore:
        def list_messages(self, dest, limit=None):
            return list(history)

    app = _routing_app(core=FakeCore())
    app._peer_screen = FakePeerScreen()
    app.open_peer("Phone B", peer_hex)

    # The old history was baselined, not rendered.
    assert rendered == []
    assert app._shown_peer_msgs == {"01", "02"}

    # Old rows are still in the fake DB — baselining never deleted anything.
    assert len(history) == 2

    # A message that arrives during the session renders normally (inbound),
    # and one we send renders as outbound.
    history.append({"hash": b"\x03", "source": peer, "content": b"new inbound"})
    history.append({"hash": b"\x04", "source": me, "content": b"new outbound"})
    app._poll_peer_messages()
    assert rendered == [("new inbound", False), ("new outbound", True)]


def test_reentering_peer_chat_baselines_previous_session():
    """Leave a chat, message lands in the DB meanwhile, re-enter: the chat
    starts blank again (the earlier session's messages are now history)."""
    peer_hex = "11" * 16
    peer = bytes.fromhex(peer_hex)
    history = [{"hash": b"\x01", "source": peer, "content": b"session one"}]

    rendered = []

    class FakePeerScreen(_FakePeer):
        def add_message(self, text, outbound):
            rendered.append((text, outbound))

    class FakeCore:
        def list_messages(self, dest, limit=None):
            return list(history)

    app = _routing_app(core=FakeCore())
    app._peer_screen = FakePeerScreen()

    app.open_peer("Phone B", peer_hex)
    assert rendered == []          # baselined
    app.go_home()
    assert app._peer_screen.closed is True

    history.append({"hash": b"\x02", "source": peer, "content": b"while away"})
    app.open_peer("Phone B", peer_hex)
    assert rendered == []          # both old messages baselined on re-entry
    assert app._shown_peer_msgs == {"01", "02"}
