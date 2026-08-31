"""
test_hide_and_node_picker.py — Hide-removal guards, peer aliases, time-ago
refresh, preset relabel, and Map-one-node picker.

The Talk-list Hide feature was removed (farmers kept hiding devices by
accident); these tests now guard that no Hide plumbing remains anywhere in the
wrapper. Its FarmSettings slot was replaced by wrapper-only peer aliases
(local display names keyed by LXMF destination hash). All behaviour lives in
the farmui layer; these tests never touch Sideband/RNS/LXMF. Widget wiring is
checked via source guards in the same style as test_farmui_logic.py.
"""
from __future__ import annotations

import inspect
import os
import tempfile

os.environ["KIVY_NO_ENV_CONFIG"] = "1"
os.environ["KIVY_WINDOW"] = "headless"
os.environ["DISPLAY"] = ""


def _settings_in_tmp():
    from sbapp.farmui.settings import FarmSettings
    d = tempfile.mkdtemp()
    return FarmSettings(d), d


# ── Hide removal: no Hide button, plumbing, or filtering anywhere ──────────────

def test_stream_source_has_no_hide():
    from sbapp.farmui.screens import stream as stream_mod
    src = inspect.getsource(stream_mod)
    # No Hide button, callback plumbing, or hide-contact wiring anywhere.
    # ("hide_update" — collapsing the OTA update card — is unrelated and fine.)
    assert "Hide" not in src, "the Talk list must not carry a Hide control"
    for gone in ("on_hide", "_hide_btn", "hide_contact", "_fire_hide"):
        assert gone not in src, f"stale Hide plumbing: {gone}"
    assert "on_hide" not in inspect.signature(
        stream_mod.AnnounceRow.__init__).parameters


def test_app_has_no_hide_contact():
    from sbapp.farmui.app import FarmApp
    assert not hasattr(FarmApp, "hide_contact")
    src = inspect.getsource(FarmApp._refresh_announces)
    assert "hidden" not in src, "_refresh_announces must not filter hidden contacts"


def test_settings_have_no_hidden_contacts():
    from sbapp.farmui import settings as settings_mod
    assert "hidden_contacts" not in settings_mod._DEFAULT
    s, _ = _settings_in_tmp()
    for gone in ("hide_contact", "unhide_contact", "hidden_contacts"):
        assert not hasattr(s, gone)


def test_announce_row_touch_has_no_hide_special_case():
    from sbapp.farmui.screens import stream as stream_mod
    down = inspect.getsource(stream_mod.AnnounceRow.on_touch_down)
    assert "collide_point" in down and "_press_key" in down
    assert "hide" not in down.lower()


# ── FarmSettings: peer-alias persistence (wrapper-only rename) ─────────────────

def test_peer_aliases_default_present():
    from sbapp.farmui.settings import _DEFAULT
    assert "peer_aliases" in _DEFAULT
    assert _DEFAULT["peer_aliases"] == {}


def test_peer_alias_persist_roundtrip():
    from sbapp.farmui.settings import FarmSettings
    s, d = _settings_in_tmp()
    s.set_peer_alias("abc123", "North barn phone")
    assert s.get_peer_alias("abc123") == "North barn phone"
    # Reload from disk — the alias must survive an app restart.
    s2 = FarmSettings(d)
    assert s2.get_peer_alias("abc123") == "North barn phone"
    # Clear and confirm it's gone, on disk too.
    s2.clear_peer_alias("abc123")
    assert s2.get_peer_alias("abc123") is None
    assert FarmSettings(d).get_peer_alias("abc123") is None


def test_peer_aliases_returns_copy():
    s, _ = _settings_in_tmp()
    s.set_peer_alias("abc", "Barn")
    snap = s.peer_aliases
    snap["abc"] = "mutated"  # mutating the returned dict must not affect storage
    assert s.get_peer_alias("abc") == "Barn"


def test_clear_peer_alias_of_unknown_hash_is_noop():
    s, _ = _settings_in_tmp()
    s.clear_peer_alias("never-set")
    assert s.peer_aliases == {}


def test_node_cache_persist_roundtrip():
    from sbapp.farmui.settings import FarmSettings
    s, d = _settings_in_tmp()
    s.node_cache = ["!a", "!b"]
    assert FarmSettings(d).node_cache == ["!a", "!b"]


# ── parse_nodes_reply: only "!"-prefixed node IDs, ignores other replies ───────

def test_parse_nodes_reply_extracts_ids():
    from sbapp.farmui.dispatch import parse_nodes_reply
    # Matches the gateway's "nodes" reply format.
    reply = "Known field nodes:\n  !drynode001\n  !wetnode002"
    assert parse_nodes_reply(reply) == ["!drynode001", "!wetnode002"]


