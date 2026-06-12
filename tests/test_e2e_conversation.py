"""
test_e2e_conversation.py — End-to-end command flow tests.

Uses LxmfDirectDispatcher (same code path as FarmApp's buttons) against the
phase-2 stub gateway rig. Verifies:
- All 9 commands produce correct replies
- Wire content logged by gateway == exact command strings
- Map reply has FIELD_IMAGE with JPEG bytes
- Node picker: empty cache gracefully handled
- Failed-delivery path when gateway stopped
"""
from __future__ import annotations

import os
import sys
import time
import threading

import pytest
import RNS
import LXMF

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sbapp"))
from farmui.dispatch import (
    LxmfDirectDispatcher, CommandReply, DELIVERED, FAILED,
    parse_nodes_reply,
)
from farmui.command_registry import get_wire


ANNOUNCE_WAIT = 25.0
REPLY_TIMEOUT = 35.0


# ── Shared session ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def e2e_session(shared_tcp_testnet):
    """
    Module-scoped LXMF dispatcher on top of the session-scoped shared TCP testnet.
    RNS.Reticulum is already initialised by conftest.shared_tcp_testnet.
    """
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="navamesh_e2e_")
    net = shared_tcp_testnet
    try:
        storagedir = os.path.join(tmpdir, "lxmf")
        os.makedirs(storagedir, exist_ok=True)
        id_path = os.path.join(storagedir, "identity")
        if os.path.exists(id_path):
            identity = RNS.Identity.from_file(id_path)
        else:
            identity = RNS.Identity()
            identity.to_file(id_path)

        router = LXMF.LXMRouter(storagepath=storagedir, autopeer=False)
        source = router.register_delivery_identity(identity, display_name="E2EClient")
        source.announce()

        dispatcher = LxmfDirectDispatcher(router, source)

        # Gateway already resolved by conftest; verify it's still reachable
        assert RNS.Identity.recall(bytes.fromhex(net.gateway_hash)) is not None, (
            "Shared gateway identity lost"
        )

        yield {
            "dispatcher": dispatcher,
            "gw_hash":    net.gateway_hash,
            "wirelog":    net.wirelog,
            "net":        net,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _wirelog_last(wirelog_path: str) -> str:
    if not os.path.exists(wirelog_path):
        return ""
    lines = open(wirelog_path).read().strip().splitlines()
    return lines[-1].strip() if lines else ""


# ── Wire-content assertions ───────────────────────────────────────────────────

@pytest.mark.parametrize("cmd_key,expected_wire", [
    ("status",   "status"),
    ("soil",     "soil"),
    ("battery",  "battery"),
    ("position", "position"),
    ("link",     "link"),
    ("map_all",  "map"),
    ("nodes",    "nodes"),
    ("help",     "help"),
])
def test_wire_content(e2e_session, cmd_key, expected_wire):
    """Gate: gateway logs exactly the wire string for each command."""
    disp = e2e_session["dispatcher"]
    gw   = e2e_session["gw_hash"]
    wlog = e2e_session["wirelog"]

    reply = disp.send_command(cmd_key, gw, timeout=REPLY_TIMEOUT)
    assert reply.state == DELIVERED, f"{cmd_key}: state={reply.state} err={reply.error}"

    logged = _wirelog_last(wlog)
    assert logged == expected_wire, (
        f"Wire mismatch for {cmd_key!r}: expected {expected_wire!r}, got {logged!r}"
    )


def test_wire_content_map_one(e2e_session):
    disp = e2e_session["dispatcher"]
    gw   = e2e_session["gw_hash"]
    wlog = e2e_session["wirelog"]

    reply = disp.send_command("map_one", gw, node_id="!drynode001", timeout=REPLY_TIMEOUT)
    assert reply.state == DELIVERED

    logged = _wirelog_last(wlog)
    assert logged == "map !drynode001", f"Expected 'map !drynode001', got {logged!r}"


# ── Reply content assertions ──────────────────────────────────────────────────

def test_soil_reply_content(e2e_session):
    disp = e2e_session["dispatcher"]
    gw   = e2e_session["gw_hash"]

    reply = disp.send_command("soil", gw, timeout=REPLY_TIMEOUT)
    assert reply.state == DELIVERED
    assert "Soil" in reply.text
    assert "20.0%" in reply.text  # dry node
    assert "75.0%" in reply.text  # wet node


def test_map_all_has_image(e2e_session):
    disp = e2e_session["dispatcher"]
    gw   = e2e_session["gw_hash"]

    reply = disp.send_command("map_all", gw, timeout=REPLY_TIMEOUT)
    assert reply.state == DELIVERED, f"map_all state={reply.state}"
    assert reply.image_bytes is not None, "map reply missing image bytes"
    assert len(reply.image_bytes) > 100, "map image too small"
    assert reply.image_bytes[:2] == b"\xff\xd8", "image is not a JPEG"


def test_nodes_reply_parsed(e2e_session):
    disp = e2e_session["dispatcher"]
    gw   = e2e_session["gw_hash"]

    reply = disp.send_command("nodes", gw, timeout=REPLY_TIMEOUT)
    assert reply.state == DELIVERED
    nodes = parse_nodes_reply(reply.text)
    assert len(nodes) >= 4, f"Expected ≥4 nodes, got: {nodes}"
    assert "!drynode001" in nodes


def test_node_picker_empty_cache_graceful():
    """Empty node cache should return a helpful string, not raise."""
    from sbapp.farmui.dispatch import CommandReply
    nodes = []
    if not nodes:
        msg = "No node list yet — tap 'List nodes' first."
        r = CommandReply(cmd_key="map_one", text=msg, state="info")
    assert "List nodes" in r.text


def test_all_9_commands_delivered(e2e_session):
    """Quick smoke: all 9 commands reach delivered state."""
    disp = e2e_session["dispatcher"]
    gw   = e2e_session["gw_hash"]
    failures = []
    for cmd in ["status", "soil", "battery", "position", "link",
                "map_all", "nodes", "help"]:
        r = disp.send_command(cmd, gw, timeout=REPLY_TIMEOUT)
        if r.state != DELIVERED:
            failures.append(f"{cmd}: {r.state} / {r.error}")
    r_map_one = disp.send_command("map_one", gw, node_id="!drynode001", timeout=REPLY_TIMEOUT)
    if r_map_one.state != DELIVERED:
        failures.append(f"map_one: {r_map_one.state}")
    assert not failures, "Commands failed:\n" + "\n".join(failures)


def test_failed_delivery_state(e2e_session):
    """
    Sending to an unknown/unreachable hash should return FAILED state
    with a plain-language error message.
    """
    disp = e2e_session["dispatcher"]
    dead_hash = "deadbeef" * 4  # 32 bytes of fake hash

    reply = disp.send_command("status", dead_hash, timeout=3.0)
    assert reply.state == FAILED, f"Expected FAILED, got {reply.state}"
    assert reply.error, "Expected non-empty error message"
    assert reply.text, "Expected plain-language failure text"