def test_parse_nodes_reply_ignores_non_node_reply():
    from sbapp.farmui.dispatch import parse_nodes_reply
    status = "Farm status\nSoil: 42%\nBattery: 88%"
    assert parse_nodes_reply(status) == []


# ── parse_node_labels: the continuation line parse_nodes_reply drops ──────────

_LABELLED_REPLY = (
    "Known field nodes:\n"
    "  !061d8b62\n    \u00b7 Node A\n"
    "  !79d4bb41\n    \u00b7 Node B  \u26a0\ufe0f no readings in 2h\n"
    "  !982a7572\n    \u00b7 \u26a0\ufe0f no readings in 3h\n"
    "  !bare0001"
)


def test_parse_node_labels_reads_long_names():
    from sbapp.farmui.dispatch import parse_node_labels
    labels = parse_node_labels(_LABELLED_REPLY)
    assert labels["!061d8b62"] == "Node A"
    # A health note follows the label on the same line and must be stripped off.
    assert labels["!79d4bb41"] == "Node B"


def test_parse_node_labels_skips_note_only_and_bare_nodes():
    """A continuation carrying only a warning is not a label, and a node with no
    continuation at all has none either -- both must fall back to the id."""
    from sbapp.farmui.dispatch import parse_node_labels
    labels = parse_node_labels(_LABELLED_REPLY)
    assert "!982a7572" not in labels
    assert "!bare0001" not in labels


def test_parse_node_labels_ignores_non_node_reply():
    from sbapp.farmui.dispatch import parse_node_labels
    assert parse_node_labels("Farm status\nSoil: 42%\nBattery: 88%") == {}


def test_parse_nodes_reply_still_returns_every_id():
    """Labels are additive: a node without a name is still commandable."""
    from sbapp.farmui.dispatch import parse_nodes_reply
    assert parse_nodes_reply(_LABELLED_REPLY) == [
        "!061d8b62", "!79d4bb41", "!982a7572", "!bare0001",
    ]


def test_node_picker_button_shows_label_not_id():
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.NodePickerDialog)
    assert "labels" in inspect.signature(widgets.NodePickerDialog.__init__).parameters
    # The button reads the label; the id is what _choose() still sends.
    assert "labels.get(node_id) or node_id" in src
    assert "self._choose(nid)" in src


def test_open_node_picker_passes_labels_and_confirm_uses_them():
    from sbapp.farmui.app import FarmApp
    picker = inspect.getsource(FarmApp.open_node_picker)
    assert "labels=" in picker
    confirm = inspect.getsource(FarmApp.open_command_confirm)
    # The dialog displays the label but must keep addressing the id.
    assert "self._node_labels.get(node_id) or node_id" in confirm
    assert "node_id=node_id" in confirm


def test_node_labels_survive_relaunch():
    from sbapp.farmui import settings as settings_mod
    assert "node_labels" in settings_mod._DEFAULT
    s, _ = _settings_in_tmp()
    s.node_labels = {"!061d8b62": "Node A"}
    assert s.node_labels == {"!061d8b62": "Node A"}


# ── Preset relabels (Feature 3) ────────────────────────────────────────────────

def test_preset_labels_renamed():
    from sbapp.farmui.command_registry import COMMANDS
    by_key = {c.key: c for c in COMMANDS}
    assert by_key["position"].label == "Position"
    assert by_key["link"].label == "Sensor strength"
    # Wire strings are untouched (the help-list commands stay the same).
    assert by_key["position"].wire == "position"
    assert by_key["link"].wire == "link"


# ── FarmApp._refresh_announces: alias precedence + time-ago tick ───────────────

class _FakeStream:
    def __init__(self):
        self.added = []        # (name, dest_hex) rows shown this pass
        self.renamed = []
        self.refresh_calls = 0

    def add_announce(self, name, dest_hex, time_ago, received=None):
        self.added.append((name, dest_hex))

    def update_name(self, dest_hex, name):
        self.renamed.append((dest_hex, name))

    def refresh_times(self, formatter):
        self.refresh_calls += 1


def _app_for_refresh(stream, settings, announces):
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app.sideband = object()           # truthy — _refresh_announces guards on this
    app._settings = settings
    app._str_screen = stream
    app._announced_names = {}
    app.list_announces_safe = lambda: announces
    return app


def _ann(dest_hex, t, name="Phone"):
    return {"dest_hex": dest_hex, "name": name, "type": "lxmf.delivery", "time": t}


def test_contact_is_shown_and_times_refreshed():
    s, _ = _settings_in_tmp()
    stream = _FakeStream()
    app = _app_for_refresh(stream, s, [_ann("peer1", 1000.0)])
    app._refresh_announces()
    assert stream.added == [("Phone", "peer1")]
    assert stream.refresh_calls == 1   # "time ago" ticked this poll
    # The announced name was remembered for alias-clear fallback.
    assert app._announced_names == {"peer1": "Phone"}


def test_refresh_prefers_local_alias_over_announced_name():
    s, _ = _settings_in_tmp()
    s.set_peer_alias("peer1", "North barn phone")
    stream = _FakeStream()
    app = _app_for_refresh(stream, s, [_ann("peer1", 1000.0)])
    app._refresh_announces()
    assert stream.added == [("North barn phone", "peer1")]


def test_refresh_falls_back_to_unnamed_device():
    s, _ = _settings_in_tmp()
    stream = _FakeStream()
    app = _app_for_refresh(stream, s, [_ann("peer1", 1000.0, name="")])
    app._refresh_announces()
    assert stream.added == [("(unnamed device)", "peer1")]


# ── FarmApp.rename_peer: persists + updates header and Talk row ────────────────

class _FakePeerScreen:
    def __init__(self):
        self.shown_name = None

    def set_display_name(self, name):
        self.shown_name = name


def _app_for_rename(settings):
    from sbapp.farmui.app import FarmApp
    app = FarmApp.__new__(FarmApp)
    app._settings = settings
    app._str_screen = _FakeStream()
    app._peer_screen = _FakePeerScreen()
    app._announced_names = {"peer1": "Phone"}
    app._active_peer_hash = "peer1"
    return app


def test_rename_peer_saves_alias_and_updates_ui():
    s, _ = _settings_in_tmp()
    app = _app_for_rename(s)
    app.rename_peer("peer1", "  North barn phone  ")
    assert s.get_peer_alias("peer1") == "North barn phone"   # trimmed + persisted
    assert app._peer_screen.shown_name == "North barn phone"  # header updated
    assert app._str_screen.renamed == [("peer1", "North barn phone")]


def test_rename_peer_empty_clears_alias_and_falls_back():
    s, _ = _settings_in_tmp()
    s.set_peer_alias("peer1", "Old alias")
    app = _app_for_rename(s)
    app.rename_peer("peer1", "   ")
    assert s.get_peer_alias("peer1") is None
    assert app._peer_screen.shown_name == "Phone"            # announced name
    assert app._str_screen.renamed == [("peer1", "Phone")]


def test_rename_peer_does_not_touch_header_of_other_chat():
    s, _ = _settings_in_tmp()
    app = _app_for_rename(s)
    app._active_peer_hash = "other"
    app.rename_peer("peer1", "Barn")
    assert app._peer_screen.shown_name is None   # header untouched
    assert app._str_screen.renamed == [("peer1", "Barn")]


# ── Source guards for the widget wiring (headless-safe) ─────────────────────────

def test_refresh_announces_ticks_time_and_applies_alias():
    from sbapp.farmui import app as app_mod
    src = inspect.getsource(app_mod.FarmApp._refresh_announces)
    assert "refresh_times" in src
    assert "get_peer_alias" in src


def test_announce_row_supports_received_and_refresh():
    from sbapp.farmui.screens.stream import AnnounceRow, StreamScreen
    assert "received" in inspect.signature(AnnounceRow.__init__).parameters
    assert hasattr(AnnounceRow, "refresh_time_ago")
    assert hasattr(AnnounceRow, "set_display_name")
    assert hasattr(StreamScreen, "update_name")
    assert hasattr(StreamScreen, "refresh_times")


def test_peer_chat_has_rename_control():
    """The peer chat header carries a Rename control wired to rename_peer."""
    from sbapp.farmui.screens import peer_chat as pc_mod
    init = inspect.getsource(pc_mod.PeerChatScreen.__init__)
    assert "Rename" in init and "_open_rename" in init
    open_rename = inspect.getsource(pc_mod.PeerChatScreen._open_rename)
    assert "RenameDialog" in open_rename and "rename_peer" in open_rename
    # The dialog is a plain text-input modal with explicit Save/Cancel.
    dlg = inspect.getsource(pc_mod.RenameDialog)
    assert "TextInput" in dlg and "Save" in dlg and "Cancel" in dlg


def test_node_picker_is_selection_only():
    """NodePickerDialog must not contain a TextInput — selection only."""
    from sbapp.farmui import widgets
    src = inspect.getsource(widgets.NodePickerDialog)
    assert "TextInput" not in src
    assert "No nodes found yet" in src
    assert "Close" in src


def test_open_node_picker_uses_on_pick():
    from sbapp.farmui.app import FarmApp
    params = inspect.signature(FarmApp.open_node_picker).parameters
    assert "on_pick" in params
    # The conversation screen routes node commands through the picker, not a
    # premature dispatch.
    from sbapp.farmui.screens.conversation import ConversationScreen
    src = inspect.getsource(ConversationScreen._on_command)
    assert "open_node_picker" in src
    assert "on_pick=self._run_command" in src
    assert hasattr(ConversationScreen, "_run_command")
